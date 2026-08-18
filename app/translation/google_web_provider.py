"""Resilient Google Translate web-compatible provider.

The provider intentionally uses only public web-compatible HTTP requests. It
keeps a warm connection for short translations, fails over between the two
well-known Google hosts, and remembers the endpoint that most recently worked
so repeated live translations do not repeatedly wait on an unhealthy host.
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

DEFAULT_WEB_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
DEFAULT_FALLBACK_WEB_ENDPOINT = "https://translate.google.com/translate_a/single"
DEFAULT_TIMEOUT_SECONDS = 3.0
DEFAULT_MAX_RETRIES = 1
DEFAULT_MIN_INTERVAL_SECONDS = 0.12
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
LOGGER_NAME = "desktop_translator"
TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
GOOGLE_TRANSLATE_HOSTS = frozenset({"translate.google.com", "translate.googleapis.com"})
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
    """Use certifi when available while retaining certificate verification."""

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class _PersistentWebRequester:
    """Keep one HTTP/1.1 connection warm and repair stale keep-alive sockets."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._connection: HTTPConnection | HTTPSConnection | None = None
        self._connection_key: tuple[str, str, int | None] | None = None
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
            request_headers.setdefault("Accept-Encoding", "identity")

            # A server can silently close an idle keep-alive socket. A failed
            # request on a reused socket is safe to replay once because this is
            # an idempotent GET. A new connection still gets only one attempt;
            # provider-level failover handles broader network failures.
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
        if self._connection is not None and self._connection_key == connection_key:
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
    """Translate with bounded latency and adaptive Google-host failover."""

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
        requested_endpoint = (
            endpoint
            if endpoint is not None
            else getattr(resolved_config, "google_web_endpoint", DEFAULT_WEB_ENDPOINT)
        )
        self.endpoint = self._safe_endpoint(requested_endpoint)
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
            else getattr(resolved_config, "google_web_max_retries", DEFAULT_MAX_RETRIES)
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
        self._transport = None if requester is not None else _PersistentWebRequester()
        self._requester = requester or self._transport
        self._sleep = sleep_function or sleep
        self._clock = clock or monotonic
        self._rate_lock = Lock()
        self._endpoint_lock = Lock()
        self._last_request_at: float | None = None
        self._endpoints = self._endpoint_candidates(self.endpoint)
        self._preferred_endpoint = self._endpoints[0]
        self.logger = logger or logging.getLogger(LOGGER_NAME)

    @staticmethod
    def _safe_endpoint(value: object) -> str:
        endpoint = str(value or "").strip()
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
        # Live translation should fail over rather than leave the UI waiting
        # on a single host for many seconds. Explicit settings are therefore
        # bounded to five seconds per endpoint.
        return min(5.0, max(0.5, timeout))

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

    @staticmethod
    def _endpoint_candidates(endpoint: str) -> tuple[str, ...]:
        parsed = urlsplit(endpoint)
        host = (parsed.hostname or "").lower()
        if host not in GOOGLE_TRANSLATE_HOSTS:
            return (endpoint,)
        fallback = (
            DEFAULT_FALLBACK_WEB_ENDPOINT
            if host == "translate.googleapis.com"
            else DEFAULT_WEB_ENDPOINT
        )
        if fallback == endpoint:
            return (endpoint,)
        return (endpoint, fallback)

    def _attempt_endpoints(self) -> tuple[str, ...]:
        """Return at most 1 + max_retries endpoint attempts.

        With the default retry count this means exactly two bounded attempts:
        the most recently successful endpoint followed by the other Google
        host. Custom endpoints are retried on themselves because there is no
        safe implicit alternate host for them.
        """

        budget = self.max_retries + 1
        with self._endpoint_lock:
            preferred = self._preferred_endpoint
            candidates = [preferred]
            candidates.extend(item for item in self._endpoints if item != preferred)
        if not candidates:
            candidates = [self.endpoint]
        while len(candidates) < budget:
            candidates.append(preferred)
        return tuple(candidates[:budget])

    @property
    def name(self) -> str:
        return "google_web"

    @property
    def preferred_endpoint(self) -> str:
        with self._endpoint_lock:
            return self._preferred_endpoint

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()

    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Send one bounded request sequence and remember the working host."""

        if not self.enabled:
            raise WebTranslationError("Google web translation is disabled")

        headers = {
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.8",
            "User-Agent": self.user_agent,
        }
        endpoints = self._attempt_endpoints()
        last_error: BaseException | None = None
        last_status: int | None = None

        for attempt, endpoint in enumerate(endpoints):
            self._wait_for_rate_limit()
            url = self._build_url(request, endpoint=endpoint)
            try:
                response = self._coerce_response(
                    self._requester(url, headers, self.timeout_seconds)
                )
            except Exception as exc:
                last_error = exc
                if attempt + 1 < len(endpoints):
                    self._retry_log(attempt, status=None, endpoint=endpoint)
                    # Transport failures switch hosts immediately; waiting here
                    # only makes an already-slow UI slower.
                    continue
                raise WebTranslationError(
                    "Google web translation request failed"
                ) from exc

            last_status = response.status_code
            if response.status_code in TRANSIENT_HTTP_STATUSES:
                if attempt + 1 < len(endpoints):
                    self._retry_log(
                        attempt,
                        status=response.status_code,
                        endpoint=endpoint,
                    )
                    self._sleep(self._retry_delay(attempt))
                    continue
                raise WebTranslationError("Google web translation request failed")

            if response.status_code < 200 or response.status_code >= 300:
                raise WebTranslationError("Google web translation request failed")

            result = self._parse_response(response.body, request)
            with self._endpoint_lock:
                changed = endpoint != self._preferred_endpoint
                self._preferred_endpoint = endpoint
            if changed:
                self.logger.info(
                    "google_web_endpoint_promoted host=%s",
                    urlsplit(endpoint).hostname,
                )
            return result

        self.logger.warning(
            "google_web_request_failed status=%s error_type=%s",
            last_status,
            type(last_error).__name__ if last_error is not None else "none",
        )
        raise WebTranslationError("Google web translation request failed")

    def _build_url(
        self,
        request: TranslationRequest,
        *,
        endpoint: str | None = None,
    ) -> str:
        target_endpoint = self._safe_endpoint(endpoint or self.endpoint)
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
                ("tk", generate_token(request.source_text)),
                ("q", request.source_text),
            ]
        )
        query = urlencode(query_items)
        separator = "&" if "?" in target_endpoint else "?"
        return f"{target_endpoint}{separator}{query}"

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
        return min(1.0, 0.25 * (2**attempt))

    def _retry_log(
        self,
        attempt: int,
        *,
        status: int | None,
        endpoint: str,
    ) -> None:
        self.logger.info(
            "google_web_retry attempt=%s status=%s host=%s",
            attempt + 1,
            status,
            urlsplit(endpoint).hostname,
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

        source_language = detected_language or request.source_language
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
    "DEFAULT_FALLBACK_WEB_ENDPOINT",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MIN_INTERVAL_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_USER_AGENT",
    "DEFAULT_WEB_ENDPOINT",
    "GOOGLE_TRANSLATE_HOSTS",
    "GoogleWebTranslationProvider",
    "TRANSIENT_HTTP_STATUSES",
    "WEB_LANGUAGE_MAP",
    "WEB_TRANSLATION_TYPES",
    "WebRequester",
    "WebResponse",
]
