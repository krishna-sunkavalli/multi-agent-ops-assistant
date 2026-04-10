"""
Agent Registry — creates and manages agents in Microsoft Foundry.

Two-layer architecture:
  1. Microsoft Foundry SDK (azure-ai-projects) registers agents via
     agents.create_version() so they appear in the new Foundry portal.
  2. Microsoft Agent Framework (agent-framework-azure-ai) wraps each
     Foundry agent for workflow orchestration and tool execution.

Foundry IQ integration:
  Agents with use_knowledge=True get AzureAISearchContextProvider
  (native Foundry IQ grounding) as a context provider — Foundry's model
  handles intelligent retrieval and reranking from the Search index.

Agent configs are loaded from YAML files in agents/configs/ for clean
separation of agent behavior (config) from runtime code.
"""
import inspect
import json
import logging
import pathlib
import threading
from typing import Annotated

import yaml
from agent_framework import Agent, ChatOptions, tool
from agent_framework_azure_ai import AzureAIClient
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    FunctionTool as FoundryFunctionTool,
    PromptAgentDefinition,
)
from azure.identity import DefaultAzureCredential
from pydantic import Field

from agents.exceptions import AgentConfigurationError

from tools.pos_tools import get_store_metrics, get_order_mix
from tools.staffing_tools import (
    get_station_throughput,
    get_staffing_positions,
    move_staff_to_station,
)
from tools.forecasting_tools import get_mobile_order_queue, get_demand_forecast
from tools.dynamic_sql import get_database_schema, run_sql_query, _schema_cache
from guardrails.content_safety import analyze_content_safety
from evals.response_evaluator import evaluate_response_quality, evaluate_agent_tools
from shared_state import get_last_interaction
from agents.knowledge import build_knowledge_provider
from config.settings import DEFAULT_STORE_ID

log = logging.getLogger(__name__)


# ── Schema injection for performance ────────────────────────────────
# Instead of agents calling get_database_schema (extra LLM round-trip),
# we inject the cached schema directly into agent instructions at build time.

_SCHEMA_AGENTS = {"operations", "diagnostics", "forecasting"}


def _build_schema_prompt() -> str:
    """
    Build a compact schema string from the pre-warmed cache.
    Called once during agent construction (after api.py pre-warms).
    Falls back to a live fetch if cache is empty.
    """
    # Use cached schema if available (pre-warmed in api.py lifespan)
    schema_data = _schema_cache.get(DEFAULT_STORE_ID)
    if not schema_data:
        schema_data = get_database_schema(DEFAULT_STORE_ID)

    tables = schema_data.get("database_tables", {})
    lines = [
        "",
        "## Database Schema (auto-injected — do NOT call get_database_schema)",
    ]
    for tbl_name, info in tables.items():
        cols = ", ".join(info.get("columns", []))
        lines.append(f"- **{tbl_name}** ({info.get('row_count', '?')} rows): {cols}")
        sample = info.get("sample", {})
        if sample:
            sample_str = "; ".join(f"{k}={v}" for k, v in sample.items())
            lines.append(f"  Sample: {sample_str}")

    domain = schema_data.get("data_domain", "")
    notes = schema_data.get("notes", "")
    if domain:
        lines.append("")
        lines.append(domain)
    if notes:
        lines.append("")
        lines.append(notes)
    return "\n".join(lines)


# ── Tool registry: map tool names (from YAML) to callable objects ───

TOOL_REGISTRY: dict[str, callable] = {
    "route_to_specialist": None,         # populated below after definition
    "get_store_metrics": get_store_metrics,
    "get_order_mix": get_order_mix,
    "get_station_throughput": get_station_throughput,
    "get_staffing_positions": get_staffing_positions,
    "move_staff_to_station": move_staff_to_station,
    "get_mobile_order_queue": get_mobile_order_queue,
    "get_demand_forecast": get_demand_forecast,
    "get_database_schema": get_database_schema,
    "run_sql_query": run_sql_query,
    "analyze_content_safety": analyze_content_safety,
    "evaluate_response_quality": evaluate_response_quality,
    "evaluate_agent_tools": evaluate_agent_tools,
    "get_last_interaction": get_last_interaction,
}


# ── Load agent configs from YAML ────────────────────────────────────

_CONFIGS_DIR = pathlib.Path(__file__).parent / "configs"


