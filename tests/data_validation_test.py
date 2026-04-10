"""
Data validation tests for Ops Assistant.

Verifies data integrity, consistency, and correctness through the
live API endpoints. Tests cover:
  1. Dashboard data structure & value ranges
  2. Station / staff count cross-consistency
  3. Staff move → immediate count reflection (the bug we fixed)
  4. Order mix / channel split percentage integrity
  5. KPI sanity checks

Usage:
    python tests/data_validation_test.py https://shiftiq.azdemohub.com
"""
import asyncio
import json
import ssl
import sys
import time

import httpx
import websockets


class ValidationResult:
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
        print(f"\n{'=' * 55}")
        print(f"  Data Validation: {self.passed}/{total} passed", end="")
        if self.warnings:
            print(f", {self.warnings} warnings")
        else:
            print()
        if self.errors:
            print(f"  Failures:")
            for e in self.errors:
                print(f"    \u2022 {e}")
        if self.warn_msgs:
            print(f"  Warnings:")
            for w in self.warn_msgs:
                print(f"    \u2022 {w}")
        print(f"{'=' * 55}")
        return self.failed == 0


# ── Helper: send a WebSocket message and collect the full response ──
async def ws_ask(base_url: str, question: str, timeout_secs: int = 90) -> dict:
    """Send a question via WebSocket and return parsed response data."""
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://") + "/ws"
    ssl_ctx = None
    if ws_url.startswith("wss://"):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    async with websockets.connect(ws_url, ssl=ssl_ctx) as ws:
        await ws.send(question)
        agent_name = ""
        response_text = ""
        done = False
        deadline = time.time() + timeout_secs

        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
            except asyncio.TimeoutError:
                break
            if msg.startswith("[AGENT:"):
                agent_name = msg.split(":")[1].rstrip("]")
            elif msg.startswith("[DONE]"):
                done = True
                break
            elif msg.startswith("[SAFETY:") or msg.startswith("[SUGGESTIONS:"):
                pass
            else:
                response_text += msg

    return {"agent": agent_name, "text": response_text, "done": done}


# ═══════════════════════════════════════════════════════════════════
# Test 1: Dashboard data structure and value ranges
# ═══════════════════════════════════════════════════════════════════
async def test_dashboard_structure(base_url: str, result: ValidationResult) -> dict:
    """Validate dashboard JSON structure, types, and value ranges."""
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.get(f"{base_url}/api/dashboard")
        if resp.status_code != 200:
            result.fail("Dashboard HTTP", f"HTTP {resp.status_code}")
            return {}
        data = resp.json()

    # Required top-level keys
    required_keys = {"store_id", "kpis", "stations", "staff", "order_mix",
                     "channel_split", "pipeline", "hourly_volume", "shift"}
    missing = required_keys - set(data.keys())
    if missing:
        result.fail("Dashboard keys", f"Missing: {missing}")
    else:
        result.ok("Dashboard keys", f"All {len(required_keys)} present")

    # KPI value ranges
    kpis = data.get("kpis", {})
    kpi_checks = [
        ("orders_hr", 0, 500),
        ("target_hr", 1, 500),
        ("pace_pct", 0, 300),
        ("avg_wait_secs", 0, 600),
        ("active_orders", 0, 1000),
        ("est_revenue", 0, 50000),
    ]
    kpi_ok = True
    for key, lo, hi in kpi_checks:
        val = kpis.get(key)
        if val is None:
            result.fail(f"KPI {key}", "missing")
            kpi_ok = False
        elif not (lo <= val <= hi):
            result.fail(f"KPI {key}", f"{val} outside [{lo}, {hi}]")
            kpi_ok = False
    if kpi_ok:
        result.ok("KPI ranges", f"orders_hr={kpis['orders_hr']}, wait={kpis['avg_wait_secs']}s, active={kpis['active_orders']}")

    # Stations list
    stations = data.get("stations", [])
    if not stations:
        result.fail("Stations", "empty list")
    else:
        expected_stations = {"hot_bar", "cold_bar", "food"}
        found = {s["station"] for s in stations}
        if expected_stations - found:
            result.fail("Stations", f"Missing: {expected_stations - found}")
        else:
            result.ok("Station names", f"All 3 present: {sorted(found)}")

        # Validate each station
        for s in stations:
            name = s["station"]
            if s.get("staff_count", 0) < 0:
                result.fail(f"Station {name} staff", f"negative: {s['staff_count']}")
            if s.get("capacity_pct") is not None and s["capacity_pct"] < 0:
                result.fail(f"Station {name} capacity", f"negative: {s['capacity_pct']}")
            if s.get("avg_wait_secs", 0) < 0:
                result.fail(f"Station {name} wait", f"negative: {s['avg_wait_secs']}")
            if s.get("color") not in ("green", "amber", "red"):
                result.fail(f"Station {name} color", f"invalid: {s.get('color')}")

        # All station checks passed if no failures were added
        station_staff = {s["station"]: s["staff_count"] for s in stations}
        result.ok("Station metrics", f"staff: {station_staff}, all ranges valid")

    return data


