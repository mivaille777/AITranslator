from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ResearchSourceFamily = Literal["browser", "pdf", "word", "desktop", "other"]
ResearchIdentityQuality = Literal["locator", "title", "note"]


class ResearchSourceSummaryResponse(BaseModel):
    source_id: str
    display_title: str
    resource_url: str = ""
    resource_locator: str = ""
    source_kind: str = ""
    source_family: ResearchSourceFamily = "other"
    identity_quality: ResearchIdentityQuality = "note"
    note_count: int = 0
    section_count: int = 0
    linked_conversation_count: int = 0
    annotation_count: int = 0
    ai_evidence_count: int = 0
    updated_at: str = ""


class ResearchSourceSectionResponse(BaseModel):
    section_id: str
    heading: str
    note_count: int = 0
    linked_conversation_count: int = 0
    annotation_count: int = 0
    ai_evidence_count: int = 0
    updated_at: str = ""


class ResearchSourceProfileResponse(ResearchSourceSummaryResponse):
    sections: list[ResearchSourceSectionResponse]


class ResearchNoteDetailResponse(BaseModel):
    note_id: str
    source_id: str
    created_at: str
    updated_at: str
    display_title: str
    excerpt: str
    resource_url: str = ""
    resource_title: str = ""
    section_heading: str = ""
    source_text: str = ""
    translated_text: str = ""
    context_before: str = ""
    context_after: str = ""
    source_kind: str = ""
    ai_content: str = ""
    ai_action: str = ""
    user_note: str = ""
    conversation_id: str = ""


class ResearchWorkspaceResponse(BaseModel):
    total: int
    sources: list[ResearchSourceSummaryResponse]
    notes: list[ResearchNoteDetailResponse]


class ResearchNoteUpdateRequest(BaseModel):
    user_note: str = Field(default="", max_length=20_000)


class ResearchNoteDeleteResponse(BaseModel):
    deleted: bool
    note_id: str
