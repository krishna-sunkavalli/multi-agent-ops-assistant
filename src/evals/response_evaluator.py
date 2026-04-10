"""
Microsoft Foundry evaluation for Ops Assistant.

Two evaluation modes:
  1. Response Quality — CoherenceEvaluator, FluencyEvaluator,
     RelevanceEvaluator, GroundednessEvaluator (1-5 scale)
  2. Agent Tool Quality — built-in Foundry agent evaluators:
     ToolCallAccuracyEvaluator, _ToolCallSuccessEvaluator,
     _ToolOutputUtilizationEvaluator, IntentResolutionEvaluator,
     TaskAdherenceEvaluator, ResponseCompletenessEvaluator

Both use the evaluate() batch API so every run is logged to the
Foundry portal (Build → Evaluations) for comparison and auditing.
"""

import json
import logging
import time

log = logging.getLogger(__name__)

# ── Lazy-initialized state ───────────────────────────────────────────

_model_config: dict | None = None
_azure_ai_project: dict | None = None
_initialized = False


def _init_eval_config():
    """Lazy-init model config and project context on first use."""
    global _model_config, _azure_ai_project, _initialized
    if _initialized:
        return

    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from config.settings import (
            AZURE_OPENAI_ENDPOINT,
            MODEL_DEPLOYMENT_NAME,
            AZURE_SUBSCRIPTION_ID,
            AZURE_RESOURCE_GROUP,
            AZURE_PROJECT_NAME,
        )

        if not AZURE_OPENAI_ENDPOINT:
            log.warning("AZURE_OPENAI_ENDPOINT not set — evaluators disabled")
            _initialized = True
            return

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )

        _model_config = {
            "azure_endpoint": AZURE_OPENAI_ENDPOINT,
            "azure_deployment": MODEL_DEPLOYMENT_NAME,
            "azure_ad_token_provider": token_provider,
        }

        # Project context — required for logging results to Foundry portal
        _azure_ai_project = {
            "subscription_id": AZURE_SUBSCRIPTION_ID,
            "resource_group_name": AZURE_RESOURCE_GROUP,
            "project_name": AZURE_PROJECT_NAME,
        }

        log.info(
            "Eval config ready — project: %s/%s/%s",
            AZURE_SUBSCRIPTION_ID[:8],
            AZURE_RESOURCE_GROUP,
            AZURE_PROJECT_NAME,
        )
    except Exception as e:
        log.warning("Eval config init failed (non-fatal): %s", e)

    _initialized = True


# ── Tool 1: Response Quality ─────────────────────────────────────────


def evaluate_response_quality(
    query: str,
    response: str,
    context: str = "",
) -> str:
    """
    Evaluate agent response quality using Microsoft Foundry evaluators.
    Runs coherence, fluency, relevance, and groundedness evaluations.
    Results are logged to the Foundry portal Evaluations page.
    Scores are on a 1-5 scale (1=poor, 5=excellent).

    Parameters:
        query: The user's original question
        response: The agent's response to evaluate
        context: Optional grounding context (for groundedness evaluation)
    """
    _init_eval_config()

    if not _model_config:
        return json.dumps(
            {
                "error": "Evaluators not available. Check AZURE_OPENAI_ENDPOINT.",
                "scores": {},
            }
        )

    try:
        from azure.ai.evaluation import (
            evaluate,
            CoherenceEvaluator,
            FluencyEvaluator,
            RelevanceEvaluator,
            GroundednessEvaluator,
        )

        evaluators = {
            "coherence": CoherenceEvaluator(model_config=_model_config),
            "fluency": FluencyEvaluator(model_config=_model_config),
            "relevance": RelevanceEvaluator(model_config=_model_config),
        }

        data_row = {"query": query, "response": response}

        if context:
            data_row["context"] = context
            evaluators["groundedness"] = GroundednessEvaluator(
                model_config=_model_config
            )

        eval_name = f"ops-assistant-quality-{int(time.time())}"
        eval_kwargs = dict(
            data=[data_row],
            evaluators=evaluators,
            evaluation_name=eval_name,
        )

        if _azure_ai_project:
            eval_kwargs["azure_ai_project"] = _azure_ai_project

        result = evaluate(**eval_kwargs)

        scores = _extract_scores(result)

        output = {
            "scores": scores,
            "scale": "1-5 (1=poor, 5=excellent)",
            "evaluation_name": eval_name,
            "logged_to_foundry": bool(_azure_ai_project),
            "foundry_location": "Foundry portal → Build → Evaluations",
        }

        log.info("Response quality eval '%s' — scores: %s", eval_name, scores)
        return json.dumps(output, indent=2)

    except Exception as e:
        log.error("Response quality evaluation failed: %s", e, exc_info=True)
        return json.dumps(
            {"error": str(e), "scores": {}, "logged_to_foundry": False}
        )


# ── Tool 2: Agent Tool Quality (built-in Foundry agent evaluators) ──


