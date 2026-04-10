"""
Ops Assistant — FastAPI + WebSocket server.

Two-layer architecture:
  Layer 1 — azure-ai-projects SDK: registers agents in Foundry portal
  Layer 2 — Microsoft Agent Framework: wraps them for orchestration
  + Foundry IQ: AzureAISearchContextProvider for native KB grounding
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config.settings import (
    AZURE_AI_PROJECT_ENDPOINT,
    MODEL_DEPLOYMENT_NAME,
    TRIAGE_MODEL_DEPLOYMENT,
    DEFAULT_STORE_ID,
    ENABLE_TRAFFIC_SIMULATOR,
    TRAFFIC_SIMULATOR_INTERVAL_SECS,
    ENABLE_FOUNDRY_TRACING,
)
from agents.registry import register_agents_in_foundry, build_framework_agents, cleanup_agents
from models.messages import WebSocketMessageType
from orchestrator import OpsAssistantOrchestrator
from tools.db import managed_connection, warm_up
from tools.dynamic_sql import _schema_cache, get_database_schema
from tools.dashboard import get_dashboard_data

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ── Shared state ──
_agents: dict = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup:
      1. Register agents in Foundry portal (azure-ai-projects)
      2. Wrap them with Agent Framework + Foundry IQ for orchestration
    """
    global _agents

    log.info("Connecting to Microsoft Foundry: %s", AZURE_AI_PROJECT_ENDPOINT)

    # Pre-warm: cache Entra ID token + TCP/TLS handshake with SQL Server
    try:
        warm_up()
        log.info("Database connection pre-warmed (token cached)")
    except Exception as exc:
        log.warning("DB warm-up failed (non-fatal): %s", exc)

    # Pre-warm schema cache so first user query skips the heavy schema SQL
    try:
        schema = get_database_schema()
        log.info(
            "Schema cache pre-warmed: %d tables",
            len(schema.get("database_tables", {})),
        )
    except Exception as exc:
        log.warning("Schema pre-warm failed (non-fatal): %s", exc)

    credential = DefaultAzureCredential()

    # Layer 1: Register agents so they appear in Foundry portal
    project_client = AIProjectClient(
        endpoint=AZURE_AI_PROJECT_ENDPOINT,
        credential=credential,
    )

    # ── Foundry Tracing: send OpenTelemetry spans to Application Insights ──
    if ENABLE_FOUNDRY_TRACING:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            conn_string = project_client.telemetry.get_application_insights_connection_string()
            if conn_string:
                configure_azure_monitor(connection_string=conn_string)
                log.info("Foundry tracing enabled → Application Insights")
            else:
                log.warning(
                    "Foundry tracing: no Application Insights linked to project. "
                    "Link one in Foundry portal → Tracing → Manage data source."
                )
        except Exception as exc:
            log.warning("Foundry tracing setup failed (non-fatal): %s", exc)
    else:
        log.info("Foundry tracing disabled (set ENABLE_FOUNDRY_TRACING=true to enable)")

    agent_names = register_agents_in_foundry(
        project_client, MODEL_DEPLOYMENT_NAME, TRIAGE_MODEL_DEPLOYMENT
    )
    log.info("Foundry agents registered: %s", list(agent_names.keys()))

    # Layer 2: Wrap with Agent Framework + Foundry IQ context providers
    _agents = build_framework_agents(
        project_endpoint=AZURE_AI_PROJECT_ENDPOINT,
        model_deployment=MODEL_DEPLOYMENT_NAME,
        credential=credential,
        agent_names=agent_names,
        triage_model_deployment=TRIAGE_MODEL_DEPLOYMENT,
    )
    log.info("Framework agents ready: %s", list(_agents.keys()))

    # Start traffic simulator if enabled
    _traffic_task = None
    if ENABLE_TRAFFIC_SIMULATOR:
        from tools.traffic_simulator import start_traffic_loop
        _traffic_task = asyncio.create_task(
            start_traffic_loop(interval_secs=TRAFFIC_SIMULATOR_INTERVAL_SECS)
        )
        log.info("Traffic simulator enabled (interval=%ds)", TRAFFIC_SIMULATOR_INTERVAL_SECS)
    else:
        log.info("Traffic simulator disabled (set ENABLE_TRAFFIC_SIMULATOR=true to enable)")

    yield  # App is running

    # ── Graceful shutdown: release agent resources ──
    if _traffic_task:
        _traffic_task.cancel()
    await cleanup_agents(_agents)
    log.info("Shutdown complete")


