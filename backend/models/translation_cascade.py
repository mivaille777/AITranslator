from typing import Literal

from pydantic import BaseModel, Field

from backend.models.translation import TranslationApiRequest

TranslationAttemptStatus = Literal["success", "unavailable"]
TranslationProviderMode = Literal["auto", "youdao_web", "google_web", "ai"]


class TranslationCascadeRequest(TranslationApiRequest):
    provider_mode: TranslationProviderMode = "auto"


class TranslationCascadeAttempt(BaseModel):
    provider: str
    status: TranslationAttemptStatus


class TranslationCascadeResponse(BaseModel):
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    provider: str
    model: str = ""
    request_id: int = 0
    fallback_level: int = Field(ge=0, le=2)
    notice: str = ""
    attempts: list[TranslationCascadeAttempt] = Field(default_factory=list)
