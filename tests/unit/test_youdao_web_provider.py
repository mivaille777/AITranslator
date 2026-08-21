"""Offline tests for the current Youdao WebFanyi provider."""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import urlparse
from unittest.mock import MagicMock

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import pytest

from app.infrastructure.settings import SettingsManager
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.errors import WebTranslationError
from app.translation.manager import TranslationManager
from app.translation.youdao_web_provider import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_MIN_INTERVAL_SECONDS,
    DEFAULT_YOUDAO_KEY_ENDPOINT,
    DEFAULT_YOUDAO_WEB_ENDPOINT,
    YoudaoWebResponse,
    YoudaoWebTranslationProvider,
)


def _request(
    *,
    source: str = "en",
    target: str = "zh-CN",
    text: str = "Hello world",
) -> TranslationRequest:
    return TranslationRequest(
        source_text=text,
        source_language=source,
        target_language=target,
        request_id=7,
    )


def _encrypted_payload(
    payload: dict,
    *,
    aes_key: str = "test-aes-key",
    aes_iv: str = "test-aes-iv",
) -> str:
    key = hashlib.md5(aes_key.encode("utf-8")).digest()
    iv = hashlib.md5(aes_iv.encode("utf-8")).digest()
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ciphertext = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plaintext, AES.block_size))
    return base64.urlsafe_b64encode(ciphertext).decode("ascii")


def _success_payload() -> dict:
    return {
        "code": 0,
        "type": "EN2ZH-CHS",
        "translateResult": [
            [
                {"src": "Hello ", "tgt": "你好"},
                {"src": "world", "tgt": "世界"},
            ]
        ],
    }


def _full_flow_requester(calls: list, *, translated_payload: dict | None = None):
    payload = translated_payload or _success_payload()

    def requester(method, url, headers, params, data, timeout):
        calls.append(
            (
                method,
                url,
                dict(headers),
                None if params is None else dict(params),
                None if data is None else dict(data),
                timeout,
            )
        )
        if url == "https://fanyi.youdao.com/":
            return YoudaoWebResponse(200, "<html></html>", content_type="text/html")
        if url == DEFAULT_YOUDAO_KEY_ENDPOINT:
            return YoudaoWebResponse(
                200,
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "secretKey": "test-secret-key",
                            "aesKey": "test-aes-key",
                            "aesIv": "test-aes-iv",
                        },
                    }
                ),
                content_type="application/json",
            )
        if url == DEFAULT_YOUDAO_WEB_ENDPOINT:
            return YoudaoWebResponse(
                200,
                _encrypted_payload(payload),
                content_type="text/plain",
            )
        raise AssertionError(f"unexpected URL: {url}")

    return requester


def test_youdao_defaults_use_current_webtranslate_endpoints() -> None:
    assert DEFAULT_MAX_RETRIES == 1
    assert DEFAULT_MIN_INTERVAL_SECONDS >= 0.1
    assert urlparse(DEFAULT_YOUDAO_WEB_ENDPOINT).hostname == "dict.youdao.com"
    assert urlparse(DEFAULT_YOUDAO_KEY_ENDPOINT).hostname == "dict.youdao.com"
    assert DEFAULT_YOUDAO_WEB_ENDPOINT.endswith("/webtranslate")
    assert DEFAULT_YOUDAO_KEY_ENDPOINT.endswith("/webtranslate/key")


def test_youdao_sign_matches_browser_formula() -> None:
    timestamp = 1_725_000_000_123
    key = "abc123"
    expected = hashlib.md5(
        (
            "client=fanyideskweb"
            f"&mysticTime={timestamp}"
            "&product=webfanyi"
            f"&key={key}"
        ).encode("utf-8")
    ).hexdigest()

    assert YoudaoWebTranslationProvider._sign(timestamp, key) == expected


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("auto", "auto"),
        ("zh-CN", "zh-CHS"),
        ("zh-TW", "zh-CHT"),
        ("en-US", "en"),
        ("en", "en"),
        ("jp", "ja"),
        ("kr", "ko"),
    ],
)
def test_youdao_language_normalization(language: str, expected: str) -> None:
    assert YoudaoWebTranslationProvider._normalize_language(language) == expected