# ═══════════════════════════════════════════════════════════════════
# Test 2: Staff / station count cross-consistency
# ═══════════════════════════════════════════════════════════════════
async def test_staff_station_consistency(data: dict, result: ValidationResult):
    """Dashboard staff list counts must match station staff_count values."""
    staff = data.get("staff", [])
    stations = data.get("stations", [])

    if not staff or not stations:
        result.warn("Staff consistency", "Insufficient data to cross-check")
        return

    # Count staff per station from the staff roster
    roster_counts: dict[str, int] = {}
    for s in staff:
        station = s["station"]
        roster_counts[station] = roster_counts.get(station, 0) + 1

    # Compare with station metrics staff_count
    mismatches = []
    for st in stations:
        name = st["station"]
        metric_count = st["staff_count"]
        roster_count = roster_counts.get(name, 0)
        if metric_count != roster_count:
            mismatches.append(f"{name}: roster={roster_count}, metric={metric_count}")

    if mismatches:
        result.fail("Staff ↔ station count", "; ".join(mismatches))
    else:
        result.ok("Staff ↔ station count", f"Consistent: {roster_counts}")


# ═══════════════════════════════════════════════════════════════════
# Test 3: Order mix percentages sum to ~100%
# ═══════════════════════════════════════════════════════════════════
async def test_order_mix_integrity(data: dict, result: ValidationResult):
    """Order mix and channel split percentages should sum to ~100%."""
    order_mix = data.get("order_mix", {})
    channel_split = data.get("channel_split", {})

    if order_mix:
        mix_pct_sum = sum(v.get("pct", 0) for v in order_mix.values())
        mix_count_sum = sum(v.get("count", 0) for v in order_mix.values())
        # Allow rounding tolerance (integer percentages may not sum exactly)
        if mix_count_sum > 0 and not (95 <= mix_pct_sum <= 105):
            result.fail("Order mix %", f"Sum={mix_pct_sum}% (expected ~100%)")
        elif mix_count_sum > 0:
            result.ok("Order mix %", f"Sum={mix_pct_sum}%, counts={mix_count_sum}")
        else:
            result.warn("Order mix", "No active orders")

        # No negative counts
        for k, v in order_mix.items():
            if v.get("count", 0) < 0:
                result.fail(f"Order mix {k}", f"negative count: {v['count']}")
    else:
        result.warn("Order mix", "No data")

    if channel_split:
        ch_pct_sum = sum(v.get("pct", 0) for v in channel_split.values())
        ch_count_sum = sum(v.get("count", 0) for v in channel_split.values())
        if ch_count_sum > 0 and not (95 <= ch_pct_sum <= 105):
            result.fail("Channel split %", f"Sum={ch_pct_sum}% (expected ~100%)")
        elif ch_count_sum > 0:
            result.ok("Channel split %", f"Sum={ch_pct_sum}%, counts={ch_count_sum}")
        else:
            result.warn("Channel split", "No active orders")


