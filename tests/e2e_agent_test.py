"""
End-to-end agent & tool coverage test for Ops Assistant.

Runs a multi-turn conversation through the live deployment to verify
every agent is invoked and every tool produces meaningful output.

Conversation flow:
  1. Operations — "how are we doing?" → triggers run_sql_query
  2. Operations — "what's the order mix?" → triggers run_sql_query
  3. Forecasting — "any pending mobile orders?" → triggers run_sql_query
  4. Forecasting — "what's the demand forecast?" → triggers run_sql_query
  5. Diagnostics — "is there a bottleneck?" → triggers run_sql_query
  6. Diagnostics — "move Lisa to hot_bar" → triggers move_staff_to_station
  7. Diagnostics — "move Lisa to cold_bar" (restore) → move_staff_to_station
  8. Safety — "analyze content safety of: hello" → triggers analyze_content_safety
  9. Quality — "evaluate the last response" → triggers get_last_interaction + evaluate_*
  10. Streaming — verify response arrives in multiple chunks (not one blob)

Usage:
    python tests/e2e_agent_test.py https://shiftiq.azdemohub.com
"""
import asyncio
import json
import re
import ssl
import sys
import time

import websockets


# ── Result tracker ──────────────────────────────────────────────────

class E2EResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors: list[str] = []
        self.warn_msgs: list[str] = []

    def ok(self, name: str, detail: str = ""):
        self.passed += 1
        print(f"  \u2705 {name}" + (f" \u2014 {detail}" if detail else ""))

    def fail(self, name: str, detail: str = ""):
        self.failed += 1
        self.errors.append(f"{name}: {detail}")
        print(f"  \u274c {name}" + (f" \u2014 {detail}" if detail else ""))

    def warn(self, name: str, detail: str = ""):
        self.warnings += 1
        self.warn_msgs.append(f"{name}: {detail}")
        print(f"  \u26a0\ufe0f  {name}" + (f" \u2014 {detail}" if detail else ""))

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'=' * 60}")
        print(f"  E2E Agent Coverage: {self.passed}/{total} passed", end="")
        if self.warnings:
            print(f", {self.warnings} warnings")
        else:
            print()
        if self.errors:
            print("  Failures:")
            for e in self.errors:
                print(f"    \u2022 {e}")
        if self.warn_msgs:
            print("  Warnings:")
            for w in self.warn_msgs:
                print(f"    \u2022 {w}")
        print(f"{'=' * 60}")
        return self.failed == 0


# ── WebSocket helper — single persistent connection ─────────────────

class ChatSession:
    """
    Persistent WebSocket session. Keeps the connection open across
    multiple turns so each agent maintains conversation history
    (just like the real UI).
    """

    def __init__(self, base_url: str):
        self.ws_url = (
            base_url.replace("https://", "wss://").replace("http://", "ws://")
            + "/ws"
        )
        self.ws = None
        self._ssl = None
        if self.ws_url.startswith("wss://"):
            self._ssl = ssl.create_default_context()
            self._ssl.check_hostname = False
            self._ssl.verify_mode = ssl.CERT_NONE

    async def connect(self):
        self.ws = await websockets.connect(
            self.ws_url, ssl=self._ssl, close_timeout=5
        )

    async def close(self):
        if self.ws:
            await self.ws.close()

    async def ask(
        self, question: str, timeout_secs: int = 120
    ) -> dict:
        """
        Send a message and collect the full streamed response.

        Returns {
            "agent": str,         # agent display name
            "text": str,          # full response text
            "done": bool,         # [DONE] received
            "chunks": int,        # number of text chunks (streaming)
            "safety": dict|None,  # safety metadata
            "suggestions": list,  # follow-up suggestions
        }
        """
        await self.ws.send(question)
        agent_name = ""
        response_text = ""
        done = False
        chunks = 0
        safety = None
        suggestions = []
        deadline = time.time() + timeout_secs

        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=120)
            except asyncio.TimeoutError:
                break

            if msg.startswith("[DONE]"):
                done = True
                break
            elif msg.startswith("[AGENT:"):
                agent_name = msg[7:-1]
            elif msg.startswith("[SAFETY:"):
                try:
                    safety = json.loads(msg[8:-1])
                except (json.JSONDecodeError, IndexError):
                    pass
            elif msg.startswith("[SUGGESTIONS:"):
                try:
                    suggestions = json.loads(msg[13:-1])
                except (json.JSONDecodeError, IndexError):
                    pass
            else:
                response_text += msg
                chunks += 1

        return {
            "agent": agent_name,
            "text": response_text,
            "done": done,
            "chunks": chunks,
            "safety": safety,
            "suggestions": suggestions,
        }


