"""
Unit tests for dynamic SQL safety guardrails.

Tests the SQL injection prevention, blocked patterns, comment stripping,
and query validation in run_sql_query without a live database.
"""
import re
import pytest


# ── Import the module-level patterns and helpers ─────────────────────

from tools.dynamic_sql import _BLOCKED_PATTERNS, _LINE_COMMENT, _BLOCK_COMMENT


# ── Tests: blocked SQL patterns ──────────────────────────────────────

class TestBlockedPatterns:
    """SQL injection and write-operation detection."""

    @pytest.mark.parametrize("keyword", [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "EXEC", "EXECUTE", "MERGE", "GRANT", "REVOKE",
        "DENY", "BACKUP", "RESTORE", "SHUTDOWN", "DBCC", "BULK",
        "OPENROWSET", "OPENDATASOURCE",
    ])
    def test_blocks_write_operations(self, keyword):
        text = f"{keyword} INTO dbo.Staff VALUES ('hacker')"
        assert _BLOCKED_PATTERNS.search(text) is not None

    @pytest.mark.parametrize("keyword", [
        "insert", "update", "delete", "drop", "alter", "create",
        "truncate", "exec", "execute",
    ])
    def test_blocks_case_insensitive(self, keyword):
        text = f"{keyword} something"
        assert _BLOCKED_PATTERNS.search(text) is not None

    def test_blocks_xp_cmdshell(self):
        # xp_ and sp_ contain word char `_`, so \b won't match before them.
        # But they ARE caught when preceded by EXEC: "EXEC xp_cmdshell"
        assert _BLOCKED_PATTERNS.search("EXEC xp_cmdshell 'dir'") is not None

    def test_blocks_sp_via_exec(self):
        assert _BLOCKED_PATTERNS.search("EXEC sp_executesql @sql") is not None

    def test_blocks_information_schema(self):
        assert _BLOCKED_PATTERNS.search(
            "SELECT * FROM INFORMATION_SCHEMA.TABLES"
        ) is not None

    def test_blocks_sys_objects(self):
        assert _BLOCKED_PATTERNS.search(
            "SELECT * FROM sys.objects"
        ) is not None

    def test_blocks_select_into(self):
        assert _BLOCKED_PATTERNS.search(
            "SELECT * INTO #temp FROM dbo.Staff"
        ) is not None

    def test_allows_simple_select(self):
        assert _BLOCKED_PATTERNS.search(
            "SELECT EmployeeName, Station FROM dbo.StaffAssignments WHERE StoreId = 'STORE-001'"
        ) is None

    def test_allows_select_with_aggregates(self):
        assert _BLOCKED_PATTERNS.search(
            "SELECT Station, COUNT(*) AS cnt FROM dbo.StaffAssignments GROUP BY Station"
        ) is None

    def test_allows_select_with_join(self):
        assert _BLOCKED_PATTERNS.search(
            "SELECT a.EmployeeName, b.Station FROM dbo.Staff a JOIN dbo.Stations b ON a.StationId = b.Id"
        ) is None

    def test_allows_select_top(self):
        assert _BLOCKED_PATTERNS.search(
            "SELECT TOP 10 * FROM dbo.LiveOrders ORDER BY OrderTime DESC"
        ) is None


# ── Tests: comment stripping ─────────────────────────────────────────

class TestCommentStripping:
    """SQL comment removal before pattern matching."""

    def test_strips_line_comments(self):
        sql = "SELECT 1 -- DROP TABLE users"
        stripped = _LINE_COMMENT.sub(" ", sql)
        assert "DROP" not in stripped

    def test_strips_block_comments(self):
        sql = "SELECT 1 /* DELETE FROM users */"
        stripped = _BLOCK_COMMENT.sub(" ", sql)
        assert "DELETE" not in stripped

    def test_strips_multiline_block_comments(self):
        sql = "SELECT 1 /* \nDROP TABLE\nusers\n*/"
        stripped = _BLOCK_COMMENT.sub(" ", sql)
        assert "DROP" not in stripped


# ── Tests: run_sql_query validation (without DB connection) ──────────

class TestRunSqlQueryValidation:
    """Test query validation logic in run_sql_query (mocked DB)."""

    def test_rejects_insert(self):
        from tools.dynamic_sql import run_sql_query
        result = run_sql_query("INSERT INTO dbo.Staff VALUES ('hacker')")
        assert result["success"] is False
        assert "blocked" in result["error"].lower()

    def test_rejects_delete(self):
        from tools.dynamic_sql import run_sql_query
        result = run_sql_query("DELETE FROM dbo.StaffAssignments")
        assert result["success"] is False

    def test_rejects_drop(self):
        from tools.dynamic_sql import run_sql_query
        result = run_sql_query("DROP TABLE dbo.Staff")
        assert result["success"] is False

    def test_rejects_update(self):
        from tools.dynamic_sql import run_sql_query
        result = run_sql_query("UPDATE dbo.Staff SET Name='hacked' WHERE 1=1")
        assert result["success"] is False

    def test_rejects_exec(self):
        from tools.dynamic_sql import run_sql_query
        result = run_sql_query("EXEC sp_executesql @sql")
        assert result["success"] is False

    def test_rejects_non_select(self):
        from tools.dynamic_sql import run_sql_query
        result = run_sql_query("WAITFOR DELAY '00:00:05'")
        assert result["success"] is False
        assert "SELECT" in result["error"]

    def test_rejects_comment_bypass_line(self):
        """Attacker hides DROP after a line comment."""
        from tools.dynamic_sql import run_sql_query
        result = run_sql_query("SELECT 1\n--\nDROP TABLE users")
        assert result["success"] is False

    def test_rejects_comment_bypass_block(self):
        """Attacker hides DROP inside a block comment prefix."""
        from tools.dynamic_sql import run_sql_query
        result = run_sql_query("SELECT 1; /* */ DROP TABLE users")
        assert result["success"] is False

    def test_rejects_union_with_sys(self):
        from tools.dynamic_sql import run_sql_query
        result = run_sql_query(
            "SELECT 1 UNION SELECT name FROM sys.tables"
        )
        assert result["success"] is False

    def test_rejects_openrowset(self):
        from tools.dynamic_sql import run_sql_query
        result = run_sql_query(
            "SELECT * FROM OPENROWSET('SQLNCLI', 'Server=evil;', 'SELECT 1')"
        )
        assert result["success"] is False