def _load_agent_configs() -> dict[str, dict]:
    """
    Load all ``*.yaml`` files from ``agents/configs/`` and return a dict
    keyed by agent short name with resolved tool callables.

    Each YAML file must define:
      - name: short identifier (e.g. "triage")
      - instructions: system prompt (string)
      - tools: list of tool function names (strings)
      - use_knowledge: bool

    Optional:
      - display_name: Foundry display name
      - description: agent description
    """
    configs: dict[str, dict] = {}

    for yaml_path in sorted(_CONFIGS_DIR.glob("*.yaml")):
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        short = raw["name"]

        # Resolve tool name strings → callable objects
        resolved_tools = []
        for tool_name in raw.get("tools", []):
            fn = TOOL_REGISTRY.get(tool_name)
            if fn is None:
                raise AgentConfigurationError(
                    f"Agent '{short}' references unknown tool '{tool_name}' "
                    f"in {yaml_path.name}. Add it to TOOL_REGISTRY."
                )
            resolved_tools.append(fn)

        configs[short] = {
            "instructions": raw["instructions"].strip(),
            "tools": resolved_tools,
            "use_knowledge": raw.get("use_knowledge", False),
            "display_name": raw.get("display_name", f"OpsAssistant-{short}"),
            "description": raw.get("description", f"Ops Assistant {short} agent"),
        }

        log.info("Loaded agent config: %s from %s", short, yaml_path.name)

    return configs


# ── Route capture for triage agent ───────────────────────────────────
# NOTE: We use a mutable dict instead of ContextVar because the Agent
# Framework executes tool functions in a copied/separate async context.
# Dict mutations are visible across all contexts sharing the same object.
_route_capture: dict[str, str | None] = {"value": None}
_route_lock = threading.Lock()

VALID_ROUTES = {"operations", "diagnostics", "forecasting", "safety", "quality"}


def route_to_specialist(
    agent_name: Annotated[
        str,
        Field(
            description=(
                "The specialist to route to: "
                "'operations', 'diagnostics', or 'forecasting'."
            )
        ),
    ],
) -> str:
    """
    Route the conversation to a specialist agent.
    Valid values: 'operations', 'diagnostics', 'forecasting'.
    """
    route = agent_name.lower().strip()
    log.info("route_to_specialist called with: %s", route)
    with _route_lock:
        _route_capture["value"] = route
    return f"Routing confirmed to {agent_name}"


# Register route_to_specialist now that it's defined
TOOL_REGISTRY["route_to_specialist"] = route_to_specialist


def get_captured_route() -> str | None:
    """Get the route captured by the last triage run."""
    with _route_lock:
        return _route_capture["value"]


def clear_captured_route():
    """Clear the captured route before a new triage run."""
    with _route_lock:
        _route_capture["value"] = None


# ── Helper: build a Foundry FunctionTool from a callable ─────────────


def _make_foundry_tool(fn) -> FoundryFunctionTool:
    """
    Build an ``azure.ai.projects.models.FunctionTool`` from a plain
    Python function so it can be attached to a PromptAgentDefinition.
    """
    sig = inspect.signature(fn)
    props = {}
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        ann = param.annotation
        ptype = "string"
        if ann is int:
            ptype = "integer"
        elif ann is float:
            ptype = "number"
        elif ann is bool:
            ptype = "boolean"
        props[name] = {"type": ptype}
        if param.default is not inspect.Parameter.empty:
            props[name]["default"] = str(param.default)

    return FoundryFunctionTool(
        name=fn.__name__,
        description=(fn.__doc__ or "").strip().split("\n")[0],
        parameters={
            "type": "object",
            "properties": props,
        },
        strict=False,
    )


# ── Agent Configs (loaded from YAML at import time) ──────────────────

AGENT_CONFIGS = _load_agent_configs()


# ── Layer 1: Register agents in Foundry portal ──────────────────────


def register_agents_in_foundry(
    project_client: AIProjectClient,
    model_deployment: str,
    triage_model_deployment: str | None = None,
) -> dict[str, str]:
    """
    Create / update every agent in Foundry via ``agents.create_version()``.
    Agents registered this way appear in the **new Foundry portal → Agents**
    page.  Returns ``{short_name: agent_name}`` mapping.

    The triage agent uses ``triage_model_deployment`` (gpt-4o-mini) for
    faster, cheaper routing decisions. All other agents use ``model_deployment``.
    """
    agent_names: dict[str, str] = {}

    for short, cfg in AGENT_CONFIGS.items():
        agent_name = cfg.get("display_name", f"OpsAssistant-{short}")
        foundry_tools = [_make_foundry_tool(t) for t in cfg["tools"]]

        # Use lighter model for triage, full model for specialists
        model = triage_model_deployment if (short == "triage" and triage_model_deployment) else model_deployment

        definition = PromptAgentDefinition(
            model=model,
            instructions=cfg["instructions"],
            tools=foundry_tools,
        )

        try:
            version = project_client.agents.create_version(
                agent_name=agent_name,
                definition=definition,
                description=cfg.get("description", f"Ops Assistant {short} agent"),
            )
            log.info(
                "Foundry agent registered: %s (version %s)",
                agent_name,
                getattr(version, "version", "?"),
            )
        except Exception as exc:
            log.warning(
                "Could not register %s in Foundry (non-fatal): %s",
                agent_name,
                exc,
            )

        agent_names[short] = agent_name

    return agent_names


