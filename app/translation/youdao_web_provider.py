"""Youdao web-compatible translation provider.

This adapter uses the public web-compatible translation route exposed by
fanyi.youdao.com. It intentionally does not require a Youdao Cloud app key and
does not attempt to bypass CAPTCHA, login, or other access controls.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import logging
from threading import Lock
from time import monotonic, sleep
from typing import Any
from urllib.parse import urlsplit

import certifi
import requests

from app.infrastructure.config import ConfigManager
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.errors import WebTranslationError


DEFAULT_YOUDAO_WEB_ENDPOINT = "https://fanyi.youdao.com/translate"
DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_MAX_RETRIES = 1
DEFAULT_MIN_INTERVAL_SECONDS = 0.2
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
LOGGER_NAME = "desktop_translator"
TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})

# Language identifiers accepted by the simple fanyi.youdao.com/translate route.
# For unsupported pairs the web endpoint's AUTO mode remains the safe fallback.
YOUDAO_PAIR_MAP: dict[tuple[str, str], str] = {
    ("zh-CN", "en"): "ZH_CN2EN",
    ("zh-CN", "ja"): "ZH_CN2JA",
    ("zh-CN", "ko"): "ZH_CN2KR",
    ("zh-CN", "fr"): "ZH_CN2FR",
    ("zh-CN", "ru"): "ZH_CN2RU",
    ("zh-CN", "es"): "ZH_CN2SP",
    ("en", "zh-CN"): "EN2ZH_CN",
    ("ja", "zh-CN"): "JA2ZH_CN",
    ("ko", "zh-CN"): "KR2ZH_CN",
    ("fr", "zh-CN"): "FR2ZH_CN",
    ("ru", "zh-CN"): "RU2ZH_CN",
    ("es", "zh-CN"): "SP2ZH_CN",
}

YOUDAO_SOURCE_LANGUAGE_MAP = {
    "ZH_CN": "zh-CN",
    "EN": "en",
    "JA": "ja",
    "KR": "ko",
    "FR": "fr",
    "RU": "ru",
    "SP": "es",
}


@dataclass(frozen=True)
class YoudaoWebResponse:
    """Transport-independent response used by runtime and offline tests."""

    status_code: int
    body: bytes | str


YoudaoRequester = Callable[
    [str, Mapping[str, str], Mapping[str, str], float],
    YoudaoWebResponse | tuple[int, bytes | str],
]


class _RequestsRequester:
    """Small persistent requests transport with explicit certifi verification."""

    def __init__(self) -> None:
        self._session = requests.Session()

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        form: Mapping[str, str],
        timeout: float,
    ) -> YoudaoWebResponse:
        response = self._session.post(
            url,
            headers=dict(headers),
            data=dict(form),
            timeout=timeout,
            allow_redirects=True,
            verify=certifi.where(),
        )
        return YoudaoWebResponse(
            status_code=int(response.status_code),
            body=response.content,
        )

    def close(self) -> None:
        self._session.close()


class YoudaoWebTranslationProvider(TranslationProvider):
    """Translate through Youdao's unauthenticated web-compatible endpoint."""

    def __init__(
        self,
        *,
        config_manager: ConfigManager | Any | None = None,
        endpoint: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        min_interval_seconds: float | None = None,
        enabled: bool | None = None,
        requester: YoudaoRequester | None = None,
        sleep_function: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
        logger: logging.Logger | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        resolved_config = config_manager or ConfigManager()
        self.endpoint = self._safe_endpoint(
            endpoint
            if endpoint is not None
            else self._config_value(
                resolved_config,
                "endpoint",
                DEFAULT_YOUDAO_WEB_ENDPOINT,
            )
        )
        self.timeout_seconds = self._safe_timeout(
            timeout_seconds
            if timeout_seconds is not None
            else float(
                self._config_value(
                    resolved_config,
                    "timeout_ms",
                    int(DEFAULT_TIMEOUT_SECONDS * 1000),
                )
            )
            / 1000.0
        )
        self.max_retries = self._safe_retries(
            max_retries
            if max_retries is not None
            else self._config_value(
                resolved_config,
                "max_retries",
                DEFAULT_MAX_RETRIES,
            )
        )
        self.min_interval_seconds = self._safe_interval(
            min_interval_seconds
            if min_interval_seconds is not None
            else float(
                self._config_value(
                    resolved_config,
                    "min_interval_ms",
                    int(DEFAULT_MIN_INTERVAL_SECONDS * 1000),
                )
            )
            / 1000.0
        )
        self.enabled = self._safe_bool(
            enabled
            if enabled is not None
            else self._config_value(resolved_config, "enabled", True),
            True,
        )
        self.user_agent = str(user_agent).strip() or DEFAULT_USER_AGENT
        self._transport = None if requester is not None else _RequestsRequester()
        self._requester = requester or self._transport
        self._sleep = sleep_function or sleep
        self._clock = clock or monotonic
        self._rate_lock = Lock()
        self._last_request_at: float | None = None
        self.logger = logger or logging.getLogger(LOGGER_NAME)

    @staticmethod
    def _config_value(config: object, key: str, default: object) -> object:
        getter = getattr(config, "get", None)
        if callable(getter):
            try:
                return getter("youdao_web", key, default)
            except TypeError:
                pass
        return getattr(config, f"youdao_web_{key}", default)

    @staticmethod
    def _safe_endpoint(value: object) -> str:
        endpoint = str(value).strip().rstrip("?")
        parsed = urlsplit(endpoint)
        if parsed.scheme == "https" and parsed.hostname:
            return endpoint
        return DEFAULT_YOUDAO_WEB_ENDPOINT

    @staticmethod
    def _safe_timeout(value: object) -> float:
        try:
            timeout = float(value)
            if timeout != timeout or timeout in {float("inf"), float("-inf")}:
                raise ValueError("timeout must be finite")
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT_SECONDS
        return min(60.0, max(0.5, timeout))

    @staticmethod
    def _safe_retries(value: object) -> int:
        try:
            retries = int(value)
        except (TypeError, ValueError):
            retries = DEFAULT_MAX_RETRIES
        return min(3, max(0, retries))

    @staticmethod
    def _safe_interval(value: object) -> float:
        try:
            interval = float(value)
            if interval != interval or interval in {float("inf"), float("-inf")}:
                raise ValueError("interval must be finite")
        except (TypeError, ValueError):
            interval = DEFAULT_MIN_INTERVAL_SECONDS
        return min(60.0, max(0.0, interval))

    @staticmethod
    def _safe_bool(value: object, fallback: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            return fallback
        if value is None:
            return fallback
        return bool(value)

    @property
    def name(self) -> str:
        return "youdao_web"

    @property
    def endpoint_host(self) -> str:
        return str(urlsplit(self.endpoint).hostname or "unknown")

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()

    @classmethod
    def _translation_type(cls, source_language: str, target_language: str) -> str:
        source = cls._normalize_language(source_language)
        target = cls._normalize_language(target_language)
        if source == "auto":
            return "AUTO"
        return YOUDAO_PAIR_MAP.get((source, target), "AUTO")

    @staticmethod
    def _normalize_language(language: object) -> str:
        value = str(language or "").strip()
        aliases = {
            "auto": "auto",
            "zh": "zh-CN",
            "zh-cn": "zh-CN",
            "zh_cn": "zh-CN",
            "en-us": "en",
            "en-gb": "en",
            "jp": "ja",
            "kr": "ko",
            "sp": "es",
        }
        return aliases.get(value.lower(), value)

    def _build_form(self, request: TranslationRequest) -> dict[str, str]:
        translation_type = self._translation_type(
            request.source_language,
            request.target_language,
        )
        return {
            "i": request.source_text,
            "from": "AUTO",
            "to": "AUTO",
            "smartresult": "dict",
            "client": "fanyideskweb",
            "doctype": "json",
            "version": "2.1",
            "keyfrom": "fanyi.web",
            "action": "FY_BY_CLICKBUTTON",
            "typoResult": "true",
            "type": translation_type,
        }

    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Send one bounded web request and parse Youdao's JSON response."""

        if not self.enabled:
            raise WebTranslationError("Youdao web translation is disabled")

        headers = {
            "Accept": "application/json,text/javascript,*/*;q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://fanyi.youdao.com",
            "Referer": "https://fanyi.youdao.com/",
            "User-Agent": self.user_agent,
        }
        form = self._build_form(request)
        last_status: int | None = None

        for attempt in range(self.max_retries + 1):
            self._wait_for_rate_limit()
            try:
                response = self._coerce_response(
                    self._requester(
                        self.endpoint,
                        headers,
                        form,
                        self.timeout_seconds,
                    )
                )
            except Exception as exc:
                if attempt < self.max_retries:
                    self._retry_log(attempt, status=None)
                    self._sleep(self._retry_delay(attempt))
                    continue
                self.logger.warning(
                    "youdao_web_transport_failed error_type=%s host=%s attempts=%s",
                    type(exc).__name__,
                    self.endpoint_host,
                    attempt + 1,
                )
                raise WebTranslationError(
                    "Youdao web translation request failed"
                ) from exc

            last_status = response.status_code
            if response.status_code in TRANSIENT_HTTP_STATUSES:
                if attempt < self.max_retries:
                    self._retry_log(attempt, status=response.status_code)
                    self._sleep(self._retry_delay(attempt))
                    continue
                self._log_http_failure(response.status_code, attempt + 1)
                raise WebTranslationError("Youdao web translation request failed")

            if response.status_code < 200 or response.status_code >= 300:
                self._log_http_failure(response.status_code, attempt + 1)
                raise WebTranslationError("Youdao web translation request failed")

            return self._parse_response(response.body, request)

        self._log_http_failure(last_status, self.max_retries + 1)
        raise WebTranslationError("Youdao web translation request failed")

    def _log_http_failure(self, status: int | None, attempts: int) -> None:
        # Never log form data because it contains the user's selected text.
        self.logger.warning(
            "youdao_web_http_failed status=%s host=%s attempts=%s",
            status,
            self.endpoint_host,
            attempts,
        )

    def _wait_for_rate_limit(self) -> None:
        if self.min_interval_seconds <= 0:
            return
        with self._rate_lock:
            now = self._clock()
            if self._last_request_at is not None:
                remaining = self.min_interval_seconds - (now - self._last_request_at)
                if remaining > 0:
                    self._sleep(remaining)
            self._last_request_at = self._clock()

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return min(2.0, 0.25 * (2**attempt))

    def _retry_log(self, attempt: int, status: int | None) -> None:
        self.logger.info(
            "youdao_web_retry attempt=%s status=%s host=%s",
            attempt + 1,
            status,
            self.endpoint_host,
        )

    @staticmethod
    def _coerce_response(
        response: YoudaoWebResponse | tuple[int, bytes | str],
    ) -> YoudaoWebResponse:
        if isinstance(response, YoudaoWebResponse):
            return response
        if isinstance(response, tuple) and len(response) == 2:
            return YoudaoWebResponse(int(response[0]), response[1])
        raise TypeError("unsupported Youdao web response")

    @classmethod
    def _parse_response(
        cls,
        body: bytes | str,
        request: TranslationRequest,
    ) -> TranslationResult:
        try:
            raw_body = body.decode("utf-8") if isinstance(body, bytes) else str(body)
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, TypeError, ValueError) as exc:
            raise WebTranslationError(
                "unsupported Youdao web translation result"
            ) from exc

        if not isinstance(payload, Mapping):
            raise WebTranslationError("unsupported Youdao web translation result")

        error_code = payload.get("errorCode", 0)
        if str(error_code) != "0":
            raise WebTranslationError("Youdao web translation request failed")

        translated_text = cls._extract_translation(payload)
        if not translated_text.strip():
            raise WebTranslationError("unsupported Youdao web translation result")

        detected_language = cls._detected_source_language(payload)
        source_language = (
            detected_language
            if request.source_language == "auto" and detected_language
            else request.source_language
        )
        return TranslationResult(
            source_text=request.source_text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=request.target_language,
            provider="youdao_web",
            request_id=request.request_id,
        )

    @staticmethod
    def _extract_translation(payload: Mapping[str, object]) -> str:
        rows = payload.get("translateResult")
        if not isinstance(rows, list):
            return ""

        fragments: list[str] = []
        for row in rows:
            if not isinstance(row, list):
                continue
            for segment in row:
                if not isinstance(segment, Mapping):
                    continue
                target = segment.get("tgt")
                if isinstance(target, str):
                    fragments.append(target)
        return "".join(fragments)

    @staticmethod
    def _detected_source_language(
        payload: Mapping[str, object],
    ) -> str | None:
        translation_type = payload.get("type")
        if not isinstance(translation_type, str) or "2" not in translation_type:
            return None
        source_code = translation_type.split("2", 1)[0]
        return YOUDAO_SOURCE_LANGUAGE_MAP.get(source_code)


__all__ = [
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MIN_INTERVAL_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_YOUDAO_WEB_ENDPOINT",
    "YOUDAO_PAIR_MAP",
    "YoudaoWebResponse",
    "YoudaoWebTranslationProvider",
]
