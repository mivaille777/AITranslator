from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """Shared state passed through the agent execution lifecycle."""

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
