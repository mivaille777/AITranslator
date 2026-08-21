from __future__ import annotations

from threading import RLock

from app.models.translation import TranslationResult
from app.translation.manager import TranslationManager

SUPPORTED_TRANSLATION_PROVIDERS = {"google_web", "youdao_web"}


class TranslationService:
    """Application boundary for deterministic text translation.

    The service deliberately reuses the mature legacy translation core while
    keeping FastAPI, React, and desktop-runtime concerns outside that core.
    """

    def __init__(self, manager: TranslationManager | None = None) -> None:
        self._manager = manager or TranslationManager()
        self._lock = RLock()

    @property
    def provider_name(self) -> str:
        with self._lock:
            return self._manager.provider_name

    @property
    def default_source_language(self) -> str:
        with self._lock:
            return self._manager.default_source_language

    @property
    def default_target_language(self) -> str:
        with self._lock:
            return self._manager.default_target_language

    def select_provider(self, provider: str) -> str:
        normalized = str(provider).strip().lower().replace("-", "_")
        aliases = {
            "google": "google_web",
            "google_web": "google_web",
            "youdao": "youdao_web",
            "youdao_web": "youdao_web",
        }
        selected = aliases.get(normalized, normalized)
        if selected not in SUPPORTED_TRANSLATION_PROVIDERS:
            raise ValueError(f"unsupported translation provider: {provider}")

        with self._lock:
            if self._manager.provider_name == selected:
                return self._manager.provider_name

            config = self._manager.config_manager
            data = getattr(config, "_data", None)
            if not isinstance(data, dict):
                raise RuntimeError("translation configuration is not mutable at runtime")
            section = data.setdefault("translation", {})
            if not isinstance(section, dict):
                section = {}
                data["translation"] = section
            section["provider"] = selected
            self._manager.configure_provider(force=True)
            return self._manager.provider_name

    def translate(
        self,
        source_text: str,
        *,
        source_language: str = "auto",
        target_language: str = "zh-CN",
        request_id: int = 0,
    ) -> TranslationResult:
        with self._lock:
            return self._manager.translate(
                source_text,
                source_language=source_language,
                target_language=target_language,
                request_id=request_id,
            )

    def close(self) -> None:
        with self._lock:
            self._manager.close()
