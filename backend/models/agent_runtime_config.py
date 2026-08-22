from __future__ import annotations

from pydantic import BaseModel, Field


class AgentModelRouteInfo(BaseModel):
    role: str
    provider: str
    model: str
    thinking_enabled: bool = False


class AgentPromptInfo(BaseModel):
    name: str
    version: str
    prompt_id: str


class AgentRuntimeConfigResponse(BaseModel):
    model_routes: list[AgentModelRouteInfo] = Field(default_factory=list)
    prompts: list[AgentPromptInfo] = Field(default_factory=list)
    planner_context_max_chars: int = Field(ge=1)
    chat_context_max_chars: int = Field(ge=1)
    document_content_trust: str = "untrusted_data"
    planner_argument_policy: str = "tool_schema_allowlist"
    write_confirmation_required: bool = True


__all__ = [
    "AgentModelRouteInfo",
    "AgentPromptInfo",
    "AgentRuntimeConfigResponse",
]
