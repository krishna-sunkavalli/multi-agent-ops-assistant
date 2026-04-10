"""
Unit tests for content safety guardrails.

Tests the check_safety function with mocked Azure Content Safety client
to validate blocking logic, threshold behavior, and graceful degradation.
"""
import sys
import pytest
from unittest.mock import patch, MagicMock


# ── Helpers ──────────────────────────────────────────────────────────

def _make_category(category: str, severity: int):
    """Create a mock category analysis result."""
    mock = MagicMock()
    mock.category = category
    mock.severity = severity
    return mock


def _make_response(categories: list):
    """Create a mock AnalyzeTextResponse."""
    mock = MagicMock()
    mock.categories_analysis = categories
    return mock


# ── Reset module state between tests ─────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_content_safety():
    """Reset the lazy-init state so each test starts fresh."""
    import guardrails.content_safety as cs
    cs._client = None
    cs._initialized = False
    yield
    cs._client = None
    cs._initialized = False


@pytest.fixture(autouse=True)
def _mock_contentsafety_models():
    """Ensure azure.ai.contentsafety.models is importable."""
    mock_models = MagicMock()
    mock_models.AnalyzeTextOptions = lambda text: MagicMock(text=text)
    with patch.dict('sys.modules', {
        'azure.ai.contentsafety': MagicMock(),
        'azure.ai.contentsafety.models': mock_models,
    }):
        yield


# ── Tests: client unavailable (graceful degradation) ─────────────────

class TestCheckSafetyNoClient:
    """When Content Safety client is unavailable, guardrails pass-through."""

    def test_returns_safe_when_client_unavailable(self):
        from guardrails.content_safety import check_safety

        # Force client to be None (endpoint not set)
        import guardrails.content_safety as cs
        cs._initialized = True
        cs._client = None

        result = check_safety("any text")

        assert result["safe"] is True
        assert result["available"] is False
        assert result["flagged"] == []
        assert result["categories"] == {}

    def test_returns_safe_when_init_fails(self):
        from guardrails.content_safety import check_safety

        # Simulate init failure — _initialized=True but _client=None
        import guardrails.content_safety as cs
        cs._initialized = True
        cs._client = None

        result = check_safety("I will harm someone")

        assert result["safe"] is True
        assert result["available"] is False


# ── Tests: client available, safe content ────────────────────────────

class TestCheckSafetySafeContent:
    """Content below threshold should return safe=True."""

    def test_all_zeros_is_safe(self):
        from guardrails.content_safety import check_safety
        import guardrails.content_safety as cs

        mock_client = MagicMock()
        mock_client.analyze_text.return_value = _make_response([
            _make_category("Hate", 0),
            _make_category("SelfHarm", 0),
            _make_category("Sexual", 0),
            _make_category("Violence", 0),
        ])
        cs._initialized = True
        cs._client = mock_client

        result = check_safety("How are we doing today?")

        assert result["safe"] is True
        assert result["available"] is True
        assert result["flagged"] == []
        assert result["categories"]["hate"] == 0
        assert result["categories"]["violence"] == 0

    def test_below_threshold_is_safe(self):
        from guardrails.content_safety import check_safety
        import guardrails.content_safety as cs

        mock_client = MagicMock()
        mock_client.analyze_text.return_value = _make_response([
            _make_category("Hate", 2),
            _make_category("SelfHarm", 0),
            _make_category("Sexual", 0),
            _make_category("Violence", 2),
        ])
        cs._initialized = True
        cs._client = mock_client

        # Default threshold is 4 — severity 2 should pass
        result = check_safety("slightly edgy content")

        assert result["safe"] is True
        assert result["flagged"] == []


# ── Tests: client available, unsafe content ──────────────────────────

class TestCheckSafetyUnsafeContent:
    """Content at or above threshold should return safe=False."""

    def test_at_threshold_is_blocked(self):
        from guardrails.content_safety import check_safety
        import guardrails.content_safety as cs

        mock_client = MagicMock()
        mock_client.analyze_text.return_value = _make_response([
            _make_category("Hate", 0),
            _make_category("SelfHarm", 0),
            _make_category("Sexual", 0),
            _make_category("Violence", 4),
        ])
        cs._initialized = True
        cs._client = mock_client

        result = check_safety("violent content", threshold=4)

        assert result["safe"] is False
        assert "Violence" in result["flagged"]

    def test_above_threshold_is_blocked(self):
        from guardrails.content_safety import check_safety
        import guardrails.content_safety as cs

        mock_client = MagicMock()
        mock_client.analyze_text.return_value = _make_response([
            _make_category("Hate", 6),
            _make_category("SelfHarm", 0),
            _make_category("Sexual", 0),
            _make_category("Violence", 6),
        ])
        cs._initialized = True
        cs._client = mock_client

        result = check_safety("hate and violence")

        assert result["safe"] is False
        assert "Hate Speech" in result["flagged"]
        assert "Violence" in result["flagged"]

    def test_custom_lower_threshold(self):
        from guardrails.content_safety import check_safety
        import guardrails.content_safety as cs

        mock_client = MagicMock()
        mock_client.analyze_text.return_value = _make_response([
            _make_category("Hate", 0),
            _make_category("SelfHarm", 2),
            _make_category("Sexual", 0),
            _make_category("Violence", 0),
        ])
        cs._initialized = True
        cs._client = mock_client

        # Stricter threshold
        result = check_safety("self harm reference", threshold=2)

        assert result["safe"] is False
        assert "Self-Harm" in result["flagged"]

    def test_multiple_categories_flagged(self):
        from guardrails.content_safety import check_safety
        import guardrails.content_safety as cs

        mock_client = MagicMock()
        mock_client.analyze_text.return_value = _make_response([
            _make_category("Hate", 6),
            _make_category("SelfHarm", 4),
            _make_category("Sexual", 6),
            _make_category("Violence", 4),
        ])
        cs._initialized = True
        cs._client = mock_client

        result = check_safety("terrible content")

        assert result["safe"] is False
        assert len(result["flagged"]) == 4


# ── Tests: exception handling ────────────────────────────────────────

class TestCheckSafetyExceptionHandling:
    """API errors should fail open (return safe=True)."""

    def test_api_exception_returns_safe(self):
        from guardrails.content_safety import check_safety
        import guardrails.content_safety as cs

        mock_client = MagicMock()
        mock_client.analyze_text.side_effect = Exception("API timeout")
        cs._initialized = True
        cs._client = mock_client

        result = check_safety("any text")

        assert result["safe"] is True