# ── Error-signal detection ──────────────────────────────────────────

# Phrases the agent uses when a tool (especially SQL) fails gracefully.
# If these appear in a response, the agent is masking a backend error.
ERROR_SIGNALS = [
    "unable to", "failed to", "couldn't retrieve",
    "cannot access", "database issue", "database error", "data is unavailable",
    "experiencing an issue", "currently unavailable", "no data returned",
    "error occurred", "service unavailable", "timed out",
    "access denied", "permission denied", "login failed",
]


def check_no_error_signals(text: str, test_name: str, result: E2EResult) -> bool:
    """Fail the test if the response contains graceful-error language.

    Returns True if the text is clean (no error signals found).
    """
    lower = text.lower()
    for signal in ERROR_SIGNALS:
        if signal in lower:
            result.fail(
                f"{test_name} error signal",
                f"Response contains '{signal}' — likely a backend failure: {text[:200]}",
            )
            return False
    return True


def check_has_numeric_data(text: str, test_name: str, result: E2EResult) -> bool:
    """Fail the test if the response has no numbers (digits).

    Data-driven responses always contain counts, percentages, or metrics.
    Returns True if at least one number is found.
    """
    if re.search(r'\d', text):
        return True
    result.fail(
        f"{test_name} numeric data",
        f"Response has no numbers — likely no real data: {text[:200]}",
    )
    return False


# ── Test definitions ────────────────────────────────────────────────

async def test_operations_status(
    session: ChatSession, result: E2EResult
) -> dict:
    """Turn 1: Operations agent — store status overview."""
    print("\n  [1/9] Operations Agent — store status")
    resp = await session.ask("how are we doing?")

    if not resp["done"]:
        result.fail("OPS status done", "No [DONE] received")
        return resp
    if "Operations Agent" not in resp["agent"]:
        result.fail("OPS status routing", f"Routed to {resp['agent']}, expected Operations Agent")
        return resp
    result.ok("OPS status routing", f"→ {resp['agent']}")

    text = resp["text"].lower()

    # Gate: fail fast if the agent is masking a backend error
    if not check_no_error_signals(resp["text"], "OPS status", result):
        return resp
    check_has_numeric_data(resp["text"], "OPS status", result)

    # Should mention status, pace, orders, or station data
    has_data = any(
        kw in text
        for kw in ["pace", "order", "status", "station", "wait", "target", "capacity", "staff"]
    )
    if has_data:
        result.ok("OPS status content", f"{len(resp['text'])} chars, has metrics")
    else:
        result.fail("OPS status content", f"No operational data in response: {resp['text'][:200]}")

    return resp


async def test_operations_order_mix(
    session: ChatSession, result: E2EResult
) -> dict:
    """Turn 2: Operations agent — order mix breakdown."""
    print("\n  [2/9] Operations Agent — order mix")
    resp = await session.ask("what's the current order mix?")

    if not resp["done"]:
        result.fail("OPS order mix done", "No [DONE] received")
        return resp
    if "Operations Agent" not in resp["agent"]:
        result.fail("OPS order mix routing", f"Routed to {resp['agent']}")
        return resp
    result.ok("OPS order mix routing", f"→ {resp['agent']}")

    text = resp["text"].lower()

    if not check_no_error_signals(resp["text"], "OPS order mix", result):
        return resp
    check_has_numeric_data(resp["text"], "OPS order mix", result)

    has_data = any(
        kw in text for kw in ["hot", "cold", "food", "mobile", "in-store", "in_store", "%", "percent"]
    )
    if has_data:
        result.ok("OPS order mix content", f"{len(resp['text'])} chars, has mix data")
    else:
        result.fail("OPS order mix content", f"No mix data: {resp['text'][:200]}")

    return resp