# ── Layer 2: Wrap Foundry agents with Agent Framework ────────────────


def build_framework_agents(
    project_endpoint: str,
    model_deployment: str,
    credential: DefaultAzureCredential,
    agent_names: dict[str, str],
    triage_model_deployment: str | None = None,
) -> dict:
    """
    For each registered Foundry agent, create an ``AzureAIClient`` and
    construct an ``Agent`` with explicit ``ChatOptions`` for full control
    over inference parameters.

    Agents flagged with ``use_knowledge=True`` get the native Foundry IQ
    ``AzureAISearchContextProvider`` as a context provider — Foundry's model
    handles intelligent retrieval and reranking from the Search index.

    The triage agent uses ``triage_model_deployment`` (gpt-4o-mini) for
    faster, cheaper routing. All other agents use ``model_deployment``.

    Returns ``{short_name: Agent}``.
    """
    agents: dict = {}

    # Build the schema prompt once for injection into specialist agents
    schema_prompt = None
    try:
        schema_prompt = _build_schema_prompt()
        log.info("Schema prompt built (%d chars) for injection", len(schema_prompt))
    except Exception as exc:
        log.warning("Could not build schema prompt (agents will work without it): %s", exc)

    # Build the Foundry IQ context provider (shared by KB-enabled agents)
    knowledge_provider = None
    try:
        knowledge_provider = build_knowledge_provider()
        log.info("Foundry IQ context provider created")
    except Exception as exc:
        log.warning("Could not create Foundry IQ provider (non-fatal): %s", exc)

    for short, cfg in AGENT_CONFIGS.items():
        foundry_name = agent_names[short]

        # Use lighter model for triage, full model for specialists
        model = triage_model_deployment if (short == "triage" and triage_model_deployment) else model_deployment

        client = AzureAIClient(
            project_endpoint=project_endpoint,
            model_deployment_name=model,
            credential=credential,
            agent_name=foundry_name,
            use_latest_version=True,
            # Triage only needs 1 tool call (route_to_specialist) and 2
            # iterations (call + final response).  Without this cap the
            # framework's default 40 iterations causes the model to loop
            # because tool_choice="required" + instructions that forbid
            # text output keep triggering redundant tool calls.
            **({"function_invocation_configuration": {
                "max_function_calls": 1,
                "max_iterations": 2,
            }} if short == "triage" else {}),
        )

        # Wrap all plain callables with the @tool decorator for the framework
        wrapped_tools = [tool(t) for t in cfg["tools"]]

        # Inject schema into specialist agent instructions
        instructions = cfg["instructions"]
        if short in _SCHEMA_AGENTS and schema_prompt:
            instructions = instructions + "\n" + schema_prompt
            log.info("Injected schema into %s instructions (+%d chars)", short, len(schema_prompt))

        # Explicit ChatOptions — staff-eng level: every inference parameter visible
        # - store=True: let the Responses API manage conversation state server-side.
        #   Required in rc2 AzureAIClient so that tool-result turn submissions
        #   reference the previous_response_id instead of rebuilding the full
        #   payload (which hits 400 "invalid_payload" on schema mismatch).
        # - temperature: 0.0 for triage (deterministic routing), 0.1 for specialists
        # - tool_choice: "required" forces triage to always call route_to_specialist;
        #   "auto" lets specialists decide when to use tools
        options = ChatOptions(
            store=True,
            temperature=0.0 if short == "triage" else 0.1,
            tool_choice="required" if short == "triage" else "auto",
        )

        # Build kwargs for Agent constructor
        agent_kwargs = dict(
            client=client,
            name=foundry_name,
            instructions=instructions,
            tools=wrapped_tools,
            default_options=options,
        )

        # Add native Foundry IQ context provider for KB-enabled agents
        if cfg.get("use_knowledge") and knowledge_provider:
            agent_kwargs["context_providers"] = [knowledge_provider]

        agent = Agent(**agent_kwargs)

        agents[short] = agent
        log.info(
            "Framework agent ready: %s → %s (KB: %s, temp: %.1f, tool_choice: %s)",
            short,
            foundry_name,
            "yes" if cfg.get("use_knowledge") and knowledge_provider else "no",
            options["temperature"],
            options["tool_choice"],
        )

    return agents


async def cleanup_agents(agents: dict) -> None:
    """
    Gracefully close all Agent Framework agents on shutdown.
    Calls agent.close() to release server-side resources and connections.
    """
    if not agents:
        return

    for short, agent in agents.items():
        try:
            close_fn = getattr(agent, "close", None)
            if callable(close_fn):
                await close_fn()
                log.info("Closed agent: %s", short)
        except Exception as exc:
            log.warning("Error closing agent %s (non-fatal): %s", short, exc)

    agents.clear()
    log.info("Agent cleanup completed")
