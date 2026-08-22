from typing import Literal

from pydantic import BaseModel, Field, field_validator

TranslationProviderName = Literal["google_web", "youdao_web"]


class TranslationApiRequest(BaseModel):
    source_text: str = Field(min_length=1)
    source_language: str = "auto"
    target_language: str = "zh-CN"
    request_id: int = Field(default=0, ge=0)

    @field_validator("source_language", "target_language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("language code must not be empty")
        return normalized


class TranslationApiResponse(BaseModel):
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    provider: str
    request_id: int


class TranslationProviderSelectionRequest(BaseModel):
    provider: TranslationProviderName


class TranslationStatusResponse(BaseModel):
    provider: str
    source_language: str
    target_language: str
