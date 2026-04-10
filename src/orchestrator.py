"""
Multi-agent orchestrator using Microsoft Agent Framework.
Uses Agent.run() for triage → specialist routing.
Supports streaming responses via Agent.run(stream=True).

Architecture:
  - Agents registered in Foundry (azure-ai-projects) for portal visibility
  - Agent Framework wraps them for orchestration & auto tool execution
  - Triage agent calls route_to_specialist → captured via mutable dict
  - Specialist agent runs with persistent session per specialist
  - Streaming: specialist uses stream=True, yielding token deltas via WebSocket
  - Content Safety guardrails: pre-check input, post-check output
  - Shared state: last interaction stored for Quality Agent evaluation
"""
import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from agent_framework import AgentSession

# Retry config for Azure OpenAI 429 rate limits
_MAX_RETRIES = 3
_BASE_DELAY = 2  # seconds

from agents.exceptions import (
    AgentRoutingError,
    AgentNotFoundError,
    AgentExecutionError,
    ContentSafetyViolation,
)
from agents.registry import get_captured_route, clear_captured_route, VALID_ROUTES, AGENT_CONFIGS
from guardrails.content_safety import check_safety
from models.messages import OrchestratorResult, SafetyResult, StreamEvent
from shared_state import update_last_interaction

log = logging.getLogger(__name__)

DISPLAY_NAMES = {
    "operations": "Operations Agent",
    "diagnostics": "Diagnostics Agent",
    "forecasting": "Forecasting Agent",
    "safety": "Safety Agent",
    "quality": "Quality Agent",
}


def _is_rate_limit(exc: Exception) -> bool:
    """Check if an exception is a 429 rate-limit error."""
    msg = str(exc).lower()
    return "429" in msg or "too_many_requests" in msg or "rate limit" in msg


def _friendly_error(exc: Exception | None) -> str:
    """Return a short, user-friendly error summary."""
    if exc is None:
        return "unknown error"
    msg = str(exc)
    # Extract just the retry-after hint if present
    match = re.search(r"retry after (\d+)", msg, re.IGNORECASE)
    if match:
        return f"retry after {match.group(1)}s"
    if "429" in msg or "too_many_requests" in msg:
        return "Azure OpenAI rate limit exceeded"
    return msg[:120]


_FOLLOWUP_RE = re.compile(r'\[FOLLOWUP:\s*(\[.*?\])\s*\]', re.DOTALL)

# Deterministic keyword overrides — checked BEFORE calling the LLM triage.
# KEEP THIS LIST MINIMAL. The triage agent (LLM) handles the vast majority
# of routing autonomously. Only add overrides here for edge cases where the
# LLM cannot reliably disambiguate (e.g., single-word confirmations that
# lack enough context for the model to reason about).
_KEYWORD_OVERRIDES: list[tuple[re.Pattern, str]] = [
    # Bare confirmations — no semantic context for the LLM to work with,
    # and these always refer to a preceding diagnostics recommendation.
    (re.compile(r'^\s*(yes|do\s+it|go\s+ahead|proceed|confirm|approved?|sure)\s*[.!]?\s*$', re.I), "diagnostics"),
]


def _extract_suggestions(text: str) -> tuple[str, list[str]]:
    """Strip [FOLLOWUP:[...]] from response text and return (clean_text, suggestions)."""
    m = _FOLLOWUP_RE.search(text)
    if not m:
        return text, []
    try:
        suggestions = json.loads(m.group(1))
        if isinstance(suggestions, list):
            suggestions = [str(s).strip() for s in suggestions if s]
    except (json.JSONDecodeError, TypeError):
        suggestions = []
    clean = text[:m.start()].rstrip()
    return clean, suggestions


