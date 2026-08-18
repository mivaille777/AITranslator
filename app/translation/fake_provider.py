"""Deterministic offline translation provider for development and tests."""

from __future__ import annotations

from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider

TEST_TRANSLATION_PREFIX = "[TEST TRANSLATION] "


class FakeTranslationProvider(TranslationProvider):
    """Return a deterministic marker without network access."""

    def __init__(self, prefix: str = TEST_TRANSLATION_PREFIX) -> None:
        self.prefix = prefix

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return TranslationResult(
            source_text=request.source_text,
            translated_text=f"{self.prefix}{request.source_text}",
            source_language=request.source_language,
            target_language=request.target_language,
            provider="fake",
            request_id=request.request_id,
        )
