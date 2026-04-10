"""
Order Traffic Simulator — background task that generates realistic order flow.

Runs as an async background task inside the FastAPI process. Every tick
(default 60s) it inserts new orders, completes old ones, refreshes station
metrics, and drips mobile orders — keeping the demo data alive and evolving.

Toggled via ENABLE_TRAFFIC_SIMULATOR env var (default: false).
"""
import asyncio
import logging
import random
from datetime import datetime, timezone

from tools.db import managed_connection
from config.settings import DEFAULT_STORE_ID

log = logging.getLogger(__name__)

# ── Time-of-day order-rate profiles (orders per tick per station) ──
# Keys = hour (UTC), values = (hot_bar_mean, cold_bar_mean, food_mean)
_HOURLY_PROFILE = {
    6: (3, 1, 1),   7: (5, 3, 1),   8: (7, 5, 2),
    9: (7, 6, 2),  10: (6, 5, 2),  11: (5, 4, 2),
    12: (6, 5, 3), 13: (5, 5, 2),  14: (5, 4, 2),
    15: (4, 3, 1), 16: (4, 4, 2),  17: (5, 5, 2),
    18: (4, 3, 1), 19: (3, 2, 1),  20: (2, 1, 1),
    21: (1, 1, 0),
}
_DEFAULT_RATE = (2, 1, 1)  # outside operating hours

_ORDER_TYPES = ["in_store", "mobile", "drive_thru"]
_ORDER_TYPE_WEIGHTS = [0.55, 0.30, 0.15]

_DRINK_MAP = {
    "hot_bar": "hot",
    "cold_bar": "cold",
    "food": "food",
}

# Completion probability per tick for in_progress orders (higher = faster throughput)
_COMPLETION_PROB_BY_STATION = {
    "hot_bar": 0.6,
    "cold_bar": 0.4,  # slower — cold drinks take longer
    "food": 0.5,
}

# Mobile drip: probability of a new mobile order arriving each tick
_MOBILE_DRIP_PROB = 0.35


def _generate_orders(cursor, store_id: str, hour: int):
    """Insert a batch of new orders based on time-of-day profile."""
    hot_mean, cold_mean, food_mean = _HOURLY_PROFILE.get(hour, _DEFAULT_RATE)

    new_orders = []
    for station, mean in [("hot_bar", hot_mean), ("cold_bar", cold_mean), ("food", food_mean)]:
        count = max(0, int(random.gauss(mean, mean * 0.3)))
        for _ in range(count):
            order_type = random.choices(_ORDER_TYPES, _ORDER_TYPE_WEIGHTS, k=1)[0]
            drink_type = _DRINK_MAP[station]
            status = random.choice(["queued", "in_progress"])
            new_orders.append((store_id, order_type, drink_type, station, status))

    if new_orders:
        placeholders = ", ".join(["(?, ?, ?, ?, ?)"] * len(new_orders))
        params = [p for row in new_orders for p in row]
        cursor.execute(
            f"INSERT INTO dbo.LiveOrders (StoreId, OrderType, DrinkType, Station, Status) VALUES {placeholders}",
            *params,
        )

    return len(new_orders)


def _complete_orders(cursor, store_id: str):
    """Randomly complete some in-progress orders to simulate throughput."""
    completed = 0
    for station, prob in _COMPLETION_PROB_BY_STATION.items():
        # Get in_progress orders for this station
        cursor.execute(
            "SELECT OrderId FROM dbo.LiveOrders WHERE StoreId = ? AND Station = ? AND Status = 'in_progress'",
            store_id, station,
        )
        in_progress = [row[0] for row in cursor.fetchall()]

        to_complete = [oid for oid in in_progress if random.random() < prob]
        if to_complete:
            placeholders = ", ".join(["?"] * len(to_complete))
            cursor.execute(
                f"UPDATE dbo.LiveOrders SET Status = 'completed', CompletedTime = SYSUTCDATETIME(), "
                f"WaitTimeSecs = DATEDIFF(SECOND, OrderTime, SYSUTCDATETIME()) "
                f"WHERE OrderId IN ({placeholders})",
                *to_complete,
            )
            completed += len(to_complete)

    # Promote some queued → in_progress
    cursor.execute(
        "UPDATE dbo.LiveOrders SET Status = 'in_progress' "
        "WHERE StoreId = ? AND Status = 'queued' "
        "AND OrderId IN (SELECT TOP 5 OrderId FROM dbo.LiveOrders "
        "WHERE StoreId = ? AND Status = 'queued' ORDER BY OrderTime)",
        store_id, store_id,
    )

    return completed


def _cleanup_old_orders(cursor, store_id: str):
    """Remove completed orders older than 30 minutes to prevent table bloat."""
    cursor.execute(
        "DELETE FROM dbo.LiveOrders WHERE StoreId = ? AND Status = 'completed' "
        "AND CompletedTime < DATEADD(MINUTE, -30, SYSUTCDATETIME())",
        store_id,
    )


