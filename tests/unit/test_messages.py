"""
Unit tests for message models (Pydantic models + enums).
"""
import pytest


class TestWebSocketMessageType:
    """WebSocket protocol message types."""

    def test_all_types_defined(self):
        from models.messages import WebSocketMessageType

        assert WebSocketMessageType.AGENT == "AGENT"
        assert WebSocketMessageType.SAFETY == "SAFETY"
        assert WebSocketMessageType.DONE == "DONE"
        assert WebSocketMessageType.SUGGESTIONS == "SUGGESTIONS"
        assert WebSocketMessageType.ERROR == "ERROR"


class TestSafetyResult:
    """Safety result Pydantic model."""

    def test_defaults(self):
        from models.messages import SafetyResult

        sr = SafetyResult()
        assert sr.input_safe is True
        assert sr.output_safe is True
        assert sr.categories == {}
        assert sr.flagged == []
        assert sr.available is False

    def test_custom_values(self):
        from models.messages import SafetyResult

        sr = SafetyResult(
            input_safe=False,
            output_safe=True,
            categories={"hate": 6},
            flagged=["Hate Speech"],
            available=True,
        )
        assert sr.input_safe is False
        assert sr.flagged == ["Hate Speech"]

    def test_serialization(self):
        from models.messages import SafetyResult

        sr = SafetyResult(flagged=["Violence"])
        data = sr.model_dump()
        assert isinstance(data, dict)
        assert data["flagged"] == ["Violence"]


class TestOrchestratorResult:
    """Orchestrator result Pydantic model."""

    def test_minimal(self):
        from models.messages import OrchestratorResult

        result = OrchestratorResult(
            agent_name="Operations Agent",
            response="All good.",
        )
        assert result.agent_name == "Operations Agent"
        assert result.response == "All good."
        assert result.suggestions == []
        assert result.safety.input_safe is True

    def test_with_suggestions(self):
        from models.messages import OrchestratorResult

        result = OrchestratorResult(
            agent_name="Forecasting Agent",
            response="Surge expected.",
            suggestions=["Start batch prep?", "Check staffing levels?"],
        )
        assert len(result.suggestions) == 2

    def test_serialization_roundtrip(self):
        from models.messages import OrchestratorResult, SafetyResult

        result = OrchestratorResult(
            agent_name="Diagnostics Agent",
            response="Cold bar is bottlenecked.",
            safety=SafetyResult(available=True, input_safe=True, output_safe=True),
        )
        data = result.model_dump()
        restored = OrchestratorResult(**data)
        assert restored.agent_name == result.agent_name
        assert restored.safety.available is True


class TestStreamEvent:
    """Stream event named tuple."""

    def test_create_agent_event(self):
        from models.messages import StreamEvent

        evt = StreamEvent(type="agent", data="Operations Agent")
        assert evt.type == "agent"
        assert evt.data == "Operations Agent"

    def test_create_done_event(self):
        from models.messages import StreamEvent

        evt = StreamEvent(type="done")
        assert evt.type == "done"
        assert evt.data is None
