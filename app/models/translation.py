"""Translation request and result data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    """Normalized input passed to a translation provider."""

    source_text: str
    source_language: str = "auto"
    target_language: str = "zh-CN"
    request_id: int = 0


@dataclass(frozen=True, slots=True)
class TranslationResult:
    """Provider-independent translation output."""

    source_text: str
    translated_text: str
    source_language: str = "auto"
    target_language: str = "zh-CN"
    provider: str = "unknown"
    request_id: int = 0

    @property
    def text(self) -> str:
        """Short alias for UI code that only needs the translated text."""

        return self.translated_text
