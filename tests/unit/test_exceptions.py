"""
Unit tests for exception hierarchy.
"""
import pytest


class TestExceptionHierarchy:
    """All custom exceptions inherit from OpsAssistantError."""

    def test_base_exception(self):
        from agents.exceptions import OpsAssistantError

        err = OpsAssistantError("test")
        assert isinstance(err, Exception)
        assert str(err) == "test"

    def test_routing_error(self):
        from agents.exceptions import AgentRoutingError, OpsAssistantError

        err = AgentRoutingError("bad route")
        assert isinstance(err, OpsAssistantError)

    def test_not_found_error(self):
        from agents.exceptions import AgentNotFoundError, OpsAssistantError

        err = AgentNotFoundError("missing agent")
        assert isinstance(err, OpsAssistantError)

    def test_execution_error(self):
        from agents.exceptions import AgentExecutionError, OpsAssistantError

        err = AgentExecutionError("run failed")
        assert isinstance(err, OpsAssistantError)

    def test_safety_violation(self):
        from agents.exceptions import ContentSafetyViolation, OpsAssistantError

        err = ContentSafetyViolation("blocked")
        assert isinstance(err, OpsAssistantError)

    def test_config_error(self):
        from agents.exceptions import AgentConfigurationError, OpsAssistantError

        err = AgentConfigurationError("bad config")
        assert isinstance(err, OpsAssistantError)