def _refresh_station_metrics(cursor, store_id: str):
    """Recompute station metrics from current LiveOrders + StaffAssignments."""
    stations = ["hot_bar", "cold_bar", "food"]
    for station in stations:
        # Count active orders
        cursor.execute(
            "SELECT COUNT(*) FROM dbo.LiveOrders WHERE StoreId = ? AND Station = ? AND Status IN ('queued', 'in_progress')",
            store_id, station,
        )
        active_orders = cursor.fetchone()[0]

        # Count staff
        cursor.execute(
            "SELECT COUNT(*) FROM dbo.StaffAssignments WHERE StoreId = ? AND Station = ? AND IsActive = 1",
            store_id, station,
        )
        staff_count = max(cursor.fetchone()[0], 1)

        # Compute avg wait from recent completed orders (last 15 min)
        cursor.execute(
            "SELECT AVG(WaitTimeSecs) FROM dbo.LiveOrders WHERE StoreId = ? AND Station = ? "
            "AND Status = 'completed' AND CompletedTime > DATEADD(MINUTE, -15, SYSUTCDATETIME())",
            store_id, station,
        )
        avg_wait = cursor.fetchone()[0] or (active_orders * 30)  # fallback estimate

        # Throughput: completed in last 60 min, scaled to per-hour
        cursor.execute(
            "SELECT COUNT(*) FROM dbo.LiveOrders WHERE StoreId = ? AND Station = ? "
            "AND Status = 'completed' AND CompletedTime > DATEADD(HOUR, -1, SYSUTCDATETIME())",
            store_id, station,
        )
        orders_per_hour = cursor.fetchone()[0]

        # Capacity = active orders / (staff * baseline throughput)
        baseline_per_staff = {"hot_bar": 20, "cold_bar": 15, "food": 18}
        max_capacity = staff_count * baseline_per_staff.get(station, 15)
        capacity_pct = round((active_orders / max(max_capacity, 1)) * 100, 2) if max_capacity else 0

        # Insert new snapshot (keeps history for sparkline chart)
        cursor.execute(
            "INSERT INTO dbo.StationMetrics (StoreId, Station, OrdersPerHour, CapacityPct, StaffCount, AvgWaitSecs) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            store_id, station, orders_per_hour, capacity_pct, staff_count, int(avg_wait),
        )


def _drip_mobile_orders(cursor, store_id: str):
    """Occasionally add a new pending mobile order to keep the pipeline alive."""
    if random.random() < _MOBILE_DRIP_PROB:
        drink = random.choices(["cold", "hot", "food"], [0.6, 0.3, 0.1], k=1)[0]
        minutes_ahead = random.randint(5, 25)
        cursor.execute(
            "INSERT INTO dbo.MobileOrderQueue (StoreId, OrderId, ScheduledTime, DrinkType, Status) "
            "VALUES (?, NEWID(), DATEADD(MINUTE, ?, SYSUTCDATETIME()), ?, 'pending')",
            store_id, minutes_ahead, drink,
        )

    # Accept some pending mobile orders that are due
    cursor.execute(
        "UPDATE dbo.MobileOrderQueue SET Status = 'accepted' "
        "WHERE StoreId = ? AND Status = 'pending' AND ScheduledTime <= SYSUTCDATETIME()",
        store_id,
    )

    # Clean up old accepted/preparing entries
    cursor.execute(
        "DELETE FROM dbo.MobileOrderQueue WHERE StoreId = ? AND Status IN ('accepted', 'preparing') "
        "AND ScheduledTime < DATEADD(MINUTE, -30, SYSUTCDATETIME())",
        store_id,
    )


def run_tick(store_id: str | None = None):
    """Execute one simulation tick — called from the async loop."""
    sid = store_id or DEFAULT_STORE_ID
    hour = datetime.now(timezone.utc).hour

    with managed_connection() as conn:
        cursor = conn.cursor()

        new = _generate_orders(cursor, sid, hour)
        done = _complete_orders(cursor, sid)
        _cleanup_old_orders(cursor, sid)
        _refresh_station_metrics(cursor, sid)
        _drip_mobile_orders(cursor, sid)

        conn.commit()

    return {"new_orders": new, "completed": done, "hour": hour}


async def start_traffic_loop(interval_secs: int = 60):
    """
    Async background loop — runs forever, one tick per interval.
    Designed to be launched via asyncio.create_task() at app startup.
    """
    log.info("Traffic simulator started (interval=%ds, store=%s)", interval_secs, DEFAULT_STORE_ID)
    while True:
        try:
            result = await asyncio.to_thread(run_tick)
            log.debug(
                "Traffic tick: +%d orders, %d completed (hour=%d)",
                result["new_orders"], result["completed"], result["hour"],
            )
        except Exception as e:
            log.warning("Traffic simulator tick failed: %s", e)
        await asyncio.sleep(interval_secs)
