"""
Shared database connection helper.
Uses Entra ID token-based auth for Azure SQL since ODBC Driver 18
does not support the 'Authentication=ActiveDirectoryDefault' keyword.

Performance optimisations:
  - Caches the Entra ID access token for up to 45 minutes (tokens live ~60 min).
  - Exposes a `managed_connection()` context manager so callers get
    automatic `conn.close()` in a `finally` block, preventing leaks.
  - Reuses a single DefaultAzureCredential instance (imported from
    config.settings to share across the whole process).
"""
import struct
import threading
import time
from contextlib import contextmanager

import pyodbc

# Enable ODBC connection pooling explicitly (must be set before any connect())
pyodbc.pooling = True

from config.settings import SQL_SERVER_FQDN, SQL_DATABASE_NAME

# Lazy-import the shared credential on first use to avoid circular imports
_credential = None
_SQL_TOKEN_URL = "https://database.windows.net/.default"

# ── Token cache ──────────────────────────────────────────────────────
_token_cache_lock = threading.Lock()
_cached_token_struct: bytes | None = None
_cached_token_expiry: float = 0  # epoch seconds
_TOKEN_REFRESH_BUFFER_SECS = 15 * 60  # refresh 15 min before expiry

_CONN_STR = (
    f"Driver={{ODBC Driver 18 for SQL Server}};"
    f"Server={SQL_SERVER_FQDN};"
    f"Database={SQL_DATABASE_NAME};"
    f"Encrypt=Yes;TrustServerCertificate=No;"
)


def _get_credential():
    """Return the shared DefaultAzureCredential (created once)."""
    global _credential
    if _credential is None:
        from azure.identity import DefaultAzureCredential
        _credential = DefaultAzureCredential()
    return _credential


def _get_token_struct() -> bytes:
    """
    Return a packed SQL token struct, using a cached version when the
    token is still fresh.  Thread-safe.
    """
    global _cached_token_struct, _cached_token_expiry

    now = time.time()
    if _cached_token_struct and now < _cached_token_expiry:
        return _cached_token_struct

    with _token_cache_lock:
        # Double-check after acquiring lock
        now = time.time()
        if _cached_token_struct and now < _cached_token_expiry:
            return _cached_token_struct

        token = _get_credential().get_token(_SQL_TOKEN_URL)
        token_bytes = token.token.encode("utf-16-le")
        _cached_token_struct = struct.pack(
            f"<I{len(token_bytes)}s", len(token_bytes), token_bytes
        )
        _cached_token_expiry = token.expires_on - _TOKEN_REFRESH_BUFFER_SECS
        return _cached_token_struct


def get_connection() -> pyodbc.Connection:
    """Get a pyodbc connection to Azure SQL using Entra ID token auth."""
    return pyodbc.connect(_CONN_STR, attrs_before={1256: _get_token_struct()})


@contextmanager
def managed_connection():
    """
    Context manager that yields a pyodbc Connection and guarantees
    ``conn.close()`` even if the caller raises an exception.

    Usage::

        with managed_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def warm_up():
    """
    Pre-warm the database connection path: acquires and caches the
    Entra ID token and performs a TCP handshake + TLS negotiation
    with SQL Server. Call once during app startup to avoid cold-start
    latency on the first user request.
    """
    with managed_connection() as conn:
        conn.cursor().execute("SELECT 1")