async def test_forecasting_mobile(
    session: ChatSession, result: E2EResult
) -> dict:
    """Turn 3: Forecasting agent — mobile order pipeline."""
    print("\n  [3/9] Forecasting Agent — mobile orders")
    resp = await session.ask("any pending mobile orders coming in?")

    if not resp["done"]:
        result.fail("FCST mobile done", "No [DONE] received")
        return resp
    if "Forecasting Agent" not in resp["agent"]:
        result.fail("FCST mobile routing", f"Routed to {resp['agent']}")
        return resp
    result.ok("FCST mobile routing", f"→ {resp['agent']}")

    text = resp["text"].lower()

    if not check_no_error_signals(resp["text"], "FCST mobile", result):
        return resp
    check_has_numeric_data(resp["text"], "FCST mobile", result)

    has_data = any(
        kw in text for kw in ["mobile", "pending", "order", "queue", "scheduled", "cold", "hot"]
    )
    if has_data:
        result.ok("FCST mobile content", f"{len(resp['text'])} chars, has pipeline data")
    else:
        result.fail("FCST mobile content", f"No forecast data: {resp['text'][:200]}")

    return resp


async def test_forecasting_demand(
    session: ChatSession, result: E2EResult
) -> dict:
    """Turn 4: Forecasting agent — demand forecast."""
    print("\n  [4/9] Forecasting Agent — demand forecast")
    resp = await session.ask("what's the demand forecast for the next 30 minutes?")

    if not resp["done"]:
        result.fail("FCST demand done", "No [DONE] received")
        return resp
    if "Forecasting Agent" not in resp["agent"]:
        result.fail("FCST demand routing", f"Routed to {resp['agent']}")
        return resp
    result.ok("FCST demand routing", f"→ {resp['agent']}")

    text = resp["text"].lower()

    if not check_no_error_signals(resp["text"], "FCST demand", result):
        return resp
    check_has_numeric_data(resp["text"], "FCST demand", result)

    has_data = any(
        kw in text for kw in ["forecast", "demand", "order", "expect", "predict", "surge", "minute"]
    )
    if has_data:
        result.ok("FCST demand content", f"{len(resp['text'])} chars, has forecast")
    else:
        result.fail("FCST demand content", f"No forecast data: {resp['text'][:200]}")

    return resp


async def test_diagnostics_bottleneck(
    session: ChatSession, result: E2EResult
) -> dict:
    """Turn 5: Diagnostics agent — bottleneck detection."""
    print("\n  [5/9] Diagnostics Agent — bottleneck detection")
    resp = await session.ask("is there a bottleneck at any station?")

    if not resp["done"]:
        result.fail("DIAG bottleneck done", "No [DONE] received")
        return resp
    if "Diagnostics Agent" not in resp["agent"]:
        result.fail("DIAG bottleneck routing", f"Routed to {resp['agent']}")
        return resp
    result.ok("DIAG bottleneck routing", f"→ {resp['agent']}")

    text = resp["text"].lower()

    if not check_no_error_signals(resp["text"], "DIAG bottleneck", result):
        return resp
    check_has_numeric_data(resp["text"], "DIAG bottleneck", result)

    has_data = any(
        kw in text
        for kw in ["bottleneck", "capacity", "station", "cold_bar", "hot_bar", "overload", "staff", "wait"]
    )
    if has_data:
        result.ok("DIAG bottleneck content", f"{len(resp['text'])} chars, has diagnosis")
    else:
        result.fail("DIAG bottleneck content", f"No diagnosis data: {resp['text'][:200]}")

    return resp