def test_youdao_full_key_sign_post_decrypt_flow() -> None:
    calls: list = []
    provider = YoudaoWebTranslationProvider(
        timeout_seconds=3,
        min_interval_seconds=0,
        max_retries=0,
        requester=_full_flow_requester(calls),
        wall_clock=lambda: 1_725_000_000.123,
    )

    result = provider.translate(_request())

    assert result == TranslationResult(
        source_text="Hello world",
        translated_text="你好世界",
        source_language="en",
        target_language="zh-CN",
        provider="youdao_web",
        request_id=7,
    )

    key_calls = [call for call in calls if call[1] == DEFAULT_YOUDAO_KEY_ENDPOINT]
    post_calls = [call for call in calls if call[1] == DEFAULT_YOUDAO_WEB_ENDPOINT]
    assert len(key_calls) == 1
    assert len(post_calls) == 1

    _, _, _, key_params, _, _ = key_calls[0]
    assert key_params is not None
    assert key_params["keyid"] == "webfanyi-key-getter-2025"
    assert key_params["client"] == "fanyideskweb"
    assert key_params["product"] == "webfanyi"
    assert key_params["mysticTime"] == "1725000000123"

    method, _, headers, _, form, timeout = post_calls[0]
    assert method == "POST"
    assert form is not None
    assert form["i"] == "Hello world"
    assert form["from"] == "en"
    assert form["to"] == "zh-CHS"
    assert form["keyid"] == "webfanyi"
    assert form["sign"] == YoudaoWebTranslationProvider._sign(
        1_725_000_000_123,
        "test-secret-key",
    )
    assert headers["Origin"] == "https://fanyi.youdao.com"
    assert "Hello world" not in headers["User-Agent"]
    assert timeout == 3


def test_youdao_cached_key_bundle_is_reused_between_translations() -> None:
    calls: list = []
    provider = YoudaoWebTranslationProvider(
        min_interval_seconds=0,
        max_retries=0,
        requester=_full_flow_requester(calls),
        clock=lambda: 100.0,
        wall_clock=lambda: 1_725_000_000.123,
    )

    provider.translate(_request(text="one"))
    provider.translate(_request(text="two"))

    key_calls = [call for call in calls if call[1] == DEFAULT_YOUDAO_KEY_ENDPOINT]
    post_calls = [call for call in calls if call[1] == DEFAULT_YOUDAO_WEB_ENDPOINT]
    assert len(key_calls) == 1
    assert len(post_calls) == 2


def test_youdao_auto_source_uses_detected_language() -> None:
    calls: list = []
    provider = YoudaoWebTranslationProvider(
        min_interval_seconds=0,
        max_retries=0,
        requester=_full_flow_requester(calls),
    )

    result = provider.translate(_request(source="auto"))

    assert result.source_language == "en"
    assert result.target_language == "zh-CN"


def test_youdao_invalid_encrypted_response_does_not_log_source_text() -> None:
    logger = MagicMock()

    def requester(method, url, headers, params, data, timeout):
        if url == "https://fanyi.youdao.com/":
            return YoudaoWebResponse(200, "<html></html>")
        if url == DEFAULT_YOUDAO_KEY_ENDPOINT:
            return YoudaoWebResponse(
                200,
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "secretKey": "secret",
                            "aesKey": "aes",
                            "aesIv": "iv",
                        },
                    }
                ),
            )
        return YoudaoWebResponse(200, "not-encrypted-json")

    provider = YoudaoWebTranslationProvider(
        min_interval_seconds=0,
        max_retries=0,
        requester=requester,
        logger=logger,
    )

    with pytest.raises(WebTranslationError, match="request failed"):
        provider.translate(_request())

    assert all("Hello world" not in str(call) for call in logger.mock_calls)


def test_youdao_can_be_disabled_without_network_access() -> None:
    provider = YoudaoWebTranslationProvider(
        enabled=False,
        requester=lambda *_args: pytest.fail("network must not be called"),
    )

    with pytest.raises(WebTranslationError, match="disabled"):
        provider.translate(_request())


def test_translation_manager_selects_youdao_from_settings(tmp_path) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    default_path.write_text(
        """
[translation]
provider = "youdao_web"
source_language = "auto"
target_language = "zh-CN"

[youdao_web]
enabled = true
endpoint = "https://dict.youdao.com/webtranslate"
timeout_ms = 8000
max_retries = 1
min_interval_ms = 200
""",
        encoding="utf-8",
    )

    settings = SettingsManager(default_path, user_path)
    manager = TranslationManager(
        config_manager=settings,
        sqlite_enabled=False,
    )
    try:
        assert isinstance(manager.provider, YoudaoWebTranslationProvider)
        assert manager.provider_name == "youdao_web"
        assert manager.provider.endpoint == DEFAULT_YOUDAO_WEB_ENDPOINT
    finally:
        manager.close()