app = FastAPI(title="Multi-Agent Ops Assistant", lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.get("/")
async def root():
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/dashboard")
async def dashboard():
    """Return sidebar KPIs, station health, staff, pipeline, etc."""
    try:
        data = await asyncio.to_thread(get_dashboard_data)
        return JSONResponse(data)
    except Exception as e:
        log.error("Dashboard fetch failed: %s", e, exc_info=True)
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@app.get("/api/simulator")
async def simulator_status():
    """Check whether the traffic simulator is running."""
    return JSONResponse({
        "enabled": ENABLE_TRAFFIC_SIMULATOR,
        "interval_secs": TRAFFIC_SIMULATOR_INTERVAL_SECS,
    })


@app.post("/reset")
async def reset_demo():
    """Reset all demo data to original seed state."""
    try:
        await asyncio.to_thread(_reset_seed_data)
        return JSONResponse({"status": "ok", "message": "Demo data reset to seed state"})
    except Exception as e:
        log.error("Reset failed: %s", e, exc_info=True)
        return JSONResponse(
            {"status": "error", "message": "Internal server error"},
            status_code=500,
        )


def _reset_seed_data():
    """Sync helper — runs all reset SQL in a single connection (thread-safe)."""
    # Clear schema cache so next call picks up fresh data
    _schema_cache.clear()

    with managed_connection() as conn:
        cursor = conn.cursor()
        sid = DEFAULT_STORE_ID

        # Reset staff assignments
        cursor.execute("DELETE FROM dbo.StaffAssignments WHERE StoreId = ?", sid)
        cursor.execute("""
            INSERT INTO dbo.StaffAssignments (StoreId, EmployeeName, Station, ShiftStart, ShiftEnd, IsActive)
            VALUES
                (?, 'Sarah', 'hot_bar', DATEADD(HOUR, 6, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), DATEADD(HOUR, 14, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), 1),
                (?, 'Mike',  'hot_bar', DATEADD(HOUR, 6, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), DATEADD(HOUR, 14, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), 1),
                (?, 'Lisa',  'cold_bar',DATEADD(HOUR, 6, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), DATEADD(HOUR, 14, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), 1),
                (?, 'James', 'cold_bar',DATEADD(HOUR, 6, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), DATEADD(HOUR, 14, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), 1),
                (?, 'Emma',  'food',    DATEADD(HOUR, 6, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), DATEADD(HOUR, 14, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), 1)
        """, sid, sid, sid, sid, sid)

        # Reset station metrics — current snapshot + historical hourly data
        cursor.execute("DELETE FROM dbo.StationMetrics WHERE StoreId = ?", sid)
        # Current snapshot (default timestamp = now)
        cursor.execute("""
            INSERT INTO dbo.StationMetrics (StoreId, Station, OrdersPerHour, CapacityPct, StaffCount, AvgWaitSecs)
            VALUES
                (?, 'hot_bar',  35, 60.00,  2, 120),
                (?, 'cold_bar', 52, 125.00, 2, 310),
                (?, 'food',     15, 40.00,  1, 90)
        """, sid, sid, sid)
        # Historical hourly data for the sparkline chart (today, hours 6am–current)
        hourly_profile = [
            (6, 12, 8, 4),   (7, 28, 20, 8),  (8, 42, 35, 12),
            (9, 38, 32, 10), (10, 30, 22, 8), (11, 25, 18, 7),
            (12, 35, 28, 10),(13, 32, 25, 9), (14, 28, 20, 7),
            (15, 25, 18, 6), (16, 28, 22, 7), (17, 32, 25, 8),
            (18, 25, 18, 6), (19, 18, 12, 5), (20, 12, 8, 3),
            (21, 8, 5, 2),
        ]  # (hour, hot_orders, cold_orders, food_orders)
        hist_values = []
        hist_params = []
        for hr, hot, cold, food in hourly_profile:
            for station, orders, cap, wait in [
                ('hot_bar', hot, 40 + hot, 90 + hot * 2),
                ('cold_bar', cold, 50 + cold, 120 + cold * 3),
                ('food', food, 20 + food, 60 + food * 2),
            ]:
                hist_values.append("(?, ?, ?, ?, CASE WHEN ? = 'cold_bar' THEN 2 WHEN ? = 'hot_bar' THEN 2 ELSE 1 END, ?, DATEADD(HOUR, ? - DATEPART(HOUR, SYSUTCDATETIME()), SYSUTCDATETIME()))")
                hist_params.extend([sid, station, orders, cap, station, station, wait, hr])
        if hist_values:
            cursor.execute(
                f"INSERT INTO dbo.StationMetrics (StoreId, Station, OrdersPerHour, CapacityPct, StaffCount, AvgWaitSecs, [Timestamp]) VALUES {', '.join(hist_values)}",
                *hist_params,
            )

        # Reset hourly targets (single batch INSERT instead of 119 individual ones)
        cursor.execute("DELETE FROM dbo.HourlyTargets WHERE StoreId = ?", sid)
        values_rows = []
        params = []
        for dow in range(7):
            for hour in range(6, 23):
                target = 95 if 9 <= hour <= 14 else 70 if 7 <= hour <= 17 else 50
                values_rows.append("(?, ?, ?, ?, 5)")
                params.extend([sid, hour, dow, target])
        cursor.execute(
            f"INSERT INTO dbo.HourlyTargets (StoreId, HourOfDay, DayOfWeek, TargetOrders, MinStaff) VALUES {', '.join(values_rows)}",
            *params,
        )

        # Reset mobile order queue
        cursor.execute("DELETE FROM dbo.MobileOrderQueue WHERE StoreId = ?", sid)
        cursor.execute("""
            INSERT INTO dbo.MobileOrderQueue (StoreId, OrderId, ScheduledTime, DrinkType, Status)
            VALUES
                (?, NEWID(), DATEADD(MINUTE, 5,  SYSUTCDATETIME()), 'cold', 'pending'),
                (?, NEWID(), DATEADD(MINUTE, 8,  SYSUTCDATETIME()), 'cold', 'pending'),
                (?, NEWID(), DATEADD(MINUTE, 10, SYSUTCDATETIME()), 'cold', 'pending'),
                (?, NEWID(), DATEADD(MINUTE, 12, SYSUTCDATETIME()), 'hot',  'pending'),
                (?, NEWID(), DATEADD(MINUTE, 15, SYSUTCDATETIME()), 'cold', 'pending'),
                (?, NEWID(), DATEADD(MINUTE, 18, SYSUTCDATETIME()), 'cold', 'pending'),
                (?, NEWID(), DATEADD(MINUTE, 20, SYSUTCDATETIME()), 'cold', 'pending'),
                (?, NEWID(), DATEADD(MINUTE, 25, SYSUTCDATETIME()), 'cold', 'pending')
        """, sid, sid, sid, sid, sid, sid, sid, sid)

        # Reset live orders
        cursor.execute("DELETE FROM dbo.LiveOrders WHERE StoreId = ?", sid)
        cursor.execute("""
            INSERT INTO dbo.LiveOrders (StoreId, OrderType, DrinkType, Station, Status)
            VALUES
                (?, 'in_store', 'cold', 'cold_bar', 'in_progress'),
                (?, 'mobile',   'cold', 'cold_bar', 'queued'),
                (?, 'in_store', 'cold', 'cold_bar', 'in_progress'),
                (?, 'mobile',   'cold', 'cold_bar', 'queued'),
                (?, 'in_store', 'cold', 'cold_bar', 'in_progress'),
                (?, 'in_store', 'hot',  'hot_bar',  'in_progress'),
                (?, 'in_store', 'hot',  'hot_bar',  'queued'),
                (?, 'mobile',   'cold', 'cold_bar', 'in_progress'),
                (?, 'in_store', 'food', 'food',     'in_progress'),
                (?, 'mobile',   'cold', 'cold_bar', 'queued'),
                (?, 'in_store', 'hot',  'hot_bar',  'queued'),
                (?, 'in_store', 'cold', 'cold_bar', 'in_progress')
        """, sid, sid, sid, sid, sid, sid, sid, sid, sid, sid, sid, sid)

        conn.commit()


@app.websocket("/ws")
async def ws_chat(ws: WebSocket):
    """
    WebSocket chat — each connection gets its own orchestrator with
    per-specialist sessions. Messages flow: Triage → Specialist → Response.

    Uses Agent Framework streaming (Agent.run(stream=True)) for real
    token-by-token delivery instead of fake chunking.

    ⚠️  SINGLE-USER DEMO: No authentication, no session persistence.
    Conversation history lives only in the in-memory AgentSession objects
    and is lost when the WebSocket disconnects or the process restarts.
    For production, add Entra ID auth, persist messages to a database,
    and load history on reconnect.
    """
    await ws.accept()

    orch = OpsAssistantOrchestrator(agents=_agents)

    try:
        while True:
            user_msg = await ws.receive_text()
            if not user_msg.strip():
                continue

            try:
                async for event in orch.process_message_stream(user_msg):
                    if event.type == "agent":
                        await ws.send_text(f"[{WebSocketMessageType.AGENT}:{event.data}]")
                    elif event.type == "safety":
                        await ws.send_text(f"[{WebSocketMessageType.SAFETY}:{event.data}]")
                    elif event.type == "delta":
                        await ws.send_text(event.data)
                    elif event.type == "suggestions":
                        await ws.send_text(f"[{WebSocketMessageType.SUGGESTIONS}:{event.data}]")
                    elif event.type == "done":
                        await ws.send_text(f"[{WebSocketMessageType.DONE}]")

            except Exception as e:
                log.error("Error processing message: %s", e, exc_info=True)
                await ws.send_text("Something went wrong. Please try again.")
                await ws.send_text(f"[{WebSocketMessageType.DONE}]")

    except WebSocketDisconnect:
        log.info("WebSocket disconnected")