class OpsAssistantOrchestrator:
    """
    Orchestrates multi-agent conversation using Agent Framework agents
    backed by Foundry-hosted agent definitions.

    Flow per message:
    1. Run TriageAgent → calls route_to_specialist(agent_name)
    2. Run the chosen specialist with persistent session
    3. Specialist calls its tools (auto-executed by framework)
    4. Return specialist's response text

    ⚠️  SINGLE-USER DEMO: Specialist sessions (_specialist_sessions) are
    held in-memory per orchestrator instance (one per WebSocket connection).
    Nothing is persisted.  In production, store conversation turns in a
    database and reload session context on reconnect.
    """

    def __init__(self, agents: dict):
        self.agents = agents
        self._specialist_sessions: dict[str, AgentSession] = {}
        self._last_specialist_result: dict = {}
        self._tool_defs_cache: dict[str, list] = {}  # cached per specialist

    async def process_message(self, user_msg: str) -> OrchestratorResult:
        """
        Process a user message through the multi-agent pipeline.

        Flow:
        1. INPUT GUARDRAIL — check user message for harmful content
        2. Triage → route to specialist
        3. Specialist → generate response
        4. OUTPUT GUARDRAIL — check response for harmful content
        5. Store interaction for Quality Agent evaluation
        6. Return response + safety metadata
        """
        # ── Step 1+2: Input safety + triage IN PARALLEL ──
        input_safety_task = asyncio.to_thread(check_safety, user_msg)
        triage_task = self._run_triage(user_msg)
        input_safety, specialist_name = await asyncio.gather(
            input_safety_task, triage_task
        )

        if not input_safety["safe"]:
            log.warning(
                "Input blocked by content safety: %s", input_safety["flagged"]
            )
            return OrchestratorResult(
                agent_name="Safety Guard",
                response=(
                    "⚠️ **Content Safety Alert**\n\n"
                    "Your message was flagged for potentially harmful content "
                    f"({', '.join(input_safety['flagged'])}).\n\n"
                    "Please rephrase your question. This system monitors for "
                    "hate speech, violence, self-harm, and sexual content."
                ),
                safety=SafetyResult(
                    input_safe=False,
                    output_safe=True,
                    categories=input_safety["categories"],
                    flagged=input_safety["flagged"],
                    available=input_safety.get("available", False),
                ),
            )

        log.info("Triage routed to: %s", specialist_name)

        # ── Step 3: Run specialist ──
        response_text = await self._run_specialist(specialist_name, user_msg)

        # ── Step 4: Output safety guardrail (background — non-blocking) ──
        # Fire the check but don't block response delivery. If flagged,
        # log a warning. Harmful outputs are also caught by Azure OpenAI's
        # built-in content filters at the model level.
        async def _bg_output_check(text: str) -> None:
            try:
                result = await asyncio.to_thread(check_safety, text)
                if not result["safe"]:
                    log.warning(
                        "Output safety flagged (background): %s",
                        result["flagged"],
                    )
            except Exception as exc:
                log.debug("Background output safety check failed: %s", exc)

        asyncio.create_task(_bg_output_check(response_text))

        # ── Step 5: Store for Quality Agent (includes tool call data) ──
        tool_calls, tool_defs = self._extract_tool_data(specialist_name)

        # ── Step 5b: Extract follow-up suggestions from response ──
        clean_response, suggestions = _extract_suggestions(response_text)

        update_last_interaction(
            query=user_msg,
            response=clean_response,
            agent=DISPLAY_NAMES.get(specialist_name, specialist_name),
            tool_calls=tool_calls,
            tool_definitions=tool_defs,
        )

        # ── Step 6: Return with safety metadata + suggestions ──
        return OrchestratorResult(
            agent_name=DISPLAY_NAMES.get(specialist_name, specialist_name),
            response=clean_response,
            suggestions=suggestions,
            safety=SafetyResult(
                input_safe=True,
                output_safe=True,
                categories=input_safety.get("categories", {}),
                flagged=[],
                available=input_safety.get("available", False),
            ),
        )

    async def _run_triage(self, user_msg: str) -> str:
        """
        Run the triage agent to get a routing decision.
        Uses multiple strategies to capture the route:
          1. Mutable dict set by route_to_specialist (primary)
          2. Parse tool call arguments from AgentResponse (fallback)
          3. Keyword scan of response text (last resort)
        """
        # ── Strategy 0: deterministic keyword overrides ──
        for pattern, route in _KEYWORD_OVERRIDES:
            if pattern.search(user_msg):
                log.info("Keyword override matched → %s", route)
                return route

        clear_captured_route()

        triage = self.agents.get("triage")
        if not triage:
            raise AgentNotFoundError("Triage agent not registered. Check agent configs.")

        result = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                result = await triage.run(user_msg)
                break
            except Exception as e:
                if _is_rate_limit(e) and attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2 ** attempt)
                    log.warning(
                        "Triage hit 429 rate limit, retry %d/%d in %ds",
                        attempt + 1, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    log.error("Triage run failed: %s", e)
                    break

        # Strategy 1: route captured via mutable dict
        captured = get_captured_route()
        if captured and captured in VALID_ROUTES:
            log.info("Route captured via dict: %s", captured)
            return captured

        # Strategy 2: parse tool call arguments from AgentResponse
        if result:
            route = self._extract_route_from_response(result)
            if route:
                log.info("Route extracted from response messages: %s", route)
                return route

        # Strategy 3: keyword scan of response text
        if result:
            route = self._extract_route_from_text(result)
            if route:
                log.info("Route extracted from text: %s", route)
                return route

        log.warning("Could not determine route, defaulting to operations")
        return "operations"

    def _extract_route_from_response(self, result) -> str | None:
        """Parse tool call arguments from the AgentResponse messages."""
        try:
            if not hasattr(result, "messages"):
                return None
            for msg in result.messages:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        fn_name = None
                        fn_args = None
                        if hasattr(tc, "function"):
                            fn_name = getattr(tc.function, "name", None)
                            fn_args = getattr(tc.function, "arguments", None)
                        elif hasattr(tc, "name"):
                            fn_name = tc.name
                            fn_args = getattr(tc, "arguments", None)
                        if fn_name == "route_to_specialist" and fn_args:
                            if isinstance(fn_args, str):
                                args = json.loads(fn_args)
                            else:
                                args = fn_args
                            agent = args.get("agent_name", "").lower().strip()
                            if agent in VALID_ROUTES:
                                return agent
                if hasattr(msg, "content") and isinstance(msg.content, list):
                    for part in msg.content:
                        if hasattr(part, "type") and part.type == "tool_use":
                            if getattr(part, "name", None) == "route_to_specialist":
                                inp = getattr(part, "input", {})
                                agent = inp.get("agent_name", "").lower().strip()
                                if agent in VALID_ROUTES:
                                    return agent
        except Exception as e:
            log.debug("Failed to extract route from response: %s", e)
        return None

    def _extract_route_from_text(self, result) -> str | None:
        """Last resort: scan response text for route keywords."""
        try:
            text = ""
            if hasattr(result, "text") and result.text:
                text = result.text.lower()
            elif hasattr(result, "messages"):
                for msg in reversed(result.messages):
                    if hasattr(msg, "content") and isinstance(msg.content, str):
                        text = msg.content.lower()
                        break
            if not text:
                return None
            for route in ["diagnostics", "forecasting", "operations"]:
                if route in text:
                    return route
        except Exception as e:
            log.debug("Failed to extract route from text: %s", e)
        return None

    def _extract_tool_data(self, specialist_name: str) -> tuple[list, list]:
        """
        Extract tool call history and tool definitions for the specialist
        from the last agent session. Used by built-in Foundry evaluators
        (ToolCallAccuracy, ToolCallSuccess, etc.).
        """
        tool_calls = []
        tool_defs = []

        # Get tool definitions from agent config (cached after first build)
        if specialist_name in self._tool_defs_cache:
            tool_defs = self._tool_defs_cache[specialist_name]
        else:
            cfg = AGENT_CONFIGS.get(specialist_name, {})
            for fn in cfg.get("tools", []):
                import inspect
                sig = inspect.signature(fn)
                params = {}
                for pname, param in sig.parameters.items():
                    if pname in ("self", "cls"):
                        continue
                    ann = param.annotation
                    ptype = "string"
                    if ann is int:
                        ptype = "integer"
                    elif ann is float:
                        ptype = "number"
                    elif ann is bool:
                        ptype = "boolean"
                    params[pname] = {"type": ptype}
                tool_defs.append({
                    "type": "function",
                    "function": {
                        "name": fn.__name__,
                        "description": (fn.__doc__ or "").strip().split("\n")[0],
                        "parameters": {"type": "object", "properties": params},
                    },
                })
            self._tool_defs_cache[specialist_name] = tool_defs

        # Extract tool calls from the specialist session
        session = self._specialist_sessions.get(specialist_name)
        if session and hasattr(session, "messages"):
            try:
                for msg in session.messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            call = {"type": "function"}
                            if hasattr(tc, "function"):
                                call["function"] = {
                                    "name": getattr(tc.function, "name", ""),
                                    "arguments": getattr(tc.function, "arguments", "{}"),
                                }
                            elif hasattr(tc, "name"):
                                call["function"] = {
                                    "name": tc.name,
                                    "arguments": getattr(tc, "arguments", "{}"),
                                }
                            tool_calls.append(call)
            except Exception as e:
                log.debug("Could not extract tool calls: %s", e)

        # Also try to find tool calls from the last run result
        last_result = self._last_specialist_result.get(specialist_name)
        if not tool_calls and last_result and hasattr(last_result, "messages"):
            try:
                for msg in last_result.messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            call = {"type": "function"}
                            if hasattr(tc, "function"):
                                call["function"] = {
                                    "name": getattr(tc.function, "name", ""),
                                    "arguments": getattr(tc.function, "arguments", "{}"),
                                }
                            elif hasattr(tc, "name"):
                                call["function"] = {
                                    "name": tc.name,
                                    "arguments": getattr(tc, "arguments", "{}"),
                                }
                            tool_calls.append(call)
            except Exception as e:
                log.debug("Could not extract tool calls from result: %s", e)

        log.info(
            "Extracted %d tool calls, %d tool defs for %s",
            len(tool_calls), len(tool_defs), specialist_name,
        )
        return tool_calls, tool_defs

    async def _run_specialist(self, specialist_name: str, user_msg: str) -> str:
        """
        Run a specialist agent with the user message.
        Each specialist keeps its own persistent AgentSession for
        conversation history.
        """
        agent = self.agents.get(specialist_name)
        if not agent:
            raise AgentNotFoundError(
                f"Specialist '{specialist_name}' not registered. "
                f"Valid agents: {list(self.agents.keys())}"
            )

        session = self._specialist_sessions.get(specialist_name)
        if session is None:
            session = AgentSession()
            self._specialist_sessions[specialist_name] = session

        last_error = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                result = await agent.run(user_msg, session=session)
                self._last_specialist_result[specialist_name] = result

                response_text = ""
                if result and hasattr(result, "messages"):
                    for msg in reversed(result.messages):
                        if hasattr(msg, "role") and str(msg.role) == "assistant":
                            if hasattr(msg, "content"):
                                if isinstance(msg.content, str):
                                    response_text = msg.content
                                elif isinstance(msg.content, list):
                                    parts = []
                                    for part in msg.content:
                                        if hasattr(part, "text"):
                                            parts.append(part.text)
                                        elif isinstance(part, str):
                                            parts.append(part)
                                    response_text = "".join(parts)
                            break

                if not response_text:
                    if hasattr(result, "text"):
                        response_text = result.text or ""

                if not response_text:
                    response_text = "No response received."

                log.info(
                    "Specialist %s responded (%d chars)",
                    specialist_name,
                    len(response_text),
                )
                return response_text
            except Exception as e:
                last_error = e
                if _is_rate_limit(e) and attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2 ** attempt)
                    log.warning(
                        "Specialist %s hit 429 rate limit, retry %d/%d in %ds",
                        specialist_name, attempt + 1, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    log.error("Specialist %s run failed: %s", specialist_name, e)
                    break

        if last_error and _is_rate_limit(last_error):
            return (
                "I'm experiencing high demand right now. "
                "Please try again in a few seconds."
            )
        return (
            "I wasn't able to process that request. "
            f"({_friendly_error(last_error)})"
        )

    # ── Streaming Methods ──────────────────────────────────────────────

    async def _run_specialist_stream(
        self, specialist_name: str, user_msg: str
    ) -> AsyncGenerator[str, None]:
        """
        Stream a specialist agent response, yielding text deltas.
        Uses Agent.run(stream=True) for real token-by-token streaming.
        Falls back to a single error-text yield on failure.
        """
        agent = self.agents.get(specialist_name)
        if not agent:
            raise AgentNotFoundError(
                f"Specialist '{specialist_name}' not registered. "
                f"Valid agents: {list(self.agents.keys())}"
            )

        session = self._specialist_sessions.get(specialist_name)
        if session is None:
            session = AgentSession()
            self._specialist_sessions[specialist_name] = session

        last_error = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                stream = await agent.run(user_msg, stream=True, session=session)
                async for update in stream:
                    if not update.contents:
                        continue
                    for content in update.contents:
                        if content.type == "text" and content.text:
                            yield content.text

                # Finalize — store result for tool data extraction
                final = await stream.get_final_response()
                self._last_specialist_result[specialist_name] = final
                log.info("Specialist %s streamed response", specialist_name)
                return
            except Exception as e:
                last_error = e
                if _is_rate_limit(e) and attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2 ** attempt)
                    log.warning(
                        "Specialist %s hit 429 rate limit, retry %d/%d in %ds",
                        specialist_name, attempt + 1, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    log.error(
                        "Specialist %s stream failed: %s", specialist_name, e
                    )
                    break

        if last_error and _is_rate_limit(last_error):
            yield (
                "I'm experiencing high demand right now. "
                "Please try again in a few seconds."
            )
        else:
            yield (
                "I wasn't able to process that request. "
                f"({_friendly_error(last_error)})"
            )

    async def process_message_stream(
        self, user_msg: str
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream a user message through the multi-agent pipeline.
        Yields StreamEvent tuples that the WebSocket handler maps to
        wire-protocol messages.

        Flow:
        1. INPUT GUARDRAIL + triage in parallel
        2. Yield agent name + safety metadata
        3. Stream specialist response as text deltas
        4. OUTPUT GUARDRAIL (background, non-blocking)
        5. Store interaction for Quality Agent
        6. Yield follow-up suggestions + done
        """
        # ── Step 1+2: Input safety + triage ──
        # Run both in parallel: triage is an LLM call, safety is an API call.
        # Both take ~200-500ms, so parallelising saves significant latency.
        input_safety_task = asyncio.to_thread(check_safety, user_msg)
        triage_task = self._run_triage(user_msg)
        input_safety, specialist_name = await asyncio.gather(
            input_safety_task, triage_task
        )

        if not input_safety["safe"]:
            log.warning(
                "Input blocked by content safety: %s", input_safety["flagged"]
            )
            safety = SafetyResult(
                input_safe=False,
                output_safe=True,
                categories=input_safety["categories"],
                flagged=input_safety["flagged"],
                available=input_safety.get("available", False),
            )
            yield StreamEvent("agent", "Safety Guard")
            yield StreamEvent("safety", safety.model_dump_json())
            yield StreamEvent(
                "delta",
                "⚠️ **Content Safety Alert**\n\n"
                "Your message was flagged for potentially harmful content "
                f"({', '.join(input_safety['flagged'])}).\n\n"
                "Please rephrase your question. This system monitors for "
                "hate speech, violence, self-harm, and sexual content.",
            )
            yield StreamEvent("done")
            return

        display_name = DISPLAY_NAMES.get(specialist_name, specialist_name)
        yield StreamEvent("agent", display_name)
        yield StreamEvent(
            "safety",
            SafetyResult(
                input_safe=True,
                output_safe=True,
                categories=input_safety.get("categories", {}),
                flagged=[],
                available=input_safety.get("available", False),
            ).model_dump_json(),
        )

        # ── Step 3: Stream specialist response ──
        log.info("Triage routed to: %s", specialist_name)
        chunks: list[str] = []
        async for delta in self._run_specialist_stream(specialist_name, user_msg):
            chunks.append(delta)
            yield StreamEvent("delta", delta)

        full_response = "".join(chunks)

        # ── Step 4: Output safety (background, non-blocking) ──
        async def _bg_output_check(text: str) -> None:
            try:
                result = await asyncio.to_thread(check_safety, text)
                if not result["safe"]:
                    log.warning(
                        "Output safety flagged (background): %s",
                        result["flagged"],
                    )
            except Exception as exc:
                log.debug("Background output safety check failed: %s", exc)

        asyncio.create_task(_bg_output_check(full_response))

        # ── Step 5: Store for Quality Agent ──
        tool_calls, tool_defs = self._extract_tool_data(specialist_name)
        clean_response, suggestions = _extract_suggestions(full_response)
        update_last_interaction(
            query=user_msg,
            response=clean_response,
            agent=display_name,
            tool_calls=tool_calls,
            tool_definitions=tool_defs,
        )

        # ── Step 6: Suggestions + done ──
        if suggestions:
            yield StreamEvent("suggestions", json.dumps(suggestions))
        yield StreamEvent("done")
