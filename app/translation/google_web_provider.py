"""Google Translate web-compatible provider.

This adapter intentionally contains all assumptions about the web request
format. It does not use Google account cookies, OAuth tokens, browser state,
CAPTCHA handling, or access-limit workarounds.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import html
from http.client import HTTPConnection, HTTPException, HTTPSConnection
import json
import logging
import ssl
from threading import Lock
from time import monotonic, sleep
from typing import Any
from urllib.parse import urlencode, urlsplit

from app.infrastructure.config import ConfigManager
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.errors import WebTranslationError
from app.translation.token.google_tk import generate_token

DEFAULT_WEB_ENDPOINT = "https://translate.google.com/translate_a/single"
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


WebRequester = Callable[
    [str, Mapping[str, str], float],
    WebResponse | tuple[int, bytes | str],
]


def _create_ssl_context() -> ssl.SSLContext:
    """Use certifi when available, while retaining certificate verification."""

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        # The dependency is declared by the application, but falling back to
        # the platform trust store keeps the provider importable in minimal
        # test environments. TLS verification is never disabled.
        return ssl.create_default_context()


class _PersistentWebRequester:
    """Keep one HTTP/1.1 connection warm for repeated short translations.

    A server can close an idle keep-alive socket without the client knowing.
    If the first request on a *reused* connection fails at the transport layer,
    discard that socket and transparently retry once on a fresh connection.
    GET is idempotent and this reconnect does not count as provider-level retry
    policy such as handling HTTP 429/5xx responses.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._connection: HTTPConnection | HTTPSConnection | None = None
        self._connection_key: tuple[str, str, int | None] | None = None
        # Creating the trust context is relatively expensive on Windows. Do
        # it once per provider instead of once per translation request.
        self._ssl_context = _create_ssl_context()

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> WebResponse:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Google web endpoint must be an HTTP URL")

        host = parsed.hostname
        port = parsed.port
        target = parsed.path or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        connection_key = (scheme, host, port)

        with self._lock:
            reused_connection = bool(
                self._connection is not None
                and self._connection_key == connection_key
            )
            connection = self._get_connection(connection_key, timeout)
            request_headers = dict(headers)
            request_headers.setdefault("Connection", "keep-alive")
            # Avoid compressed payload handling in this small transport. The
            # response is tiny, and identity encoding keeps parsing direct.
            request_headers.setdefault("Accept-Encoding", "identity")

            attempts = 2 if reused_connection else 1
            for attempt in range(attempts):
                try:
                    connection.timeout = timeout
                    connection.request("GET", target, headers=request_headers)
                    response = connection.getresponse()
                    body = response.read()
                    status_code = int(response.status)
                    if response.will_close:
                        self._close_locked()
                    return WebResponse(status_code, body)
                except (HTTPException, OSError):
                    self._close_locked()
                    if reused_connection and attempt == 0:
                        connection = self._get_connection(connection_key, timeout)
                        continue
                    raise

        raise RuntimeError("unreachable persistent request state")

    def _get_connection(
        self,
        connection_key: tuple[str, str, int | None],
        timeout: float,
    ) -> HTTPConnection | HTTPSConnection:
        if (
            self._connection is not None
            and self._connection_key == connection_key
        ):
            self._connection.timeout = timeout
            return self._connection

        self._close_locked()
        scheme, host, port = connection_key
        if scheme == "https":
            connection = HTTPSConnection(
                host,
                port=port,
                timeout=timeout,
                context=self._ssl_context,
            )
        else:
            connection = HTTPConnection(host, port=port, timeout=timeout)
        self._connection = connection
        self._connection_key = connection_key
        return connection

    def close(self) -> None:
        """Close the warm connection, if one exists."""

        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        connection = self._connection
        self._connection = None
        self._connection_key = None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


class GoogleWebTranslationProvider(TranslationProvider):
    """Translate through the Google web-compatible request."""

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
        self._transport = (
            None if requester is not None else _PersistentWebRequester()
        )
        self._requester = requester or self._transport
        self._sleep = sleep_function or sleep
        self._clock = clock or monotonic
        self._rate_lock = Lock()
        self._last_request_at: float | None = None
        self.logger = logger or logging.getLogger(LOGGER_NAME)

    @staticmethod
    def _safe_endpoint(value: object) -> str:
        endpoint = str(value).strip()
        if endpoint.startswith(("https://", "http://")):
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
        """Stable provider name used in results and safe logs."""

        return "google_web"

    def close(self) -> None:
        """Release the persistent connection owned by this provider."""

        if self._transport is not None:
            self._transport.close()

    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Send one request, retry transient failures, and parse safe output."""

        if not self.enabled:
            raise WebTranslationError("Google web translation is disabled")

        url = self._build_url(request)
        headers = {
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.8",
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
                raise WebTranslationError(
                    "Google web translation request failed"
                ) from exc

            last_status = response.status_code
            if response.status_code in TRANSIENT_HTTP_STATUSES:
                if attempt < self.max_retries:
                    self._retry_log(attempt, status=response.status_code)
                    self._sleep(self._retry_delay(attempt))
                    continue
                raise WebTranslationError(
                    "Google web translation request failed"
                )
            if response.status_code < 200 or response.status_code >= 300:
                raise WebTranslationError(
                    "Google web translation request failed"
                )

            return self._parse_response(response.body, request)

        # The loop always returns or raises; keep a safe defensive branch for
        # unusual custom transports.
        self.logger.warning(
            "google_web_request_failed status=%s",
            last_status,
        )
        raise WebTranslationError("Google web translation request failed")

    def _build_url(self, request: TranslationRequest) -> str:
        """Build the web-compatible query without logging the source text."""

        source_language = WEB_LANGUAGE_MAP.get(
            request.source_language or "auto",
            request.source_language or "auto",
        )
        target_language = WEB_LANGUAGE_MAP.get(
            request.target_language,
            request.target_language,
        )
        # Match the compact request used by Zotero PDF Translate. Repeated
        # ``dt`` fields are intentional: Google returns a richer response
        # while the parser below still consumes only translated fragments.
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
                ("tk", generate_token(request.source_text)),
                ("q", request.source_text),
            ]
        )
        query = urlencode(query_items)
        separator = "&" if "?" in self.endpoint else "?"
        return f"{self.endpoint}{separator}{query}"

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
            "google_web_retry attempt=%s status=%s",
            attempt + 1,
            status,
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

        source_language = (
            detected_language
            if detected_language
            else request.source_language
        )
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
        # Current web-compatible responses are nested arrays where the first
        # element contains translated fragments and the third element often
        # contains the detected source language.
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

        # Accept the REST-like shape as a defensive compatibility path for a
        # future endpoint response, without coupling the Cloud provider to it.
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
    "GoogleWebTranslationProvider",
    "TRANSIENT_HTTP_STATUSES",
    "WEB_LANGUAGE_MAP",
    "WEB_TRANSLATION_TYPES",
    "WebRequester",
    "WebResponse",
]
