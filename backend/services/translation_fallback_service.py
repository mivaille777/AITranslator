from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.ai.gateway import LLMGateway
from app.infrastructure.settings import SettingsManager
from app.models.translation import TranslationRequest
from app.translation.errors import TextNormalizationError, TranslationError
from app.translation.google_web_provider import GoogleWebTranslationProvider
from app.translation.normalizer import TextNormalizer
from app.translation.youdao_web_provider import YoudaoWebTranslationProvider


@dataclass(frozen=True, slots=True)
class TranslationAttempt:
    provider: str
    status: str


@dataclass(frozen=True, slots=True)
class TranslationCascadeResult:
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    provider: str
    model: str
    request_id: int
    fallback_level: int
    notice: str
    attempts: tuple[TranslationAttempt, ...]


class TranslationFallbackService:
    """Deterministic translation cascade: Youdao -> Google -> AI.

    Provider selection here is request-local. It never mutates the user's
    persisted translation provider setting and therefore cannot race with the
    normal Translation workspace provider selector.
    """

    def __init__(
        self,
        *,
        settings_factory: Callable[[], SettingsManager] = SettingsManager,
        llm_gateway: LLMGateway | None = None,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        self._settings_factory = settings_factory
        self._llm_gateway = llm_gateway or LLMGateway()
        self._normalizer = normalizer or TextNormalizer()

    @staticmethod
    def _close_provider(provider: object | None) -> None:
        if provider is None:
            return
        close = getattr(provider, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        source_text: str,
        *,
        source_language: str,
        target_language: str,
        request_id: int,
    ) -> TranslationRequest:
        normalized = self._normalizer.normalize(source_text)
        return TranslationRequest(
            source_text=normalized,
            source_language=str(source_language or "auto").strip() or "auto",
            target_language=str(target_language or "zh-CN").strip() or "zh-CN",
            request_id=max(0, int(request_id or 0)),
        )

    def translate(
        self,
        source_text: str,
        *,
        source_language: str = "auto",
        target_language: str = "zh-CN",
        request_id: int = 0,
    ) -> TranslationCascadeResult:
        request = self._request(
            source_text,
            source_language=source_language,
            target_language=target_language,
            request_id=request_id,
        )
        attempts: list[TranslationAttempt] = []

        provider_factories = (
            (
                "youdao_web",
                lambda: YoudaoWebTranslationProvider(
                    config_manager=self._settings_factory(),
                ),
            ),
            (
                "google_web",
                lambda: GoogleWebTranslationProvider(
                    config_manager=self._settings_factory(),
                ),
            ),
        )

        for fallback_level, (provider_name, factory) in enumerate(provider_factories):
            provider = None
            try:
                provider = factory()
                result = provider.translate(request)
                if not result.translated_text.strip():
                    raise TranslationError("translated text is empty")
                attempts.append(TranslationAttempt(provider_name, "success"))
                notice = ""
                if fallback_level == 1:
                    notice = "有道翻译当前不可用，已自动切换到 Google 翻译。"
                return TranslationCascadeResult(
                    source_text=request.source_text,
                    translated_text=result.translated_text,
                    source_language=result.source_language,
                    target_language=result.target_language,
                    provider=result.provider or provider_name,
                    model="",
                    request_id=request.request_id,
                    fallback_level=fallback_level,
                    notice=notice,
                    attempts=tuple(attempts),
                )
            except TextNormalizationError:
                raise
            except Exception:
                attempts.append(TranslationAttempt(provider_name, "unavailable"))
            finally:
                self._close_provider(provider)

        ai_service = None
        try:
            ai_service = self._llm_gateway.create_text_service("translation_ai")
            ai_result = ai_service.translate(
                request.source_text,
                source_language=request.source_language,
                target_language=request.target_language,
                request_id=request.request_id,
            )
        except Exception as exc:
            raise TranslationError("all translation providers are unavailable") from exc
        finally:
            if ai_service is not None:
                ai_service.close()

        attempts.append(TranslationAttempt("ai", "success"))
        return TranslationCascadeResult(
            source_text=request.source_text,
            translated_text=ai_result.output_text,
            source_language=ai_result.source_language,
            target_language=ai_result.target_language,
            provider="ai",
            model=ai_result.model,
            request_id=request.request_id,
            fallback_level=2,
            notice="有道和 Google 翻译当前不可用，已使用 AI 翻译。",
            attempts=tuple(attempts),
        )


__all__ = [
    "TranslationAttempt",
    "TranslationCascadeResult",
    "TranslationFallbackService",
]