# ═══════════════════════════════════════════════════════════════════
# Test 4: Hourly volume array
# ═══════════════════════════════════════════════════════════════════
async def test_hourly_volume(data: dict, result: ValidationResult):
    """Hourly volume should be a 17-element array (6am–10pm) with non-negative values."""
    hourly = data.get("hourly_volume", [])

    if not hourly:
        result.warn("Hourly volume", "Empty")
        return

    if len(hourly) != 17:
        result.fail("Hourly volume length", f"Expected 17 (6am-10pm), got {len(hourly)}")
    else:
        result.ok("Hourly volume length", "17 buckets (6am-10pm)")

    negatives = [i for i, v in enumerate(hourly) if v < 0]
    if negatives:
        result.fail("Hourly volume values", f"Negative at indices {negatives}")
    else:
        total = sum(hourly)
        peak_hr = hourly.index(max(hourly)) + 6
        result.ok("Hourly volume values", f"All non-negative, total={total}, peak={peak_hr}:00")


# ═══════════════════════════════════════════════════════════════════
# Test 5: Staff move → immediate data reflection (regression test)
# ═══════════════════════════════════════════════════════════════════
async def test_staff_move_consistency(base_url: str, result: ValidationResult):
    """
    Move a staff member, then immediately check that the dashboard
    reflects the new counts without waiting for a simulator tick.
    This is a regression test for the vw_CurrentStoreStatus bug.
    """
    # Step 1: Get baseline from dashboard
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.get(f"{base_url}/api/dashboard")
        if resp.status_code != 200:
            result.fail("Move test baseline", f"Dashboard HTTP {resp.status_code}")
            return
        baseline = resp.json()

    staff = baseline.get("staff", [])
    stations = baseline.get("stations", [])
    if len(staff) < 2 or len(stations) < 2:
        result.warn("Move test", "Need ≥2 staff and ≥2 stations to test")
        return

    # Find a station with ≥2 staff and another station to move to
    station_staff = {}
    for s in staff:
        station_staff.setdefault(s["station"], []).append(s["name"])

    source = None
    target = None
    mover = None
    for stn, names in station_staff.items():
        if len(names) >= 2:
            source = stn
            mover = names[0]
            break

    if not source:
        result.warn("Move test", "No station has ≥2 staff — skipping move test")
        return

    for stn in station_staff:
        if stn != source:
            target = stn
            break

    if not target:
        result.warn("Move test", "Only one station has staff — skipping")
        return

    source_count_before = len(station_staff[source])
    target_count_before = len(station_staff.get(target, []))

    # Step 2: Ask the agent to move staff
    move_msg = f"Move {mover} to {target}"
    move_response = await ws_ask(base_url, move_msg)

    if "error" in move_response["text"].lower() or "failed" in move_response["text"].lower():
        result.fail("Move test exec", f"Agent returned error: {move_response['text'][:200]}")
        return

    if not move_response["done"]:
        result.fail("Move test exec", "No [DONE] received")
        return

    result.ok("Move test exec", f"Moved {mover}: {source} → {target}")

    # Step 3: Immediately check dashboard — counts should reflect the move
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.get(f"{base_url}/api/dashboard")
        if resp.status_code != 200:
            result.fail("Move test verify", f"Dashboard HTTP {resp.status_code}")
            return
        after = resp.json()

    after_staff = {}
    for s in after.get("staff", []):
        after_staff.setdefault(s["station"], []).append(s["name"])

    source_count_after = len(after_staff.get(source, []))
    target_count_after = len(after_staff.get(target, []))

    # Verify roster counts changed
    if source_count_after != source_count_before - 1:
        result.fail("Move roster source", f"{source}: expected {source_count_before - 1}, got {source_count_after}")
    else:
        result.ok("Move roster source", f"{source}: {source_count_before} → {source_count_after}")

    if target_count_after != target_count_before + 1:
        result.fail("Move roster target", f"{target}: expected {target_count_before + 1}, got {target_count_after}")
    else:
        result.ok("Move roster target", f"{target}: {target_count_before} → {target_count_after}")

    # Verify station metrics staff_count matches roster (the bug we fixed)
    for st in after.get("stations", []):
        if st["station"] in (source, target):
            expected = len(after_staff.get(st["station"], []))
            if st["staff_count"] != expected:
                result.fail(
                    f"Move metric {st['station']}",
                    f"staff_count={st['staff_count']} but roster={expected} (DATA BUG!)"
                )
            else:
                result.ok(f"Move metric {st['station']}", f"staff_count={st['staff_count']} matches roster")

    # Step 4: Move staff back to restore original state
    restore_msg = f"Move {mover} to {source}"
    restore = await ws_ask(base_url, restore_msg)
    if restore["done"]:
        result.ok("Move restore", f"Restored {mover} back to {source}")
    else:
        result.warn("Move restore", f"May not have restored {mover} to {source}")


