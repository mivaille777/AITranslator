from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.models.quick_actions import ReadingContextPayload

AgentToolEffect = Literal["read", "compute", "write"]


class AgentToolDefinition(BaseModel):
    name: str
    title: str
    description: str
    category: str
    effect: AgentToolEffect
    requires_reading_context: bool = True
    requires_confirmation: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)


class AgentToolCatalogResponse(BaseModel):
    tools: list[AgentToolDefinition]


class AgentToolExecuteRequest(ReadingContextPayload):
    style: str = Field(default="academic", min_length=1, max_length=64)
    user_note: str = Field(default="", max_length=20_000)
    ai_content: str = Field(default="", max_length=30_000)
    ai_action: str = Field(default="", max_length=128)
    conversation_id: str = Field(default="", max_length=128)
    request_id: int = Field(default=0, ge=0)


class AgentToolExecuteResponse(BaseModel):
    tool_name: str
    output_text: str
    effect: AgentToolEffect
    provider: str = ""
    model: str = ""
    request_id: int = 0
    data: dict[str, Any] = Field(default_factory=dict)
