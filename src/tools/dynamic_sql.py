"""
Dynamic SQL tools — let the LLM generate and execute SQL queries
based on the user's question and the actual database schema.

Safety guardrails:
  - run_sql_query only allows SELECT statements (read-only)
  - Query timeout of 30 seconds prevents runaway queries
  - Results capped at 50 rows to prevent huge payloads
  - Schema discovery provides full context so the LLM writes accurate SQL
"""
import logging
import re

from tools.db import managed_connection
from config.settings import DEFAULT_STORE_ID

log = logging.getLogger(__name__)

# Maximum rows returned from any dynamic query
_MAX_ROWS = 50

# ── Schema cache ──────────────────────────────────────────────────
# The database schema is static within a session. Caching it avoids
# a redundant SQL round-trip + reduces LLM input tokens on every call.
_schema_cache: dict[str, dict] = {}
# Query timeout in seconds
_QUERY_TIMEOUT_SECS = 30

# Statements that are NOT allowed (write operations + dangerous read patterns)
_BLOCKED_PATTERNS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|MERGE|"
    r"GRANT|REVOKE|DENY|BACKUP|RESTORE|SHUTDOWN|DBCC|BULK|OPENROWSET|OPENDATASOURCE|xp_|"
    r"INTO|INFORMATION_SCHEMA|sys\.|sp_|fn_)\b",
    re.IGNORECASE,
)

# Strip SQL comments (both -- and /* ... */) for safe pattern matching
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def get_database_schema(store_id: str = DEFAULT_STORE_ID) -> dict:
    """
    Returns the complete database schema: all tables, their columns
    (with data types), and a few sample rows from each table.
    Call this first to understand what data is available before writing
    SQL queries. The store_id filter applies to sample data only.
    Results are cached in memory — the schema doesn't change between calls.
    """
    if store_id in _schema_cache:
        log.info("Returning cached schema for %s", store_id)
        return _schema_cache[store_id]

    with managed_connection() as conn:
        cursor = conn.cursor()

        # Get all user tables
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
            ORDER BY TABLE_TYPE, TABLE_NAME
        """)
        tables = [(row.TABLE_SCHEMA, row.TABLE_NAME) for row in cursor.fetchall()]

        schema = {}
        for table_schema, table_name in tables:
            full_name = f"{table_schema}.{table_name}"

            # Get columns
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
                       CHARACTER_MAXIMUM_LENGTH, COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """, table_schema, table_name)

            columns = []
            for col in cursor.fetchall():
                col_info = {
                    "name": col.COLUMN_NAME,
                    "type": col.DATA_TYPE,
                    "nullable": col.IS_NULLABLE == "YES",
                }
                if col.CHARACTER_MAXIMUM_LENGTH:
                    col_info["max_length"] = col.CHARACTER_MAXIMUM_LENGTH
                columns.append(col_info)

            # Get 1 sample row to help the LLM understand data patterns
            # (reduced from 3 to cut token count — schema is sent on every tool call)
            try:
                cursor.execute(f"SELECT TOP 1 * FROM [{table_schema}].[{table_name}]")
                col_names = [desc[0] for desc in cursor.description]
                sample_rows = []
                for row in cursor.fetchall():
                    sample_row = {}
                    for i, val in enumerate(row):
                        sample_row[col_names[i]] = str(val) if val is not None else None
                    sample_rows.append(sample_row)
            except Exception:
                sample_rows = []

            # Get row count
            try:
                cursor.execute(
                    f"SELECT COUNT(*) AS cnt FROM [{table_schema}].[{table_name}]"
                )
                row_count = cursor.fetchone().cnt
            except Exception:
                row_count = "unknown"

            # Compact column representation: "ColName (type)" to save tokens
            compact_cols = [f"{c['name']} ({c['type']})" for c in columns]

            schema[full_name] = {
                "columns": compact_cols,
                "row_count": row_count,
                "sample": sample_rows[0] if sample_rows else {},
            }

    result = {
        "store_id": store_id,
        "database_tables": schema,
        "data_domain": (
            "This database covers REAL-TIME STORE OPERATIONS for a coffee shop. "
            "Available data includes: "
            "(1) Station metrics — orders/hr, capacity %, wait times, staff count per station (hot_bar, cold_bar, food); "
            "(2) Staff assignments — who is working at which station, shift times; "
            "(3) Live orders — current in-progress and queued orders by type (hot/cold/food) and channel (in_store/mobile); "
            "(4) Mobile order queue — pending mobile orders with scheduled times; "
            "(5) Hourly targets — expected order targets by hour and day of week; "
            "(6) Historical station metrics — past throughput data with timestamps. "
            "NOT available: revenue/sales dollars, customer names, payment info, "
            "inventory/stock levels, product menus/prices, customer satisfaction scores, "
            "employee personal details, tips, multi-store comparisons (only STORE-001 has data)."
        ),
        "notes": (
            "Most tables have a StoreId column. Filter by the store_id above "
            "unless the user asks about all stores. "
            "Use SYSUTCDATETIME() for current UTC time comparisons. "
            "Views (prefixed with vw_) combine data from multiple tables."
        ),
    }
    _schema_cache[store_id] = result
    log.info("Schema cached for %s (%d tables)", store_id, len(schema))
    return result


def run_sql_query(sql_query: str, store_id: str = DEFAULT_STORE_ID) -> dict:
    """
    Execute a READ-ONLY SQL query against the database and return results.
    Only SELECT statements are allowed. INSERT/UPDATE/DELETE/DROP etc. are blocked.
    Results are capped at 50 rows. Use this after calling get_database_schema
    to understand the available tables and columns.

    Args:
        sql_query: A valid T-SQL SELECT statement.
        store_id: Store ID for context (not auto-applied — include in your WHERE clause).
    """
    # Safety: strip comments before pattern matching to prevent bypass
    sanitized = _BLOCK_COMMENT.sub(" ", sql_query)
    sanitized = _LINE_COMMENT.sub(" ", sanitized)

    # Safety: block write operations + dangerous read patterns
    if _BLOCKED_PATTERNS.search(sanitized):
        return {
            "success": False,
            "error": (
                "Query blocked: only simple SELECT statements are allowed. "
                "Write operations, system catalog access, and SELECT INTO "
                "are not permitted through this tool."
            ),
            "suggestion": "Use move_staff_to_station tool for staff reassignments.",
        }

    # Safety: must start with SELECT (after stripping whitespace/comments)
    stripped = sanitized.strip()
    if not stripped.upper().startswith("SELECT"):
        return {
            "success": False,
            "error": "Query must be a SELECT statement.",
        }

    try:
        with managed_connection() as conn:
            conn.timeout = _QUERY_TIMEOUT_SECS
            cursor = conn.cursor()
            cursor.execute(sql_query)

            col_names = [desc[0] for desc in cursor.description]
            rows = []
            for row in cursor.fetchmany(_MAX_ROWS):
                row_dict = {}
                for i, val in enumerate(row):
                    row_dict[col_names[i]] = str(val) if val is not None else None
                rows.append(row_dict)

            # Check if there are more rows
            has_more = cursor.fetchone() is not None

        return {
            "success": True,
            "columns": col_names,
            "rows": rows,
            "row_count": len(rows),
            "truncated": has_more,
            "note": f"Showing up to {_MAX_ROWS} rows." if has_more else None,
        }

    except Exception as exc:
        log.warning("Dynamic SQL query failed: %s | Query: %s", exc, sql_query)
        return {
            "success": False,
            "error": str(exc),
            "query": sql_query,
            "suggestion": "Check column names and table names using get_database_schema.",
        }
