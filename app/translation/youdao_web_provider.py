"""Youdao web translation provider using the current WebFanyi workflow.

The legacy ``fanyi.youdao.com/translate`` route can return HTTP 200 with a
non-JSON body.  The current website obtains a short-lived signing/AES bundle
from ``dict.youdao.com/webtranslate/key`` and sends translation requests to
``dict.youdao.com/webtranslate``.

No Youdao Cloud credential is required.  This adapter does not bypass CAPTCHA
or login controls and never logs user source text or request bodies.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import logging
import re
from threading import Lock
from time import monotonic, sleep, time
from typing import Any
from urllib.parse import urlsplit

import certifi
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import requests

from app.infrastructure.config import ConfigManager
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.errors import WebTranslationError


DEFAULT_YOUDAO_HOST = "https://fanyi.youdao.com/"
DEFAULT_YOUDAO_WEB_ENDPOINT = "https://dict.youdao.com/webtranslate"
DEFAULT_YOUDAO_KEY_ENDPOINT = "https://dict.youdao.com/webtranslate/key"
DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_MAX_RETRIES = 1
DEFAULT_MIN_INTERVAL_SECONDS = 0.2
DEFAULT_KEY_TTL_SECONDS = 600.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
LOGGER_NAME = "desktop_translator"
TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
YOUDAO_KEY_IDS = ("webfanyi-key-getter-2025", "webfanyi-key-getter")
# Public browser-script signing fallbacks, not user credentials.  Runtime first
# tries to discover the current value from Youdao's own page bundle.
YOUDAO_KEY_SIGNING_FALLBACKS = (
    "asdjnjfenknafdfsdfsd",
    "yU5nT5dK3eZ1pI4j",
)
_JS_URL_PATTERN = re.compile(
    r"https://shared\.ydstatic\.com/dict/translation-website/[^\"']+/js/app\.[^\"']+\.js"
)

YOUDAO_SOURCE_LANGUAGE_MAP = {
    "ZH_CHS": "zh-CN",
    "ZH-CHS": "zh-CN",
    "ZH_CHT": "zh-TW",
    "ZH-CHT": "zh-TW",
    "ZH_CN": "zh-CN",
    "EN": "en",
    "JA": "ja",
    "KR": "ko",
    "KO": "ko",
    "FR": "fr",
    "RU": "ru",
    "SP": "es",
    "ES": "es",
}


@dataclass(frozen=True)
class YoudaoWebResponse:
    status_code: int
    body: bytes | str
    final_url: str = ""
    content_type: str = ""


YoudaoRequester = Callable[
    [
        str,
        str,
        Mapping[str, str],
        Mapping[str, str] | None,
        Mapping[str, str] | None,
        float,
    ],
    YoudaoWebResponse | tuple[int, bytes | str],
]


class _RequestsRequester:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        params: Mapping[str, str] | None,
        data: Mapping[str, str] | None,
        timeout: float,
    ) -> YoudaoWebResponse:
        response = self._session.request(
            method=method,
            url=url,
            headers=dict(headers),
            params=None if params is None else dict(params),
            data=None if data is None else dict(data),
            timeout=timeout,
            allow_redirects=True,
            verify=certifi.where(),
        )
        return YoudaoWebResponse(
            status_code=int(response.status_code),
            body=response.content,
            final_url=str(response.url),
            content_type=str(response.headers.get("content-type", "")),
        )

    def close(self) -> None:
        self._session.close()


class YoudaoWebTranslationProvider(TranslationProvider):
    """Translate through Youdao's current browser-facing WebFanyi protocol."""

    def __init__(
        self,
        *,
        config_manager: ConfigManager | Any | None = None,
        endpoint: str | None = None,
        key_endpoint: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        min_interval_seconds: float | None = None,
        key_ttl_seconds: float = DEFAULT_KEY_TTL_SECONDS,
        enabled: bool | None = None,
        requester: YoudaoRequester | None = None,
        sleep_function: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
        wall_clock: Callable[[], float] | None = None,
        logger: logging.Logger | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        resolved_config = config_manager or ConfigManager()
        self.endpoint = self._safe_endpoint(
            endpoint
            if endpoint is not None
            else self._config_value(
                resolved_config, "endpoint", DEFAULT_YOUDAO_WEB_ENDPOINT
            ),
            DEFAULT_YOUDAO_WEB_ENDPOINT,
        )
        self.key_endpoint = self._safe_endpoint(
            key_endpoint if key_endpoint is not None else DEFAULT_YOUDAO_KEY_ENDPOINT,
            DEFAULT_YOUDAO_KEY_ENDPOINT,
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
                resolved_config, "max_retries", DEFAULT_MAX_RETRIES
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
        self.key_ttl_seconds = max(30.0, min(3600.0, float(key_ttl_seconds)))
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
        self._wall_clock = wall_clock or time
        self._rate_lock = Lock()
        self._last_request_at: float | None = None
        self._secret_key = ""
        self._aes_key = ""
        self._aes_iv = ""
        self._keys_fetched_at: float | None = None
        self._discovered_signing_key = ""
        self._fallback_decode_key = ""
        self._fallback_decode_iv = ""
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
    def _safe_endpoint(value: object, fallback: str) -> str:
        endpoint = str(value).strip().rstrip("?")
        parsed = urlsplit(endpoint)
        if parsed.scheme == "https" and parsed.hostname:
            return endpoint
        return fallback

    @staticmethod
    def _safe_timeout(value: object) -> float:
        try:
            timeout = float(value)
            if timeout != timeout or timeout in {float("inf"), float("-inf")}:
                raise ValueError
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
                raise ValueError
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

    @staticmethod
    def _md5_hex(value: str) -> str:
        return hashlib.md5(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _md5_bytes(value: str) -> bytes:
        return hashlib.md5(value.encode("utf-8")).digest()

    @classmethod
    def _sign(cls, timestamp_ms: int, key: str) -> str:
        material = (
            "client=fanyideskweb"
            f"&mysticTime={timestamp_ms}"
            "&product=webfanyi"
            f"&key={key}"
        )
        return cls._md5_hex(material)

    def _timestamp_ms(self) -> int:
        return int(self._wall_clock() * 1000)

    @staticmethod
    def _normalize_language(language: object) -> str:
        value = str(language or "").strip()
        aliases = {
            "": "",
            "auto": "auto",
            "zh": "zh-CHS",
            "zh-cn": "zh-CHS",
            "zh_cn": "zh-CHS",
            "zh-hans": "zh-CHS",
            "zh-tw": "zh-CHT",
            "zh_tw": "zh-CHT",
            "zh-hant": "zh-CHT",
            "en-us": "en",
            "en-gb": "en",
            "ja-jp": "ja",
            "jp": "ja",
            "ko-kr": "ko",
            "kr": "ko",
            "sp": "es",
        }
        return aliases.get(value.lower(), value)

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": "https://fanyi.youdao.com",
            "Referer": DEFAULT_YOUDAO_HOST,
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "User-Agent": self.user_agent,
        }

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> YoudaoWebResponse:
        return self._coerce_response(
            self._requester(
                method,
                url,
                self._headers(),
                params,
                data,
                self.timeout_seconds,
            )
        )

    def _base_payload(
        self,
        *,
        keyid: str,
        key: str,
        timestamp_ms: int,
    ) -> dict[str, str]:
        return {
            "keyid": keyid,
            "sign": self._sign(timestamp_ms, key),
            "client": "fanyideskweb",
            "product": "webfanyi",
            "appVersion": "1.0.0",
            "vendor": "web",
            "pointParam": "client,mysticTime,product",
            "mysticTime": str(timestamp_ms),
            "keyfrom": "fanyi.web",
            "mid": "1",
            "screen": "1",
            "model": "1",
            "network": "wifi",
            "abtest": "0",
            "yduuid": "abcdefg",
        }

    def _discover_browser_material(self) -> None:
        """Best-effort discovery of public signing/decode material from page JS."""

        if self._discovered_signing_key:
            return
        try:
            page = self._request("GET", DEFAULT_YOUDAO_HOST)
            if page.status_code != 200:
                return
            html_text = self._body_text(page.body)
            match = _JS_URL_PATTERN.search(html_text)
            if match is None:
                return
            js = self._request("GET", match.group(0))
            if js.status_code != 200:
                return
            js_text = self._body_text(js.body)

            for keyid in YOUDAO_KEY_IDS:
                key_match = re.search(
                    rf'="{re.escape(keyid)}",\w+="(\w+)";',
                    js_text,
                )
                if key_match:
                    self._discovered_signing_key = key_match.group(1)
                    break

            decode_key_match = re.search(r'decodeKey:"(.*?)",', js_text)
            decode_iv_match = re.search(r'decodeIv:"(.*?)",', js_text)
            if decode_key_match:
                self._fallback_decode_key = decode_key_match.group(1)
            if decode_iv_match:
                self._fallback_decode_iv = decode_iv_match.group(1)
        except Exception as exc:
            self.logger.debug(
                "youdao_web_material_discovery_failed error_type=%s",
                type(exc).__name__,
            )

    def _keys_are_fresh(self) -> bool:
        return bool(
            self._secret_key
            and self._aes_key
            and self._aes_iv
            and self._keys_fetched_at is not None
            and (self._clock() - self._keys_fetched_at) < self.key_ttl_seconds
        )

    def _ensure_keys(self, *, force: bool = False) -> None:
        if not force and self._keys_are_fresh():
            return

        self._discover_browser_material()
        signing_keys = []
        if self._discovered_signing_key:
            signing_keys.append(self._discovered_signing_key)
        signing_keys.extend(
            key for key in YOUDAO_KEY_SIGNING_FALLBACKS if key not in signing_keys
        )

        last_error: Exception | None = None
        for keyid in YOUDAO_KEY_IDS:
            for signing_key in signing_keys:
                timestamp_ms = self._timestamp_ms()
                params = self._base_payload(
                    keyid=keyid,
                    key=signing_key,
                    timestamp_ms=timestamp_ms,
                )
                try:
                    response = self._request("GET", self.key_endpoint, params=params)
                    if response.status_code < 200 or response.status_code >= 300:
                        raise WebTranslationError(
                            f"Youdao key request returned HTTP {response.status_code}"
                        )
                    payload = self._parse_json_object(response.body)
                    if str(payload.get("code", 0)) != "0":
                        raise WebTranslationError("Youdao key request rejected")
                    data = payload.get("data")
                    if not isinstance(data, Mapping):
                        raise WebTranslationError("unsupported Youdao key result")

                    secret_key = data.get("secretKey")
                    aes_key = data.get("aesKey") or self._fallback_decode_key
                    aes_iv = data.get("aesIv") or self._fallback_decode_iv
                    if not all(
                        isinstance(value, str) and value.strip()
                        for value in (secret_key, aes_key, aes_iv)
                    ):
                        raise WebTranslationError("unsupported Youdao key result")

                    self._secret_key = str(secret_key)
                    self._aes_key = str(aes_key)
                    self._aes_iv = str(aes_iv)
                    self._keys_fetched_at = self._clock()
                    self.logger.info("youdao_web_key_ready keyid=%s", keyid)
                    return
                except Exception as exc:
                    last_error = exc

        self.logger.warning("youdao_web_key_failed host=dict.youdao.com")
        raise WebTranslationError("Youdao web key request failed") from last_error

    def _build_translation_form(
        self,
        request: TranslationRequest,
        *,
        timestamp_ms: int,
    ) -> dict[str, str]:
        source = self._normalize_language(request.source_language) or "auto"
        target = self._normalize_language(request.target_language) or "zh-CHS"
        form = {
            "i": request.source_text,
            "from": source,
            "to": target,
            "useTerm": "false",
            "domain": "0",
            "dictResult": "true",
        }
        form.update(
            self._base_payload(
                keyid="webfanyi",
                key=self._secret_key,
                timestamp_ms=timestamp_ms,
            )
        )
        return form

    def translate(self, request: TranslationRequest) -> TranslationResult:
        if not self.enabled:
            raise WebTranslationError("Youdao web translation is disabled")

        self._ensure_keys()
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._wait_for_rate_limit()
            try:
                timestamp_ms = self._timestamp_ms()
                response = self._request(
                    "POST",
                    self.endpoint,
                    data=self._build_translation_form(
                        request,
                        timestamp_ms=timestamp_ms,
                    ),
                )
                if response.status_code in TRANSIENT_HTTP_STATUSES:
                    raise WebTranslationError(
                        f"Youdao translation returned HTTP {response.status_code}"
                    )
                if response.status_code < 200 or response.status_code >= 300:
                    raise WebTranslationError(
                        f"Youdao translation returned HTTP {response.status_code}"
                    )
                payload = self._decrypt_response(response.body)
                if str(payload.get("code", 0)) != "0":
                    raise WebTranslationError("Youdao web translation request failed")
                return self._result_from_payload(payload, request)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    self.logger.info(
                        "youdao_web_retry attempt=%s error_type=%s host=%s",
                        attempt + 1,
                        type(exc).__name__,
                        self.endpoint_host,
                    )
                    self._ensure_keys(force=True)
                    self._sleep(self._retry_delay(attempt))
                    continue
                self.logger.warning(
                    "youdao_web_request_failed error_type=%s host=%s attempts=%s",
                    type(exc).__name__,
                    self.endpoint_host,
                    attempt + 1,
                )
                raise WebTranslationError(
                    "Youdao web translation request failed"
                ) from exc

        raise WebTranslationError("Youdao web translation request failed") from last_error

    def _decrypt_response(self, body: bytes | str) -> Mapping[str, object]:
        if not (self._aes_key and self._aes_iv):
            raise WebTranslationError("Youdao AES keys are unavailable")
        try:
            encoded = self._body_text(body).strip()
            encoded += "=" * (-len(encoded) % 4)
            ciphertext = base64.b64decode(
                encoded.encode("ascii"),
                altchars=b"-_",
                validate=False,
            )
            cipher = AES.new(
                self._md5_bytes(self._aes_key),
                AES.MODE_CBC,
                self._md5_bytes(self._aes_iv),
            )
            plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
            payload = json.loads(plaintext.decode("utf-8"))
        except Exception as exc:
            raise WebTranslationError(
                "unsupported Youdao web translation result"
            ) from exc
        if not isinstance(payload, Mapping):
            raise WebTranslationError("unsupported Youdao web translation result")
        return payload

    @classmethod
    def _result_from_payload(
        cls,
        payload: Mapping[str, object],
        request: TranslationRequest,
    ) -> TranslationResult:
        translated_text = cls._extract_translation(payload)
        if not translated_text.strip():
            raise WebTranslationError("unsupported Youdao web translation result")
        detected = cls._detected_source_language(payload)
        return TranslationResult(
            source_text=request.source_text,
            translated_text=translated_text,
            source_language=(
                detected
                if request.source_language == "auto" and detected
                else request.source_language
            ),
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
                if isinstance(segment, Mapping) and isinstance(segment.get("tgt"), str):
                    fragments.append(str(segment["tgt"]))
        return "".join(fragments)

    @staticmethod
    def _detected_source_language(payload: Mapping[str, object]) -> str | None:
        translation_type = payload.get("type")
        if not isinstance(translation_type, str) or "2" not in translation_type:
            return None
        source_code = translation_type.split("2", 1)[0].upper()
        return YOUDAO_SOURCE_LANGUAGE_MAP.get(source_code)

    @staticmethod
    def _body_text(body: bytes | str) -> str:
        return body.decode("utf-8", errors="strict") if isinstance(body, bytes) else str(body)

    @classmethod
    def _parse_json_object(cls, body: bytes | str) -> Mapping[str, object]:
        try:
            payload = json.loads(cls._body_text(body))
        except Exception as exc:
            raise WebTranslationError("unsupported Youdao JSON result") from exc
        if not isinstance(payload, Mapping):
            raise WebTranslationError("unsupported Youdao JSON result")
        return payload

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

    @staticmethod
    def _coerce_response(
        response: YoudaoWebResponse | tuple[int, bytes | str],
    ) -> YoudaoWebResponse:
        if isinstance(response, YoudaoWebResponse):
            return response
        if isinstance(response, tuple) and len(response) == 2:
            return YoudaoWebResponse(int(response[0]), response[1])
        raise TypeError("unsupported Youdao web response")


__all__ = [
    "DEFAULT_KEY_TTL_SECONDS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MIN_INTERVAL_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_YOUDAO_HOST",
    "DEFAULT_YOUDAO_KEY_ENDPOINT",
    "DEFAULT_YOUDAO_WEB_ENDPOINT",
    "YOUDAO_KEY_IDS",
    "YoudaoWebResponse",
    "YoudaoWebTranslationProvider",
]