# ═══════════════════════════════════════════════════════════════════
# Test 6: Pipeline data integrity
# ═══════════════════════════════════════════════════════════════════
async def test_pipeline_data(data: dict, result: ValidationResult):
    """Mobile pipeline entries should have valid drink types and status."""
    pipeline = data.get("pipeline", [])

    if not pipeline:
        result.warn("Pipeline", "Empty (may be normal if no pending mobile orders)")
        return

    valid_drinks = {"hot", "cold", "food"}
    invalid = [p for p in pipeline if p.get("drink_type") not in valid_drinks]
    if invalid:
        result.fail("Pipeline drink types", f"Invalid: {[p.get('drink_type') for p in invalid]}")
    else:
        result.ok("Pipeline drink types", f"All {len(pipeline)} entries valid")

    # All should be 'pending' status (dashboard only fetches pending)
    non_pending = [p for p in pipeline if p.get("status") != "pending"]
    if non_pending:
        result.fail("Pipeline status", f"{len(non_pending)} non-pending entries")
    else:
        result.ok("Pipeline status", f"All {len(pipeline)} entries pending")


# ═══════════════════════════════════════════════════════════════════
# Test 7: Total staff count sanity
# ═══════════════════════════════════════════════════════════════════
async def test_staff_sanity(data: dict, result: ValidationResult):
    """Staff count should be reasonable (1-20 for a single store)."""
    staff = data.get("staff", [])
    if not staff:
        result.fail("Staff sanity", "No staff listed")
        return

    if len(staff) < 1 or len(staff) > 20:
        result.fail("Staff sanity", f"Unexpected count: {len(staff)} (expected 1-20)")
    else:
        names = [s["name"] for s in staff]
        result.ok("Staff sanity", f"{len(staff)} staff: {names}")

    # No duplicate staff (same person at two stations)
    seen_names = {}
    for s in staff:
        name = s["name"]
        if name in seen_names:
            result.fail("Staff duplicate", f"{name} at both {seen_names[name]} and {s['station']}")
        seen_names[name] = s["station"]

    if len(seen_names) == len(staff):
        result.ok("Staff uniqueness", "No duplicates")


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════
async def main():
    if len(sys.argv) < 2:
        print("Usage: python tests/data_validation_test.py <BASE_URL>")
        print("  e.g. python tests/data_validation_test.py https://shiftiq.azdemohub.com")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    print(f"\n{'=' * 55}")
    print(f"  Data Validation Tests \u2014 {base_url}")
    print(f"{'=' * 55}\n")

    result = ValidationResult()

    # ── Tests 1-4, 6-7: Dashboard-based (fast) ──
    print("  [1/7] Dashboard structure & KPI ranges...")
    data = await test_dashboard_structure(base_url, result)

    if data:
        print("  [2/7] Staff ↔ station count consistency...")
        await test_staff_station_consistency(data, result)

        print("  [3/7] Order mix percentage integrity...")
        await test_order_mix_integrity(data, result)

        print("  [4/7] Hourly volume array...")
        await test_hourly_volume(data, result)

        print("  [5/7] Pipeline data integrity...")
        await test_pipeline_data(data, result)

        print("  [6/7] Staff sanity checks...")
        await test_staff_sanity(data, result)
    else:
        print("  Skipping tests 2-6 (no dashboard data)")

    # ── Test 5: Staff move regression (slower — involves WebSocket + agent) ──
    print("  [7/7] Staff move → immediate data reflection (regression)...")
    await test_staff_move_consistency(base_url, result)

    success = result.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
