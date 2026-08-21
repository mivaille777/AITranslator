"""Google Translate web-compatible provider.

The request contract mirrors the browser-style GTX flow used by mature clients
such as Zotero PDF Translate: a ``translate_a/single`` GET containing the
browser token (``tk``), language parameters and the response ``dt`` set.

This module does not handle CAPTCHA or attempt to bypass access controls.  It
keeps those responses diagnosable while never logging the user's source text or
full request URL.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import html
import json
import logging
from threading import Lock
from time import monotonic, sleep
from typing import Any
from urllib.parse import urlencode, urlsplit

import certifi
import requests

from app.infrastructure.config import ConfigManager
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.errors import WebTranslationError


DEFAULT_WEB_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
GOOGLE_WEB_ENDPOINT = "https://translate.google.com/translate_a/single"
LEGACY_WEB_ENDPOINTS = frozenset(
    {
        "http://translate.google.com/translate_a/single",
        "http://translate.googleapis.com/translate_a/single",
    }
)
DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_MAX_RETRIES = 1
DEFAULT_MIN_INTERVAL_SECONDS = 0.12
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
LOGGER_NAME = "desktop_translator"
TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
WEB_LANGUAGE_MAP = {"pt-BR": "pt", "pt-br": "pt"}
WEB_TRANSLATION_TYPES = (
    "at",
    "bd",
    "ex",
    "ld",
    "md",
    "qca",
    "rw",
    "rm",
    "ss",
    "t",
)


@dataclass(frozen=True)
class WebResponse:
    """Small transport-independent HTTP response used by tests and runtime."""

    status_code: int
    body: bytes | str
    final_url: str = ""
    content_type: str = ""


WebRequester = Callable[
    [str, Mapping[str, str], float],
    WebResponse | tuple[int, bytes | str],
]


class _RequestsWebRequester:
    """Persistent browser-like transport with redirect and proxy support.

    ``requests.Session`` follows redirects and honours normal environment proxy
    settings.  Explicit certifi verification avoids depending on a malformed
    Windows certificate-store entry in the active Conda environment.
    """

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> WebResponse:
        response = self._session.get(
            url,
            headers=dict(headers),
            timeout=timeout,
            allow_redirects=True,
            verify=certifi.where(),
        )
        return WebResponse(
            status_code=int(response.status_code),
            body=response.content,
            final_url=str(response.url),
            content_type=str(response.headers.get("content-type", "")),
        )

    def close(self) -> None:
        self._session.close()


# Keep the old private name as an alias so downstream imports do not break.
_PersistentWebRequester = _RequestsWebRequester


class GoogleWebTranslationProvider(TranslationProvider):
    """Translate through Google's unauthenticated browser-compatible endpoint."""

    def __init__(
        self,
        *,
        config_manager: ConfigManager | Any | None = None,
        endpoint: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        min_interval_seconds: float | None = None,
        enabled: bool | None = None,
        requester: WebRequester | None = None,
        sleep_function: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
        logger: logging.Logger | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        resolved_config = config_manager or ConfigManager()
        self.endpoint = self._safe_endpoint(
            endpoint
            if endpoint is not None
            else getattr(resolved_config, "google_web_endpoint", DEFAULT_WEB_ENDPOINT)
        )
        self.timeout_seconds = self._safe_timeout(
            timeout_seconds
            if timeout_seconds is not None
            else getattr(
                resolved_config,
                "google_web_timeout_seconds",
                DEFAULT_TIMEOUT_SECONDS,
            )
        )
        self.max_retries = self._safe_retries(
            max_retries
            if max_retries is not None
            else getattr(
                resolved_config,
                "google_web_max_retries",
                DEFAULT_MAX_RETRIES,
            )
        )
        self.min_interval_seconds = self._safe_interval(
            min_interval_seconds
            if min_interval_seconds is not None
            else getattr(
                resolved_config,
                "google_web_min_interval_seconds",
                DEFAULT_MIN_INTERVAL_SECONDS,
            )
        )
        self.enabled = self._safe_bool(
            enabled
            if enabled is not None
            else getattr(resolved_config, "google_web_enabled", True),
            True,
        )
        self.user_agent = str(user_agent).strip() or DEFAULT_USER_AGENT
        self._transport = None if requester is not None else _RequestsWebRequester()
        self._requester = requester or self._transport
        self._sleep = sleep_function or sleep
        self._clock = clock or monotonic
        self._rate_lock = Lock()
        self._last_request_at: float | None = None
        self.logger = logger or logging.getLogger(LOGGER_NAME)

    @staticmethod
    def _safe_endpoint(value: object) -> str:
        endpoint = str(value).strip().rstrip("?")
        if endpoint == "http://translate.google.com/translate_a/single":
            return GOOGLE_WEB_ENDPOINT
        if endpoint == "http://translate.googleapis.com/translate_a/single":
            return DEFAULT_WEB_ENDPOINT
        parsed = urlsplit(endpoint)
        if parsed.scheme == "https" and parsed.hostname:
            return endpoint
        return DEFAULT_WEB_ENDPOINT

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
        return "google_web"

    @property
    def endpoint_host(self) -> str:
        return str(urlsplit(self.endpoint).hostname or "unknown")

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()

    @staticmethod
    def _token_shift(value: int, pattern: str) -> int:
        """Apply the 32-bit shift/xor transform used by the browser token."""

        value &= 0xFFFFFFFF
        for index in range(0, len(pattern) - 2, 3):
            code = pattern[index + 2]
            shift = ord(code) - 87 if code >= "a" else int(code)
            if pattern[index + 1] == "+":
                shifted = (value & 0xFFFFFFFF) >> shift
            else:
                shifted = (value << shift) & 0xFFFFFFFF
            if pattern[index] == "+":
                value = (value + shifted) & 0xFFFFFFFF
            else:
                value = (value ^ shifted) & 0xFFFFFFFF
        return value & 0xFFFFFFFF

    @classmethod
    def _token(cls, text: str) -> str:
        """Generate the ``tk`` value used by Google Translate's GTX web call."""

        seed = 406644
        value = seed
        for byte in text.encode("utf-8"):
            value = (value + byte) & 0xFFFFFFFF
            value = cls._token_shift(value, "+-a^+6")
        value = cls._token_shift(value, "+-3^+b+-f")
        value = (value ^ 3293161072) & 0xFFFFFFFF
        value %= 1_000_000
        return f"{value}.{value ^ seed}"

    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Send one browser-compatible request and parse translated segments."""

        if not self.enabled:
            raise WebTranslationError("Google web translation is disabled")

        url = self._build_url(request)
        headers = {
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.8",
            "Referer": "https://translate.google.com/",
            "User-Agent": self.user_agent,
        }
        last_status: int | None = None

        for attempt in range(self.max_retries + 1):
            self._wait_for_rate_limit()
            try:
                response = self._coerce_response(
                    self._requester(url, headers, self.timeout_seconds)
                )
            except Exception as exc:
                if attempt < self.max_retries:
                    self._retry_log(attempt, status=None)
                    self._sleep(self._retry_delay(attempt))
                    continue
                self.logger.warning(
                    "google_web_transport_failed error_type=%s host=%s attempts=%s",
                    type(exc).__name__,
                    self.endpoint_host,
                    attempt + 1,
                )
                raise WebTranslationError(
                    "Google web translation request failed"
                ) from exc

            last_status = response.status_code
            if self._is_google_challenge(response):
                final_host = str(urlsplit(response.final_url).hostname or "unknown")
                self.logger.warning(
                    "google_web_challenge status=%s final_host=%s attempts=%s",
                    response.status_code,
                    final_host,
                    attempt + 1,
                )
                raise WebTranslationError("Google web translation was challenged")

            if response.status_code in TRANSIENT_HTTP_STATUSES:
                if attempt < self.max_retries:
                    self._retry_log(attempt, status=response.status_code)
                    self._sleep(self._retry_delay(attempt))
                    continue
                self._log_http_failure(response.status_code, attempt + 1)
                raise WebTranslationError("Google web translation request failed")

            if response.status_code < 200 or response.status_code >= 300:
                self._log_http_failure(response.status_code, attempt + 1)
                raise WebTranslationError("Google web translation request failed")

            return self._parse_response(response.body, request)

        self._log_http_failure(last_status, self.max_retries + 1)
        raise WebTranslationError("Google web translation request failed")

    def _log_http_failure(self, status: int | None, attempts: int) -> None:
        self.logger.warning(
            "google_web_http_failed status=%s host=%s attempts=%s",
            status,
            self.endpoint_host,
            attempts,
        )

    def _build_url(self, request: TranslationRequest) -> str:
        source_language = WEB_LANGUAGE_MAP.get(
            request.source_language or "auto",
            request.source_language or "auto",
        )
        target_language = WEB_LANGUAGE_MAP.get(
            request.target_language,
            request.target_language,
        )
        query_items: list[tuple[str, str]] = [
            ("client", "gtx"),
            ("sl", source_language),
            ("tl", target_language),
            ("hl", "en"),
        ]
        query_items.extend(("dt", value) for value in WEB_TRANSLATION_TYPES)
        query_items.extend(
            [
                ("source", "bh"),
                ("ssel", "0"),
                ("tsel", "0"),
                ("kc", "1"),
                ("tk", self._token(request.source_text)),
                ("q", request.source_text),
            ]
        )
        query = urlencode(query_items)
        separator = "&" if "?" in self.endpoint else "?"
        return f"{self.endpoint}{separator}{query}"

    @staticmethod
    def _is_google_challenge(response: WebResponse) -> bool:
        if response.final_url:
            final = urlsplit(response.final_url)
            if (
                final.hostname
                and final.hostname.lower().endswith("google.com")
                and final.path.startswith("/sorry/")
            ):
                return True

        content_type = response.content_type.lower()
        if "text/html" not in content_type:
            return False
        try:
            body = (
                response.body.decode("utf-8", errors="ignore")
                if isinstance(response.body, bytes)
                else str(response.body)
            ).lower()[:12000]
        except Exception:
            return False
        return any(
            marker in body
            for marker in (
                "our systems have detected unusual traffic",
                "g-recaptcha",
                "recaptcha",
                "/sorry/",
            )
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
            "google_web_retry attempt=%s status=%s host=%s",
            attempt + 1,
            status,
            self.endpoint_host,
        )

    @staticmethod
    def _coerce_response(
        response: WebResponse | tuple[int, bytes | str],
    ) -> WebResponse:
        if isinstance(response, WebResponse):
            return response
        if isinstance(response, tuple) and len(response) == 2:
            return WebResponse(int(response[0]), response[1])
        raise TypeError("unsupported web response")

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
                "unsupported Google web translation result"
            ) from exc

        translated_text, detected_language = cls._extract_translation(payload)
        if not translated_text.strip():
            raise WebTranslationError("unsupported Google web translation result")

        source_language = detected_language if detected_language else request.source_language
        return TranslationResult(
            source_text=request.source_text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=request.target_language,
            provider="google_web",
            request_id=request.request_id,
        )

    @staticmethod
    def _extract_translation(payload: object) -> tuple[str, str | None]:
        if isinstance(payload, list):
            fragments: list[str] = []
            first = payload[0] if payload else None
            if isinstance(first, list):
                for segment in first:
                    if (
                        isinstance(segment, (list, tuple))
                        and segment
                        and isinstance(segment[0], str)
                    ):
                        fragments.append(segment[0])
            detected = (
                payload[2]
                if len(payload) > 2 and isinstance(payload[2], str)
                else None
            )
            return html.unescape("".join(fragments)), detected

        if isinstance(payload, Mapping):
            data = payload.get("data")
            translations = data.get("translations") if isinstance(data, Mapping) else None
            if isinstance(translations, list):
                fragments = [
                    item.get("translatedText", "")
                    for item in translations
                    if isinstance(item, Mapping)
                    and isinstance(item.get("translatedText"), str)
                ]
                detected = None
                if translations and isinstance(translations[0], Mapping):
                    value = translations[0].get("detectedLanguageCode")
                    if isinstance(value, str):
                        detected = value
                return html.unescape("".join(fragments)), detected

        return "", None


__all__ = [
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MIN_INTERVAL_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_USER_AGENT",
    "DEFAULT_WEB_ENDPOINT",
    "GOOGLE_WEB_ENDPOINT",
    "GoogleWebTranslationProvider",
    "LEGACY_WEB_ENDPOINTS",
    "TRANSIENT_HTTP_STATUSES",
    "WEB_LANGUAGE_MAP",
    "WEB_TRANSLATION_TYPES",
    "WebRequester",
    "WebResponse",
]
