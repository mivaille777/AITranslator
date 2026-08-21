from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ConversationMessageStatus = Literal["complete", "streaming", "cancelled", "error"]
ConversationRole = Literal["user", "assistant"]


class ConversationMessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    request_id: int
    role: ConversationRole
    content: str
    status: ConversationMessageStatus
    provider: str = ""
    model: str = ""
    error_code: str = ""
    created_at: str
    updated_at: str


class ConversationSummaryResponse(BaseModel):
    conversation_id: str
    session_id: str
    title: str
    created_at: str
    updated_at: str
    provider: str = ""
    model: str = ""
    resource_title: str = ""
    section_heading: str = ""
    source_kind: str = ""


class ConversationDetailResponse(ConversationSummaryResponse):
    source_text: str = ""
    translated_text: str = ""
    source_language: str = "auto"
    target_language: str = "zh-CN"
    resource_url: str = ""
    context_before: str = ""
    context_after: str = ""
    messages: list[ConversationMessageResponse] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummaryResponse]


class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ConversationDeleteResponse(BaseModel):
    deleted: bool
    conversation_id: str
