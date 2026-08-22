from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _run_id() -> str:
    return f"run-{uuid4().hex}"


def _trace_id() -> str:
    return f"trace-{uuid4().hex}"


class AgentState(BaseModel):
    """Shared state passed through the agent execution lifecycle."""

    run_id: str = Field(default_factory=_run_id)
    trace_id: str = Field(default_factory=_trace_id)
    session_id: str | None = None
    user_input: str = ""
    selected_text: str = ""
    browser_context: dict[str, Any] = Field(default_factory=dict)
    intent: str | None = None
    planned_action: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    response: dict[str, Any] = Field(default_factory=dict)
    ui_mode: str = "assistant"
