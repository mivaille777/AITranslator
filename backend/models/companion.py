from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.models.quick_actions import ReadingContextPayload


class CompanionHandoffRequest(ReadingContextPayload):
    ai_content: str = Field(default="", max_length=30_000)
    ai_action: str = Field(default="", max_length=128)
    suggested_prompt: str = Field(default="", max_length=2_000)


class CompanionHandoffResponse(ReadingContextPayload):
    revision: int
    handoff_id: str
    created_at: str
    ai_content: str = ""
    ai_action: str = ""
    suggested_prompt: str = ""


class CompanionHandoffEnvelope(BaseModel):
    handoff: CompanionHandoffResponse | None = None


class CompanionDismissRequest(BaseModel):
    handoff_id: str = Field(default="", max_length=128)


CompanionChatRole = Literal["user", "assistant"]


class CompanionChatMessage(BaseModel):
    role: CompanionChatRole
    content: str = Field(min_length=1, max_length=30_000)


class CompanionChatRequest(ReadingContextPayload):
    session_id: str = Field(min_length=1, max_length=128)
    user_message: str = Field(min_length=1, max_length=20_000)
    history: list[CompanionChatMessage] = Field(default_factory=list, max_length=32)
    request_id: int = Field(default=0, ge=0)


class CompanionChatResponse(BaseModel):
    session_id: str
    user_message: str
    output_text: str
    provider: str
    model: str
    request_id: int


class CompanionChatStatusResponse(BaseModel):
    available: bool
    provider: str = ""
    model: str = ""
    detail: str = ""
