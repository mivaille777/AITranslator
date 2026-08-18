"""Provider-independent translation orchestration."""

from __future__ import annotations

from dataclasses import replace
import logging
from pathlib import Path
from typing import Any

from app.infrastructure.config import ConfigManager
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.cache import TranslationCache
from app.translation.errors import TranslationError
from app.translation.google_web_provider import GoogleWebTranslationProvider
from app.translation.normalizer import DEFAULT_MAX_TEXT_LENGTH, TextNormalizer

DEFAULT_SOURCE_LANGUAGE = "auto"
DEFAULT_TARGET_LANGUAGE = "zh-CN"
LOGGER_NAME = "desktop_translator"


class TranslationManager:
    """Validate requests, invoke one provider, and normalize its result."""

    def __init__(
        self,
        provider: TranslationProvider | Any | None = None,
        *,
        default_source_language: str | None = None,
        default_target_language: str | None = None,
        cache: TranslationCache | None = None,
        cache_enabled: bool | None = None,
        cache_max_size: int | None = None,
        sqlite_enabled: bool | None = None,
        sqlite_path: str | Path | None = None,
        history_enabled: bool | None = None,
        config_manager: ConfigManager | Any | None = None,
        logger: logging.Logger | None = None,
        text_normalizer: TextNormalizer | None = None,
        max_text_length: int | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger(LOGGER_NAME)
        resolved_config = config_manager or ConfigManager()
        self.config_manager = resolved_config
        self._provider_managed = provider is None
        # The web provider is lazy: constructing the manager performs no
        # network request. Tests and offline callers can continue to inject a
        # fake provider explicitly.
        if provider is None:
            self.provider = GoogleWebTranslationProvider(
                config_manager=resolved_config,
                logger=self.logger,
            )
        else:
            self.provider = provider
        self._provider_signature = self._read_provider_signature()
        configured_source = getattr(
            resolved_config,
            "translation_source_language",
            DEFAULT_SOURCE_LANGUAGE,
        )
        configured_target = getattr(
            resolved_config,
            "translation_target_language",
            DEFAULT_TARGET_LANGUAGE,
        )
        self.default_source_language = (
            default_source_language
            if default_source_language is not None
            else configured_source
        ) or DEFAULT_SOURCE_LANGUAGE
        self.default_target_language = (
            default_target_language
            if default_target_language is not None
            else configured_target
        ) or DEFAULT_TARGET_LANGUAGE

        if cache is not None:
            self.cache = cache
            if any(
                value is not None
                for value in (sqlite_enabled, sqlite_path, history_enabled)
            ):
                configure_persistence = getattr(
                    self.cache,
                    "configure_persistence",
                    None,
                )
                if callable(configure_persistence):
                    configure_persistence(
                        sqlite_enabled=sqlite_enabled,
                        sqlite_path=sqlite_path,
                        history_enabled=history_enabled,
                    )
        else:
            enabled = (
                cache_enabled
                if cache_enabled is not None
                else bool(
                    getattr(resolved_config, "translation_cache_enabled", True)
                )
            )
            max_size = (
                cache_max_size
                if cache_max_size is not None
                else int(
                    getattr(resolved_config, "translation_cache_max_size", 128)
                )
            )
            configured_sqlite_enabled = bool(
                getattr(resolved_config, "translation_sqlite_cache_enabled", True)
            )
            # Explicitly injected providers are normally test/offline
            # providers. Keep their default isolated from the application's
            # persistent database unless the caller opts in explicitly.
            persistent_enabled = (
                sqlite_enabled
                if sqlite_enabled is not None
                else configured_sqlite_enabled if self._provider_managed else False
            )
            configured_sqlite_path = getattr(
                resolved_config,
                "translation_cache_path",
                None,
            )
            persistent_path = (
                sqlite_path if sqlite_path is not None else configured_sqlite_path
            )
            persistent_history = (
                history_enabled
                if history_enabled is not None
                else bool(getattr(resolved_config, "translation_history_enabled", False))
            )
            self.cache = TranslationCache(
                max_size=max_size,
                enabled=enabled,
                sqlite_enabled=bool(persistent_enabled),
                sqlite_path=persistent_path,
                history_enabled=persistent_history,
                logger=self.logger,
            )

        if text_normalizer is not None:
            self.text_normalizer = text_normalizer
        else:
            normalized_limit = (
                max_text_length
                if max_text_length is not None
                else int(
                    getattr(
                        resolved_config,
                        "translation_max_text_length",
                        DEFAULT_MAX_TEXT_LENGTH,
                    )
                )
            )
            self.text_normalizer = TextNormalizer(max_length=normalized_limit)

    def configure_languages(
        self,
        source_language: str | None = None,
        target_language: str | None = None,
    ) -> None:
        """Apply language defaults for subsequent translation requests."""

        if source_language is not None and str(source_language).strip():
            self.default_source_language = str(source_language).strip()
        if target_language is not None and str(target_language).strip():
            self.default_target_language = str(target_language).strip()

    def configure_cache(
        self,
        *,
        enabled: bool | None = None,
        max_size: int | None = None,
        sqlite_enabled: bool | None = None,
        sqlite_path: str | Path | None = None,
        history_enabled: bool | None = None,
    ) -> None:
        """Apply cache settings without exposing cache implementation details."""

        next_enabled = self.cache.enabled if enabled is None else bool(enabled)
        next_size = self.cache.max_size if max_size is None else int(max_size)
        if next_size < 1:
            next_size = 1
        if next_size != self.cache.max_size:
            next_sqlite_enabled = getattr(
                self.cache,
                "sqlite_enabled",
                False,
            ) if sqlite_enabled is None else bool(sqlite_enabled)
            next_sqlite_path = getattr(
                self.cache,
                "sqlite_path",
                None,
            ) if sqlite_path is None else sqlite_path
            next_history_enabled = getattr(
                self.cache,
                "history_enabled",
                False,
            ) if history_enabled is None else bool(history_enabled)
            old_cache = self.cache
            self.cache = TranslationCache(
                max_size=next_size,
                enabled=next_enabled,
                sqlite_enabled=next_sqlite_enabled,
                sqlite_path=next_sqlite_path,
                history_enabled=next_history_enabled,
                logger=self.logger,
            )
            close_cache = getattr(old_cache, "close", None)
            if callable(close_cache):
                close_cache()
        else:
            self.cache.enabled = next_enabled
            configure_persistence = getattr(
                self.cache,
                "configure_persistence",
                None,
            )
            if callable(configure_persistence):
                configure_persistence(
                    sqlite_enabled=sqlite_enabled,
                    sqlite_path=sqlite_path,
                    history_enabled=history_enabled,
                )

    @property
    def provider_name(self) -> str:
        """Return the active provider label without exposing implementation data."""

        return self._provider_name(self.provider)

    def close(self) -> None:
        """Release resources owned by the provider and both cache levels."""

        close = getattr(self.provider, "close", None)
        try:
            if callable(close):
                close()
        finally:
            close_cache = getattr(self.cache, "close", None)
            if callable(close_cache):
                close_cache()

    def prepare_source_text(
        self,
        source_text: object | None,
        *,
        truncate: bool = False,
    ) -> str:
        """Normalize source text for a caller that needs explicit preparation."""

        return self.text_normalizer.normalize(source_text, truncate=truncate)

    @staticmethod
    def _provider_name(provider: object | None) -> str:
        if provider is None:
            return "none"
        name = getattr(provider, "name", None)
        if isinstance(name, str) and name.strip():
            return name.strip()
        return type(provider).__name__

    def _read_provider_signature(self) -> tuple[object, ...]:
        return (
            getattr(self.config_manager, "google_web_enabled", True),
            getattr(
                self.config_manager,
                "google_web_endpoint",
                "https://translate.google.com/translate_a/single",
            ),
            getattr(self.config_manager, "google_web_timeout_seconds", 8.0),
            getattr(self.config_manager, "google_web_max_retries", 0),
            getattr(self.config_manager, "google_web_min_interval_seconds", 0.0),
        )

    def configure_provider(self, *, force: bool = False) -> bool:
        """Apply the current web-provider configuration to future requests.

        Changing the endpoint or request policy clears the in-memory cache so
        a result produced under an older web configuration is not reused.
        """

        if not self._provider_managed and not force:
            return False
        signature = self._read_provider_signature()
        if not force and signature == self._provider_signature:
            return False
        old_provider = self.provider
        close = getattr(old_provider, "close", None)
        if callable(close):
            close()
        self.provider = GoogleWebTranslationProvider(
            config_manager=self.config_manager,
            logger=self.logger,
        )
        self._provider_signature = signature
        self.cache.clear()
        self.logger.info(
            "translation_provider_selected provider=%s",
            self.provider_name,
        )
        return True

    def apply_settings(
        self,
        *,
        source_language: str | None = None,
        target_language: str | None = None,
        cache_enabled: bool | None = None,
        cache_max_size: int | None = None,
        sqlite_enabled: bool | None = None,
        sqlite_path: str | Path | None = None,
        history_enabled: bool | None = None,
    ) -> None:
        """Apply common settings and then refresh the web provider."""

        self.configure_languages(source_language, target_language)
        self.configure_cache(
            enabled=cache_enabled,
            max_size=cache_max_size,
            sqlite_enabled=sqlite_enabled,
            sqlite_path=sqlite_path,
            history_enabled=history_enabled,
        )
        self.configure_provider()

    def translate(
        self,
        source_text: str,
        source_language: str | None = None,
        target_language: str | None = None,
        request_id: int = 0,
    ) -> TranslationResult:
        """Translate source text through the configured provider."""

        text = self.text_normalizer.normalize(source_text)

        request = TranslationRequest(
            source_text=text,
            source_language=source_language or self.default_source_language,
            target_language=target_language or self.default_target_language,
            request_id=request_id,
        )

        cached_result = self.cache.get(
            request.source_language,
            request.target_language,
            request.source_text,
        )
        if cached_result is not None:
            self.logger.info("CACHE_HIT request_id=%s", request.request_id)
            return replace(
                cached_result,
                source_text=request.source_text,
                request_id=request.request_id,
            )

        self.logger.info("CACHE_MISS request_id=%s", request.request_id)
        try:
            result = self.provider.translate(request)
        except TranslationError:
            raise
        except Exception as exc:
            error = TranslationError("translation provider failed")
            error.__cause__ = exc
            raise error

        if not isinstance(result, TranslationResult):
            raise TranslationError("unsupported translation result")
        if (
            not isinstance(result.translated_text, str)
            or not result.translated_text.strip()
        ):
            raise TranslationError("translated text is empty")
        # The manager owns the request boundary. Providers may not know about
        # the UI request version, so normalize the returned model here.
        if result.request_id != request.request_id:
            result = replace(result, request_id=request.request_id)
        self.cache.set(
            request.source_language,
            request.target_language,
            request.source_text,
            result,
        )
        return result

    def translate_request(self, request: TranslationRequest) -> TranslationResult:
        """Translate an already-built request using the same validation path."""

        return self.translate(
            request.source_text,
            source_language=request.source_language,
            target_language=request.target_language,
            request_id=request.request_id,
        )
