from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from backend.models.quick_actions import ReadingContextPayload

AgentToolEffect = Literal["read", "compute", "write"]
AgentRunStatus = Literal["completed", "confirmation_required"]
AgentPlanAction = Literal["answer", "tool"]


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


class AgentPlan(BaseModel):
    action: AgentPlanAction
    tool_name: str = Field(default="", max_length=128)
    user_visible_reason: str = Field(default="", max_length=500)
    arguments: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_tool_action(self) -> "AgentPlan":
        if self.action == "tool" and not self.tool_name.strip():
            raise ValueError("Agent tool plan requires tool_name.")
        if self.action == "answer":
            self.tool_name = ""
            self.arguments = {}
        return self


class AgentRunRequest(ReadingContextPayload):
    session_id: str = Field(default="agent-session", min_length=1, max_length=128)
    user_message: str = Field(min_length=1, max_length=20_000)
    style: str = Field(default="academic", min_length=1, max_length=64)
    conversation_id: str = Field(default="", max_length=128)
    confirmed_write_tools: list[str] = Field(default_factory=list, max_length=16)
    request_id: int = Field(default=0, ge=0)


class AgentRunResponse(BaseModel):
    status: AgentRunStatus
    plan: AgentPlan
    output_text: str = ""
    provider: str = ""
    model: str = ""
    request_id: int = 0
    tool_result: AgentToolExecuteResponse | None = None
