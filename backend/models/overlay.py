from typing import Literal

from pydantic import BaseModel, Field

OverlayMode = Literal["assistant", "translation"]
OverlayPhase = Literal["hidden", "idle", "loading", "ready", "error"]


class OverlayReadingContext(BaseModel):
    resource_url: str = Field(default="", max_length=4096)
    resource_title: str = Field(default="", max_length=1024)
    section_heading: str = Field(default="", max_length=1024)
    context_before: str = Field(default="", max_length=4000)
    context_after: str = Field(default="", max_length=4000)
    source_kind: str = Field(default="browser_selection", max_length=128)


class OverlayStateResponse(OverlayReadingContext):
    revision: int
    visible: bool
    mode: OverlayMode = "assistant"
    phase: OverlayPhase
    context_id: str = ""
    source_text: str = ""
    translated_text: str = ""
    source_language: str = "auto"
    target_language: str = "zh-CN"
    provider: str = ""
    message: str = ""
    translation_notice: str = ""
    companion_conversation_id: str = ""


class OverlayAssistantRequest(OverlayReadingContext):
    context_id: str = Field(min_length=1, max_length=128)
    source_text: str = Field(min_length=1, max_length=20_000)
    source_language: str = "auto"
    target_language: str = "zh-CN"


class OverlayLoadingRequest(OverlayReadingContext):
    context_id: str = Field(min_length=1, max_length=128)
    source_text: str = Field(min_length=1, max_length=20_000)
    source_language: str = "auto"
    target_language: str = "zh-CN"


class OverlayPresentRequest(OverlayLoadingRequest):
    translated_text: str = Field(min_length=1, max_length=50_000)
    provider: str = "unknown"
    translation_notice: str = Field(default="", max_length=500)


class OverlayErrorRequest(OverlayReadingContext):
    context_id: str = Field(min_length=1, max_length=128)
    source_text: str = Field(default="", max_length=20_000)
    source_language: str = "auto"
    target_language: str = "zh-CN"
    message: str = Field(default="Translation failed", max_length=500)


class OverlayCompanionBindingRequest(BaseModel):
    context_id: str = Field(min_length=1, max_length=128)
    conversation_id: str = Field(default="", max_length=128)
