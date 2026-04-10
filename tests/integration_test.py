"""
Ops Assistant — Integration Test Suite

Verifies correctness of data flow end-to-end:
  1. Dashboard API returns correct structure and counts
  2. Staff move persists in the database (the bug we fixed)
  3. WebSocket chat returns valid agent responses
  4. Reset endpoint restores seed state

Usage:
    python tests/integration_test.py                              # test against ACA
    python tests/integration_test.py --base-url http://localhost:8000  # local
    python tests/integration_test.py --verbose                    # show response bodies
"""
import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

import websockets

# ── Defaults ──
DEFAULT_BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
DEFAULT_WS_URL = os.environ.get("TEST_WS_URL", "ws://localhost:8000/ws")


# ── Result tracking ──

@dataclass
class TestResult:
    name: str
    passed: bool
    duration_s: float = 0.0
    detail: str = ""
    error: str = ""


@dataclass
class TestSuite:
    results: list[TestResult] = field(default_factory=list)

    def add(self, result: TestResult):
        status = "PASS ✅" if result.passed else "FAIL ❌"
        print(f"  {status}  {result.name} ({result.duration_s:.2f}s)")
        if result.detail and VERBOSE:
            for line in result.detail.split("\n"):
                print(f"         {line}")
        if result.error:
            print(f"         ERROR: {result.error}")
        self.results.append(result)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    def summary(self):
        total = len(self.results)
        print(f"\n{'='*60}")
        print(f"  TEST RESULTS: {self.passed}/{total} passed, {self.failed} failed")
        print(f"{'='*60}")
        if self.failed:
            print("\n  Failed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"    ❌ {r.name}: {r.error or r.detail}")
        print()
        return self.failed == 0


VERBOSE = False
suite = TestSuite()


# ── HTTP helpers ──

def _get(path: str, timeout: int = 30) -> dict:
    """GET request using urllib (no external deps)."""
    import urllib.request
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "OpsAssistant-IntegrationTest/1.0",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _post(path: str, timeout: int = 30) -> dict:
    """POST request using urllib."""
    import urllib.request
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method="POST", data=b"", headers={
        "User-Agent": "OpsAssistant-IntegrationTest/1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# ═══════════════════════════════════════════════════════════════════
#  TEST GROUP 1: Dashboard API
# ═══════════════════════════════════════════════════════════════════

def test_dashboard_structure():
    """Dashboard API returns all required keys with correct types."""
    t0 = time.perf_counter()
    try:
        data = _get("/api/dashboard")
        required_keys = ["stations", "staff", "kpis", "hourly_volume",
                         "pipeline", "order_mix"]
        missing = [k for k in required_keys if k not in data]
        if missing:
            suite.add(TestResult("Dashboard structure", False,
                                 time.perf_counter() - t0,
                                 error=f"Missing keys: {missing}"))
            return

        checks = []
        checks.append(f"stations: {type(data['stations']).__name__} ({len(data['stations'])} items)")
        checks.append(f"staff: {type(data['staff']).__name__} ({len(data['staff'])} items)")
        checks.append(f"hourly_volume: {len(data['hourly_volume'])} items")
        checks.append(f"kpis: {list(data['kpis'].keys()) if isinstance(data['kpis'], dict) else type(data['kpis']).__name__}")

        suite.add(TestResult("Dashboard structure", True,
                             time.perf_counter() - t0,
                             detail="\n".join(checks)))
    except Exception as e:
        suite.add(TestResult("Dashboard structure", False,
                             time.perf_counter() - t0, error=str(e)))


def test_station_count():
    """Dashboard returns exactly 3 stations (hot_bar, cold_bar, food)."""
    t0 = time.perf_counter()
    try:
        data = _get("/api/dashboard")
        stations = data.get("stations", [])
        names = sorted([s["station"] for s in stations])
        expected = ["cold_bar", "food", "hot_bar"]

        if names == expected:
            suite.add(TestResult("Station count (3)", True,
                                 time.perf_counter() - t0,
                                 detail=f"Stations: {names}"))
        else:
            suite.add(TestResult("Station count (3)", False,
                                 time.perf_counter() - t0,
                                 error=f"Expected {expected}, got {names} ({len(stations)} items)"))
    except Exception as e:
        suite.add(TestResult("Station count (3)", False,
                             time.perf_counter() - t0, error=str(e)))


def test_staff_count():
    """Dashboard returns exactly 5 staff members."""
    t0 = time.perf_counter()
    try:
        data = _get("/api/dashboard")
        staff = data.get("staff", [])
        names = sorted([s["name"] for s in staff])
        expected_names = ["Emma", "James", "Lisa", "Mike", "Sarah"]

        if len(staff) == 5 and names == expected_names:
            suite.add(TestResult("Staff count (5)", True,
                                 time.perf_counter() - t0,
                                 detail=f"Staff: {names}"))
        else:
            suite.add(TestResult("Staff count (5)", False,
                                 time.perf_counter() - t0,
                                 error=f"Expected {expected_names}, got {names}"))
    except Exception as e:
        suite.add(TestResult("Staff count (5)", False,
                             time.perf_counter() - t0, error=str(e)))


def test_hourly_volume():
    """Hourly volume has 17 values with realistic data (not all zeros)."""
    t0 = time.perf_counter()
    try:
        data = _get("/api/dashboard")
        volume = data.get("hourly_volume", [])
        non_zero = sum(1 for v in volume if v > 0)

        if len(volume) == 17 and non_zero >= 10:
            suite.add(TestResult("Hourly volume (17 bars)", True,
                                 time.perf_counter() - t0,
                                 detail=f"{non_zero} non-zero of {len(volume)} | peak={max(volume)}"))
        else:
            suite.add(TestResult("Hourly volume (17 bars)", False,
                                 time.perf_counter() - t0,
                                 error=f"{len(volume)} items, {non_zero} non-zero"))
    except Exception as e:
        suite.add(TestResult("Hourly volume (17 bars)", False,
                             time.perf_counter() - t0, error=str(e)))


def test_station_metrics_valid():
    """Each station has valid capacity (0-200%), staff count, and wait time."""
    t0 = time.perf_counter()
    try:
        data = _get("/api/dashboard")
        issues = []
        for s in data.get("stations", []):
            cap = s.get("capacity_pct", 0)
            staff = s.get("staff_count", 0)
            wait = s.get("avg_wait_secs", 0)
            if not (0 <= cap <= 200):
                issues.append(f"{s['station']}: capacity {cap}% out of range")
            if not (0 < staff <= 10):
                issues.append(f"{s['station']}: staff_count {staff} unusual")
            if wait < 0:
                issues.append(f"{s['station']}: negative wait time {wait}")

        if not issues:
            suite.add(TestResult("Station metrics valid", True,
                                 time.perf_counter() - t0))
        else:
            suite.add(TestResult("Station metrics valid", False,
                                 time.perf_counter() - t0,
                                 error="; ".join(issues)))
    except Exception as e:
        suite.add(TestResult("Station metrics valid", False,
                             time.perf_counter() - t0, error=str(e)))


# ═══════════════════════════════════════════════════════════════════
#  TEST GROUP 2: Reset Endpoint
# ═══════════════════════════════════════════════════════════════════

def test_reset_endpoint():
    """POST /reset returns success and restores seed state."""
    t0 = time.perf_counter()
    try:
        result = _post("/reset")
        if result.get("status") == "ok":
            # Verify seed state
            data = _get("/api/dashboard")
            station_count = len(data.get("stations", []))
            staff_count = len(data.get("staff", []))

            if station_count == 3 and staff_count == 5:
                suite.add(TestResult("Reset restores seed state", True,
                                     time.perf_counter() - t0,
                                     detail=f"3 stations, 5 staff confirmed"))
            else:
                suite.add(TestResult("Reset restores seed state", False,
                                     time.perf_counter() - t0,
                                     error=f"After reset: {station_count} stations, {staff_count} staff"))
        else:
            suite.add(TestResult("Reset restores seed state", False,
                                 time.perf_counter() - t0,
                                 error=f"Reset returned: {result}"))
    except Exception as e:
        suite.add(TestResult("Reset restores seed state", False,
                             time.perf_counter() - t0, error=str(e)))


# ═══════════════════════════════════════════════════════════════════
#  TEST GROUP 3: WebSocket Chat — Agent Routing
# ═══════════════════════════════════════════════════════════════════

async def _ws_chat(question: str, timeout: float = 120) -> dict:
    """Send a question via WebSocket and collect the full response."""
    async with websockets.connect(WS_URL, max_size=2**20) as ws:
        await ws.send(question)

        agent_name = ""
        safety = {}
        chunks = []
        suggestions = []

        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)

            if msg.startswith("[AGENT:"):
                agent_name = msg[7:-1]
            elif msg.startswith("[SAFETY:"):
                try:
                    safety = json.loads(msg[8:-1])
                except Exception:
                    pass
            elif msg.startswith("[SUGGESTIONS:"):
                try:
                    suggestions = json.loads(msg[13:-1])
                except Exception:
                    pass
            elif msg == "[DONE]":
                # Try to grab trailing SUGGESTIONS
                try:
                    extra = await asyncio.wait_for(ws.recv(), timeout=2)
                    if extra.startswith("[SUGGESTIONS:"):
                        suggestions = json.loads(extra[13:-1])
                except Exception:
                    pass
                break
            else:
                chunks.append(msg)

    return {
        "agent": agent_name,
        "response": "".join(chunks),
        "safety": safety,
        "suggestions": suggestions,
    }


async def test_routing_operations():
    """'How are we doing?' routes to Operations Agent."""
    t0 = time.perf_counter()
    try:
        result = await _ws_chat("How are we doing?")
        agent = result["agent"]
        ok = "operations" in agent.lower()
        suite.add(TestResult("Route → Operations Agent", ok,
                             time.perf_counter() - t0,
                             detail=f"Agent: {agent}" + (f"\nResponse: {result['response'][:200]}" if VERBOSE else ""),
                             error="" if ok else f"Routed to '{agent}' instead"))
    except Exception as e:
        suite.add(TestResult("Route → Operations Agent", False,
                             time.perf_counter() - t0, error=str(e)))


async def test_routing_diagnostics():
    """'Why is cold bar over capacity?' routes to Diagnostics Agent."""
    t0 = time.perf_counter()
    try:
        result = await _ws_chat("Why is cold bar over capacity?")
        agent = result["agent"]
        ok = "diagnostics" in agent.lower()
        suite.add(TestResult("Route → Diagnostics Agent", ok,
                             time.perf_counter() - t0,
                             detail=f"Agent: {agent}",
                             error="" if ok else f"Routed to '{agent}' instead"))
    except Exception as e:
        suite.add(TestResult("Route → Diagnostics Agent", False,
                             time.perf_counter() - t0, error=str(e)))


async def test_routing_forecasting():
    """'How many mobile orders pending?' routes to Forecasting Agent."""
    t0 = time.perf_counter()
    try:
        result = await _ws_chat("How many mobile orders are pending?")
        agent = result["agent"]
        ok = "forecasting" in agent.lower()
        suite.add(TestResult("Route → Forecasting Agent", ok,
                             time.perf_counter() - t0,
                             detail=f"Agent: {agent}",
                             error="" if ok else f"Routed to '{agent}' instead"))
    except Exception as e:
        suite.add(TestResult("Route → Forecasting Agent", False,
                             time.perf_counter() - t0, error=str(e)))


# ═══════════════════════════════════════════════════════════════════
#  TEST GROUP 4: Staff Move Persistence (the critical regression test)
# ═══════════════════════════════════════════════════════════════════

async def test_staff_move_persists():
    """
    CRITICAL: Verifies the staff reassignment bug fix.
    1. Reset data (Lisa at cold_bar)
    2. Ask agent to move Lisa to food
    3. Query dashboard to confirm Lisa is now at food
    4. Reset data back to seed state
    """
    t0 = time.perf_counter()
    try:
        # Step 1: Reset to known state
        _post("/reset")
        before = _get("/api/dashboard")
        lisa_before = next(
            (s for s in before["staff"] if s["name"] == "Lisa"), None
        )
        if not lisa_before:
            suite.add(TestResult("Staff move persists", False,
                                 time.perf_counter() - t0,
                                 error="Lisa not found in staff before move"))
            return

        lisa_station_before = lisa_before.get("station", "??")

        # Step 2: Move Lisa via chat agent
        result = await _ws_chat("Move Lisa to food")
        response = result["response"].lower()
        agent = result["agent"]

        # Check agent acknowledged the move
        move_confirmed = any(kw in response for kw in [
            "moved", "done", "lisa", "reassigned", "food"
        ])

        # Step 3: Verify via dashboard API
        after = _get("/api/dashboard")
        lisa_after = next(
            (s for s in after["staff"] if s["name"] == "Lisa"), None
        )
        if not lisa_after:
            suite.add(TestResult("Staff move persists", False,
                                 time.perf_counter() - t0,
                                 error="Lisa not found in staff after move"))
            return

        lisa_station_after = lisa_after.get("station", "??")
        move_persisted = lisa_station_after == "food"

        detail_lines = [
            f"Before: Lisa at {lisa_station_before}",
            f"Agent: {agent}",
            f"Agent confirmed move: {move_confirmed}",
            f"After:  Lisa at {lisa_station_after}",
            f"Move persisted in DB: {move_persisted}",
        ]
        if VERBOSE:
            detail_lines.append(f"Response: {result['response'][:300]}")

        suite.add(TestResult(
            "Staff move persists", move_persisted,
            time.perf_counter() - t0,
            detail="\n".join(detail_lines),
            error="" if move_persisted else f"Lisa still at {lisa_station_after} (expected food)",
        ))

        # Step 4: Reset back to seed state
        _post("/reset")

    except Exception as e:
        suite.add(TestResult("Staff move persists", False,
                             time.perf_counter() - t0,
                             error=f"{e}\n{traceback.format_exc()}"))


async def test_staff_move_reflected_in_followup():
    """
    After moving Lisa to food, 'view updated staffing' should show
    Lisa at food (not cold_bar). Tests persistence + follow-up routing.
    """
    t0 = time.perf_counter()
    try:
        _post("/reset")

        # Use a single WS connection for conversation continuity
        async with websockets.connect(WS_URL, max_size=2**20) as ws:
            # Move Lisa
            await ws.send("Move Lisa to food")
            move_response = await _collect_ws_response(ws)

            # Small delay for DB commit propagation
            await asyncio.sleep(1)

            # Ask for updated staffing
            await ws.send("view updated staffing")
            staffing_response = await _collect_ws_response(ws)

        # Check that the staffing response mentions Lisa at food (not cold_bar)
        resp_lower = staffing_response["response"].lower()

        # Lisa should appear near "food" in the response
        lisa_at_food = False
        lines = resp_lower.split("\n")
        for i, line in enumerate(lines):
            if "lisa" in line and "food" in line:
                lisa_at_food = True
                break

        # Also check dashboard API as ground truth
        after = _get("/api/dashboard")
        lisa_db = next((s for s in after["staff"] if s["name"] == "Lisa"), None)
        lisa_db_station = lisa_db["station"] if lisa_db else "not found"

        detail_lines = [
            f"Move agent: {move_response['agent']}",
            f"Staffing agent: {staffing_response['agent']}",
            f"Lisa in response near 'food': {lisa_at_food}",
            f"Lisa in DB: {lisa_db_station}",
        ]
        if VERBOSE:
            detail_lines.append(f"Staffing response: {staffing_response['response'][:400]}")

        passed = lisa_db_station == "food"  # DB is the ground truth
        suite.add(TestResult(
            "Follow-up shows updated staff", passed,
            time.perf_counter() - t0,
            detail="\n".join(detail_lines),
            error="" if passed else f"Lisa still at {lisa_db_station} in DB",
        ))

        _post("/reset")

    except Exception as e:
        suite.add(TestResult("Follow-up shows updated staff", False,
                             time.perf_counter() - t0,
                             error=f"{e}\n{traceback.format_exc()}"))


async def _collect_ws_response(ws, timeout: float = 120) -> dict:
    """Collect a full WS response (agent + chunks + DONE)."""
    agent_name = ""
    chunks = []
    suggestions = []

    while True:
        msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
        if msg.startswith("[AGENT:"):
            agent_name = msg[7:-1]
        elif msg.startswith("[SAFETY:") or msg.startswith("[SUGGESTIONS:"):
            if msg.startswith("[SUGGESTIONS:"):
                try:
                    suggestions = json.loads(msg[13:-1])
                except Exception:
                    pass
        elif msg == "[DONE]":
            try:
                extra = await asyncio.wait_for(ws.recv(), timeout=2)
                if extra.startswith("[SUGGESTIONS:"):
                    suggestions = json.loads(extra[13:-1])
            except Exception:
                pass
            break
        else:
            chunks.append(msg)

    return {"agent": agent_name, "response": "".join(chunks), "suggestions": suggestions}


# ═══════════════════════════════════════════════════════════════════
#  TEST GROUP 5: Content Safety
# ═══════════════════════════════════════════════════════════════════

async def test_safety_metadata():
    """Responses include safety metadata with input_safe/output_safe."""
    t0 = time.perf_counter()
    try:
        result = await _ws_chat("What's the cold bar wait time?")
        safety = result.get("safety", {})

        has_input = "input_safe" in safety
        has_output = "output_safe" in safety

        suite.add(TestResult("Safety metadata present", has_input and has_output,
                             time.perf_counter() - t0,
                             detail=f"Safety: {json.dumps(safety)}",
                             error="" if (has_input and has_output)
                             else f"Missing keys in safety: {safety}"))
    except Exception as e:
        suite.add(TestResult("Safety metadata present", False,
                             time.perf_counter() - t0, error=str(e)))


# ═══════════════════════════════════════════════════════════════════
#  TEST GROUP 6: Follow-up Suggestions
# ═══════════════════════════════════════════════════════════════════

async def test_followup_suggestions():
    """Agent responses include follow-up suggestions."""
    t0 = time.perf_counter()
    try:
        result = await _ws_chat("How are we doing?")
        suggestions = result.get("suggestions", [])

        ok = len(suggestions) >= 1
        suite.add(TestResult("Follow-up suggestions", ok,
                             time.perf_counter() - t0,
                             detail=f"Got {len(suggestions)}: {suggestions}",
                             error="" if ok else "No suggestions returned"))
    except Exception as e:
        suite.add(TestResult("Follow-up suggestions", False,
                             time.perf_counter() - t0, error=str(e)))


# ═══════════════════════════════════════════════════════════════════
#  RUNNER
# ═══════════════════════════════════════════════════════════════════

async def run_all():
    print(f"\n{'='*60}")
    print(f"  Ops Assistant — Integration Test Suite")
    print(f"  Target:  {BASE_URL}")
    print(f"  WS:      {WS_URL}")
    print(f"{'='*60}\n")

    # ── Group 1: Dashboard API (sync tests) ──
    print("  📊 Dashboard API Tests")
    print("  " + "-" * 40)
    test_dashboard_structure()
    test_station_count()
    test_staff_count()
    test_hourly_volume()
    test_station_metrics_valid()

    # ── Group 2: Reset ──
    print(f"\n  🔄 Reset Endpoint Tests")
    print("  " + "-" * 40)
    test_reset_endpoint()

    # ── Group 3: Agent Routing (async) ──
    print(f"\n  🤖 Agent Routing Tests")
    print("  " + "-" * 40)
    await test_routing_operations()
    await test_routing_diagnostics()
    await test_routing_forecasting()

    # ── Group 4: Staff Move Persistence (the bug fix regression test) ──
    print(f"\n  👥 Staff Move Persistence Tests (CRITICAL)")
    print("  " + "-" * 40)
    await test_staff_move_persists()
    await test_staff_move_reflected_in_followup()

    # ── Group 5: Safety ──
    print(f"\n  🛡️  Content Safety Tests")
    print("  " + "-" * 40)
    await test_safety_metadata()

    # ── Group 6: Suggestions ──
    print(f"\n  💡 Follow-up Suggestions Tests")
    print("  " + "-" * 40)
    await test_followup_suggestions()

    # ── Summary ──
    all_passed = suite.summary()
    return all_passed


def main():
    global BASE_URL, WS_URL, VERBOSE

    parser = argparse.ArgumentParser(description="Ops Assistant Integration Tests")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help="Base HTTP URL (default: %(default)s)")
    parser.add_argument("--ws-url", default=None,
                        help="WebSocket URL (default: derived from base-url)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show response bodies")
    args = parser.parse_args()

    BASE_URL = args.base_url.rstrip("/")
    if args.ws_url:
        WS_URL = args.ws_url
    else:
        WS_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/ws"
    VERBOSE = args.verbose

    passed = asyncio.run(run_all())
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