def evaluate_agent_tools(
    query: str,
    response: str,
    tool_calls_json: str = "[]",
    tool_definitions_json: str = "[]",
) -> str:
    """
    Evaluate agent tool usage using built-in Foundry agent evaluators.
    Runs ToolCallAccuracy, ToolCallSuccess, IntentResolution,
    TaskAdherence, and ResponseCompleteness evaluations.
    Results are logged to the Foundry portal Evaluations page.

    Parameters:
        query: The user's original question
        response: The agent's response to evaluate
        tool_calls_json: JSON string of tool calls made during the interaction
        tool_definitions_json: JSON string of tool definitions available to the agent
    """
    _init_eval_config()

    if not _model_config:
        return json.dumps(
            {
                "error": "Evaluators not available. Check AZURE_OPENAI_ENDPOINT.",
                "scores": {},
            }
        )

    try:
        tool_calls = json.loads(tool_calls_json) if isinstance(tool_calls_json, str) else tool_calls_json
        tool_definitions = json.loads(tool_definitions_json) if isinstance(tool_definitions_json, str) else tool_definitions_json
    except json.JSONDecodeError:
        tool_calls = []
        tool_definitions = []

    try:
        from azure.ai.evaluation import evaluate

        evaluators = {}
        data_row = {"query": query, "response": response}

        # ── Quality evaluators (query + response only) ──
        try:
            from azure.ai.evaluation import IntentResolutionEvaluator
            evaluators["intent_resolution"] = IntentResolutionEvaluator(
                model_config=_model_config
            )
        except ImportError:
            log.debug("IntentResolutionEvaluator not available")

        try:
            from azure.ai.evaluation import TaskAdherenceEvaluator
            evaluators["task_adherence"] = TaskAdherenceEvaluator(
                model_config=_model_config
            )
        except ImportError:
            log.debug("TaskAdherenceEvaluator not available")

        try:
            from azure.ai.evaluation import ResponseCompletenessEvaluator
            evaluators["response_completeness"] = ResponseCompletenessEvaluator(
                model_config=_model_config
            )
        except ImportError:
            log.debug("ResponseCompletenessEvaluator not available")

        # ── Tool-call evaluators (need tool_calls + tool_definitions) ──
        if tool_calls and tool_definitions:
            data_row["tool_calls"] = tool_calls
            data_row["tool_definitions"] = tool_definitions

            try:
                from azure.ai.evaluation import ToolCallAccuracyEvaluator
                evaluators["tool_call_accuracy"] = ToolCallAccuracyEvaluator(
                    model_config=_model_config
                )
            except ImportError:
                log.debug("ToolCallAccuracyEvaluator not available")

            try:
                from azure.ai.evaluation import _ToolCallSuccessEvaluator
                evaluators["tool_call_success"] = _ToolCallSuccessEvaluator(
                    model_config=_model_config
                )
            except ImportError:
                log.debug("_ToolCallSuccessEvaluator not available")

            try:
                from azure.ai.evaluation import _ToolOutputUtilizationEvaluator
                evaluators["tool_output_utilization"] = _ToolOutputUtilizationEvaluator(
                    model_config=_model_config
                )
            except ImportError:
                log.debug("_ToolOutputUtilizationEvaluator not available")

        if not evaluators:
            return json.dumps({"error": "No agent evaluators available", "scores": {}})

        eval_name = f"ops-assistant-agent-{int(time.time())}"
        eval_kwargs = dict(
            data=[data_row],
            evaluators=evaluators,
            evaluation_name=eval_name,
        )

        if _azure_ai_project:
            eval_kwargs["azure_ai_project"] = _azure_ai_project

        result = evaluate(**eval_kwargs)

        scores = _extract_scores(result)

        # Categorize scores for cleaner output
        tool_scores = {k: v for k, v in scores.items() if "tool" in k.lower()}
        quality_scores = {k: v for k, v in scores.items() if k not in tool_scores}

        output = {
            "tool_usage_scores": tool_scores,
            "quality_scores": quality_scores,
            "evaluators_used": list(evaluators.keys()),
            "tool_calls_evaluated": len(tool_calls),
            "evaluation_name": eval_name,
            "logged_to_foundry": bool(_azure_ai_project),
            "foundry_location": "Foundry portal → Build → Evaluations",
        }

        log.info(
            "Agent tool eval '%s' — tool: %s, quality: %s",
            eval_name, tool_scores, quality_scores,
        )
        return json.dumps(output, indent=2)

    except Exception as e:
        log.error("Agent tool evaluation failed: %s", e, exc_info=True)
        return json.dumps(
            {"error": str(e), "scores": {}, "logged_to_foundry": False}
        )


# ── Shared helper ─────────────────────────────────────────────────────


def _extract_scores(result: dict) -> dict:
    """Pull numeric/bool scores from an evaluate() result."""
    metrics = result.get("metrics", {})
    scores = {}
    for k, v in metrics.items():
        if isinstance(v, (int, float)):
            scores[k] = round(v, 2)
        elif isinstance(v, bool):
            scores[k] = v
        elif isinstance(v, str) and v.lower() in ("true", "false"):
            scores[k] = v.lower() == "true"

    if not scores and "rows" in result:
        rows = result["rows"]
        if rows:
            skip = {"query", "response", "context", "tool_calls", "tool_definitions"}
            for k, v in rows[0].items():
                if k in skip:
                    continue
                if isinstance(v, (int, float)):
                    scores[k] = round(v, 2)
                elif isinstance(v, bool):
                    scores[k] = v
    return scores
