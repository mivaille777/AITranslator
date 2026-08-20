from __future__ import annotations

from app.models.translation import TranslationResult
from app.translation.manager import TranslationManager


class TranslationService:
    """Application boundary for deterministic text translation.

    The service deliberately reuses the mature legacy translation core while
    keeping FastAPI, React, and desktop-runtime concerns outside that core.
    """

    def __init__(self, manager: TranslationManager | None = None) -> None:
        self._manager = manager or TranslationManager()

    @property
    def provider_name(self) -> str:
        return self._manager.provider_name

    @property
    def default_source_language(self) -> str:
        return self._manager.default_source_language

    @property
    def default_target_language(self) -> str:
        return self._manager.default_target_language

    def translate(
        self,
        source_text: str,
        *,
        source_language: str = "auto",
        target_language: str = "zh-CN",
        request_id: int = 0,
    ) -> TranslationResult:
        return self._manager.translate(
            source_text,
            source_language=source_language,
            target_language=target_language,
            request_id=request_id,
        )

    def close(self) -> None:
        self._manager.close()