async def test_diagnostics_staff_move(
    session: ChatSession, result: E2EResult
) -> dict:
    """Turn 6+7: Diagnostics agent — staff move + restore."""
    print("\n  [6/9] Diagnostics Agent — staff move (Lisa → hot_bar)")
    move_resp = await session.ask("move Lisa to hot_bar")

    if not move_resp["done"]:
        result.fail("DIAG move done", "No [DONE] received")
        return move_resp
    if "Diagnostics Agent" not in move_resp["agent"]:
        result.fail("DIAG move routing", f"Routed to {move_resp['agent']}")
        return move_resp
    result.ok("DIAG move routing", f"→ {move_resp['agent']}")

    text = move_resp["text"].lower()

    if not check_no_error_signals(move_resp["text"], "DIAG move", result):
        return move_resp

    has_confirmation = any(
        kw in text for kw in ["moved", "reassigned", "transferred", "lisa", "hot_bar", "hot bar"]
    )
    if has_confirmation:
        result.ok("DIAG move confirmation", f"Staff move confirmed")
    else:
        result.fail("DIAG move confirmation", f"No confirmation: {move_resp['text'][:200]}")

    # Restore — move Lisa back to cold_bar
    print("\n  [7/9] Diagnostics Agent — staff restore (Lisa → cold_bar)")
    restore_resp = await session.ask("move Lisa to cold_bar")

    if not restore_resp["done"]:
        result.fail("DIAG restore done", "No [DONE] received")
        return restore_resp

    restore_text = restore_resp["text"].lower()
    check_no_error_signals(restore_resp["text"], "DIAG restore", result)

    if any(kw in restore_text for kw in ["moved", "reassigned", "transferred", "lisa", "cold_bar", "cold bar"]):
        result.ok("DIAG restore confirmation", "Staff restored to cold_bar")
    else:
        result.warn("DIAG restore confirmation", f"Unconfirmed: {restore_resp['text'][:200]}")

    return move_resp


async def test_safety_agent(
    session: ChatSession, result: E2EResult
) -> dict:
    """Turn 8: Safety agent — content safety analysis."""
    print("\n  [8/9] Safety Agent — content analysis")
    resp = await session.ask(
        "Can you analyze the content safety of this text: "
        "'Our store had a great day and customers were happy'",
        timeout_secs=180,
    )

    if not resp["done"]:
        result.fail("SAFETY done", "No [DONE] received")
        return resp
    if "Safety Agent" not in resp["agent"]:
        # Safety might also be handled by Safety Guard (input guardrail)
        if resp["agent"] != "Safety Guard":
            result.fail("SAFETY routing", f"Routed to {resp['agent']}")
            return resp
    result.ok("SAFETY routing", f"→ {resp['agent']}")

    text = resp["text"].lower()
    has_analysis = any(
        kw in text
        for kw in ["safe", "no harmful", "content safety", "categories", "hate", "violence", "severity", "flagged", "clean"]
    )
    if has_analysis:
        result.ok("SAFETY content", f"{len(resp['text'])} chars, has safety analysis")
    else:
        result.fail("SAFETY content", f"No safety analysis: {resp['text'][:200]}")

    return resp


async def test_quality_agent(
    session: ChatSession, result: E2EResult
) -> dict:
    """Turn 9: Quality agent — evaluate previous response."""
    print("\n  [9/9] Quality Agent — response evaluation")
    resp = await session.ask(
        "evaluate the quality and accuracy of the previous response I just received",
        timeout_secs=180,
    )

    if not resp["done"]:
        result.fail("QUALITY done", "No [DONE] received")
        return resp
    if "Quality Agent" not in resp["agent"]:
        result.fail("QUALITY routing", f"Routed to {resp['agent']}")
        return resp
    result.ok("QUALITY routing", f"→ {resp['agent']}")

    text = resp["text"].lower()
    has_eval = any(
        kw in text
        for kw in ["coherence", "fluency", "relevance", "groundedness", "score", "evaluation", "quality", "/5", "out of"]
    )
    if has_eval:
        result.ok("QUALITY eval content", f"{len(resp['text'])} chars, has quality scores")
    else:
        result.fail("QUALITY eval content", f"No eval data: {resp['text'][:200]}")

    return resp


