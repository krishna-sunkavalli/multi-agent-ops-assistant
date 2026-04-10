"""Typed message models for Ops Assistant WebSocket protocol and orchestration."""

from enum import StrEnum
from typing import NamedTuple

from pydantic import BaseModel, Field


class WebSocketMessageType(StrEnum):
    """Wire-protocol markers sent over the WebSocket connection."""

    AGENT = "AGENT"
    SAFETY = "SAFETY"
    DONE = "DONE"
    SUGGESTIONS = "SUGGESTIONS"
    ERROR = "ERROR"


class StreamEvent(NamedTuple):
    """Event emitted during streamed orchestration."""

    type: str  # "agent" | "safety" | "delta" | "suggestions" | "done"
    data: str | None = None


class SafetyResult(BaseModel):
    """Content safety guardrail outcome."""

    input_safe: bool = True
    output_safe: bool = True
    categories: dict = Field(default_factory=dict)
    flagged: list[str] = Field(default_factory=list)
    available: bool = False


class OrchestratorResult(BaseModel):
    """Typed return value from OpsAssistantOrchestrator.process_message()."""

    agent_name: str
    response: str
    suggestions: list[str] = Field(default_factory=list)
    safety: SafetyResult = Field(default_factory=SafetyResult)
