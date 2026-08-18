"""Translation provider abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.translation import TranslationRequest, TranslationResult
from app.translation.errors import (
    TextNormalizationError,
    TranslationError,
    WebTranslationError,
)


class TranslationProvider(ABC):
    """Translate a request without exposing provider SDK details upstream."""

    @abstractmethod
    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate one request or raise TranslationError."""


__all__ = [
    "TextNormalizationError",
    "TranslationError",
    "WebTranslationError",
    "TranslationProvider",
    "TranslationRequest",
    "TranslationResult",
]