async def test_streaming_chunks(
    session: ChatSession, result: E2EResult, first_resp: dict
):
    """Verify responses arrive as multiple streamed chunks (not one blob)."""
    print("\n  [Streaming] Token-level streaming verification")

    if first_resp["chunks"] > 1:
        result.ok(
            "Real streaming",
            f"Response arrived in {first_resp['chunks']} chunks (token-level)",
        )
    elif first_resp["chunks"] == 1:
        result.warn(
            "Single chunk",
            "Response arrived as 1 chunk — streaming may not be working",
        )
    else:
        result.fail("No chunks", "No text chunks received")

    if first_resp.get("safety") is not None:
        result.ok("Safety metadata", "Received safety JSON in stream")
    else:
        result.warn("Safety metadata", "No safety metadata received")


async def test_suggestions(result: E2EResult, all_responses: list[dict]):
    """Verify at least one response included follow-up suggestions."""
    print("\n  [Suggestions] Follow-up suggestion verification")

    any_suggestions = any(r.get("suggestions") for r in all_responses)
    if any_suggestions:
        for r in all_responses:
            if r.get("suggestions"):
                result.ok(
                    "Follow-up suggestions",
                    f"Agent '{r['agent']}' returned {len(r['suggestions'])} suggestions",
                )
                break
    else:
        result.warn(
            "No suggestions",
            "None of the responses included follow-up suggestions",
        )


# ── Main ────────────────────────────────────────────────────────────

AGENTS_EXPECTED = {
    "Operations Agent",
    "Diagnostics Agent",
    "Forecasting Agent",
    "Safety Agent",
    "Quality Agent",
}


async def main(base_url: str):
    print(f"\n{'=' * 60}")
    print(f"  E2E Agent Coverage Test")
    print(f"  {base_url}")
    print(f"{'=' * 60}")

    result = E2EResult()
    session = ChatSession(base_url)
    all_responses: list[dict] = []

    try:
        await session.connect()
        result.ok("WebSocket connect", session.ws_url)
    except Exception as e:
        result.fail("WebSocket connect", str(e))
        result.summary()
        sys.exit(1)

    try:
        # Run all agent tests sequentially (multi-turn conversation)
        r1 = await test_operations_status(session, result)
        all_responses.append(r1)

        r2 = await test_operations_order_mix(session, result)
        all_responses.append(r2)

        r3 = await test_forecasting_mobile(session, result)
        all_responses.append(r3)

        r4 = await test_forecasting_demand(session, result)
        all_responses.append(r4)

        r5 = await test_diagnostics_bottleneck(session, result)
        all_responses.append(r5)

        r6 = await test_diagnostics_staff_move(session, result)
        all_responses.append(r6)

        r7 = await test_safety_agent(session, result)
        all_responses.append(r7)

        r8 = await test_quality_agent(session, result)
        all_responses.append(r8)

        # Cross-cutting checks
        await test_streaming_chunks(session, result, r1)
        await test_suggestions(result, all_responses)

        # Agent coverage summary
        print("\n  [Coverage] Agent invocation summary")
        agents_hit = {r["agent"] for r in all_responses if r.get("agent")}
        for expected in sorted(AGENTS_EXPECTED):
            if expected in agents_hit:
                result.ok(f"Agent invoked: {expected}")
            else:
                result.fail(f"Agent NOT invoked: {expected}")

    except Exception as e:
        result.fail("Unexpected error", str(e))
    finally:
        await session.close()

    ok = result.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/e2e_agent_test.py <BASE_URL>")
        print("  e.g. python tests/e2e_agent_test.py https://shiftiq.azdemohub.com")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
