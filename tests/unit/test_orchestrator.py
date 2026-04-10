"""
Unit tests for the orchestrator — keyword overrides, suggestion parsing,
rate limit detection, and friendly error formatting.
"""
import pytest


# ── Tests: keyword overrides ─────────────────────────────────────────

class TestKeywordOverrides:
    """Deterministic keyword overrides bypass LLM triage."""

    @pytest.mark.parametrize("msg", [
        "yes", "Yes", "YES", "do it", "go ahead", "proceed",
        "confirm", "approved", "sure", "  yes  ", "yes!",
    ])
    def test_confirmation_routes_to_diagnostics(self, msg):
        from orchestrator import _KEYWORD_OVERRIDES

        matched = None
        for pattern, route in _KEYWORD_OVERRIDES:
            if pattern.search(msg):
                matched = route
                break
        assert matched == "diagnostics", f"'{msg}' should route to diagnostics"

    @pytest.mark.parametrize("msg", [
        "How are we doing?",
        "What's the cold bar status?",
        "yes we should move Sarah",
        "Move Mike to hot bar",
        "Show me the forecast",
    ])
    def test_non_bare_confirmation_not_overridden(self, msg):
        from orchestrator import _KEYWORD_OVERRIDES

        matched = None
        for pattern, route in _KEYWORD_OVERRIDES:
            if pattern.search(msg):
                matched = route
                break
        assert matched is None, f"'{msg}' should NOT match keyword overrides"


# ── Tests: suggestion extraction ─────────────────────────────────────

class TestExtractSuggestions:
    """Parse [FOLLOWUP:[...]] from response text."""

    def test_extracts_suggestions(self):
        from orchestrator import _extract_suggestions

        text = 'Cold bar is at 120%. [FOLLOWUP:["Move staff to cold bar?", "Check forecast?"]]'
        clean, suggestions = _extract_suggestions(text)

        assert "FOLLOWUP" not in clean
        assert clean == "Cold bar is at 120%."
        assert suggestions == ["Move staff to cold bar?", "Check forecast?"]

    def test_no_suggestions_returns_empty(self):
        from orchestrator import _extract_suggestions

        text = "Everything is fine."
        clean, suggestions = _extract_suggestions(text)

        assert clean == "Everything is fine."
        assert suggestions == []

    def test_invalid_json_returns_empty(self):
        from orchestrator import _extract_suggestions

        text = 'Response [FOLLOWUP:[not valid json]]'
        clean, suggestions = _extract_suggestions(text)

        assert suggestions == []

    def test_strips_trailing_whitespace(self):
        from orchestrator import _extract_suggestions

        text = 'Answer here   [FOLLOWUP:["Follow up?"]]'
        clean, _ = _extract_suggestions(text)

        assert clean == "Answer here"


# ── Tests: rate limit detection ──────────────────────────────────────

class TestRateLimitDetection:
    """Detect 429 rate-limit errors from exception messages."""

    def test_detects_429(self):
        from orchestrator import _is_rate_limit

        assert _is_rate_limit(Exception("Error 429: Too Many Requests"))

    def test_detects_too_many_requests(self):
        from orchestrator import _is_rate_limit

        assert _is_rate_limit(Exception("too_many_requests"))

    def test_detects_rate_limit_text(self):
        from orchestrator import _is_rate_limit

        assert _is_rate_limit(Exception("Rate limit exceeded"))

    def test_non_rate_limit(self):
        from orchestrator import _is_rate_limit

        assert not _is_rate_limit(Exception("Connection timeout"))
        assert not _is_rate_limit(Exception("Internal server error"))


# ── Tests: friendly error formatting ─────────────────────────────────

class TestFriendlyError:
    """User-facing error messages strip internal details."""

    def test_extracts_retry_after(self):
        from orchestrator import _friendly_error

        err = Exception("Rate limit exceeded. Retry after 30 seconds.")
        msg = _friendly_error(err)
        assert "retry after 30s" in msg

    def test_429_message(self):
        from orchestrator import _friendly_error

        err = Exception("429 Too Many Requests")
        msg = _friendly_error(err)
        assert "rate limit" in msg.lower()

    def test_truncates_long_messages(self):
        from orchestrator import _friendly_error

        err = Exception("A" * 500)
        msg = _friendly_error(err)
        assert len(msg) <= 120

    def test_none_returns_unknown(self):
        from orchestrator import _friendly_error

        assert _friendly_error(None) == "unknown error"


# ── Tests: display names ─────────────────────────────────────────────

class TestDisplayNames:
    """Display names map short names to user-friendly labels."""

    def test_all_specialists_have_display_names(self):
        from orchestrator import DISPLAY_NAMES

        expected = {"operations", "diagnostics", "forecasting", "safety", "quality"}
        assert set(DISPLAY_NAMES.keys()) == expected

    def test_names_are_human_readable(self):
        from orchestrator import DISPLAY_NAMES

        for name, display in DISPLAY_NAMES.items():
            assert "Agent" in display
