from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentEventType(str, Enum):
    AGENT_START = "agent_start"
    CONTEXT_READY = "context_ready"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    AGENT_END = "agent_end"


class AgentEvent(BaseModel):
    event_type: AgentEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
