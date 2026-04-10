"""Domain-specific exceptions for Ops Assistant agent operations."""


class OpsAssistantError(Exception):
    """Base exception for all Ops Assistant errors."""


class AgentRoutingError(OpsAssistantError):
    """Raised when triage cannot determine a valid specialist route."""


class AgentNotFoundError(OpsAssistantError):
    """Raised when a requested agent is not in the registry."""


class AgentExecutionError(OpsAssistantError):
    """Raised when an agent run fails after exhausting retries."""


class ContentSafetyViolation(OpsAssistantError):
    """Raised when input or output is flagged by content safety guardrails."""


class AgentConfigurationError(OpsAssistantError):
    """Raised when agent YAML config references unknown tools or invalid settings."""
