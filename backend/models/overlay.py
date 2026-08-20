from typing import Literal

from pydantic import BaseModel, Field

OverlayPhase = Literal["hidden", "loading", "ready", "error"]


class OverlayStateResponse(BaseModel):
    revision: int
    visible: bool
    phase: OverlayPhase
    context_id: str = ""
    source_text: str = ""
    translated_text: str = ""
    source_language: str = "auto"
    target_language: str = "zh-CN"
    provider: str = ""
    message: str = ""


class OverlayLoadingRequest(BaseModel):
    context_id: str = Field(min_length=1, max_length=128)
    source_text: str = Field(min_length=1, max_length=20_000)
    source_language: str = "auto"
    target_language: str = "zh-CN"


class OverlayPresentRequest(OverlayLoadingRequest):
    translated_text: str = Field(min_length=1, max_length=50_000)
    provider: str = "unknown"


class OverlayErrorRequest(BaseModel):
    context_id: str = Field(min_length=1, max_length=128)
    source_text: str = Field(default="", max_length=20_000)
    source_language: str = "auto"
    target_language: str = "zh-CN"
    message: str = Field(default="Translation failed", max_length=500)
