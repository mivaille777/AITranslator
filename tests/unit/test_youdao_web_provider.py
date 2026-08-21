"""Offline tests for the Youdao web-compatible translation provider."""

from __future__ import annotations

import json
from urllib.parse import urlparse
from unittest.mock import MagicMock

import pytest

from app.infrastructure.settings import SettingsManager
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.errors import WebTranslationError
from app.translation.manager import TranslationManager
from app.translation.youdao_web_provider import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_MIN_INTERVAL_SECONDS,
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


def _success_body(
    *,
    source: str = "Hello world",
    target: str = "你好世界",
    translation_type: str = "EN2ZH_CN",
) -> str:
    return json.dumps(
        {
            "type": translation_type,
            "errorCode": 0,
            "translateResult": [[{"src": source, "tgt": target}]],
        },
        ensure_ascii=False,
    )


def test_youdao_defaults_are_bounded_and_https() -> None:
    assert DEFAULT_MAX_RETRIES == 1
    assert DEFAULT_MIN_INTERVAL_SECONDS >= 0.1
    parsed = urlparse(DEFAULT_YOUDAO_WEB_ENDPOINT)
    assert parsed.scheme == "https"
    assert parsed.hostname == "fanyi.youdao.com"


def test_youdao_provider_builds_zotero_style_get_query_and_parses_segments() -> None:
    calls: list[tuple[str, dict[str, str], dict[str, str], float]] = []

    def requester(url, headers, query, timeout):
        calls.append((url, dict(headers), dict(query), timeout))
        return YoudaoWebResponse(
            200,
            json.dumps(
                {
                    "type": "EN2ZH_CN",
                    "errorCode": 0,
                    "translateResult": [
                        [
                            {"src": "Hello ", "tgt": "你好"},
                            {"src": "world", "tgt": "世界"},
                        ]
                    ],
                },
                ensure_ascii=False,
            ),
        )

    provider = YoudaoWebTranslationProvider(
        endpoint="https://example.test/translate",
        timeout_seconds=3,
        min_interval_seconds=0,
        requester=requester,
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
    assert len(calls) == 1
    url, headers, query, timeout = calls[0]
    assert url == "https://example.test/translate"
    assert query == {
        "doctype": "json",
        "type": "EN2ZH_CN",
        "i": "Hello world",
    }
    assert headers["Referer"] == "https://fanyi.youdao.com/"
    assert "Hello world" not in headers["User-Agent"]
    assert timeout == 3


@pytest.mark.parametrize(
    ("source", "target", "expected"),
    [
        ("en", "zh-CN", "EN2ZH_CN"),
        ("zh-CN", "en", "ZH_CN2EN"),
        ("ja", "zh-CN", "JA2ZH_CN"),
        ("zh-CN", "ja", "ZH_CN2JA"),
        ("ko", "zh-CN", "KR2ZH_CN"),
        ("zh-CN", "ko", "ZH_CN2KR"),
        ("fr", "zh-CN", "FR2ZH_CN"),
        ("zh-CN", "fr", "ZH_CN2FR"),
        ("ru", "zh-CN", "RU2ZH_CN"),
        ("zh-CN", "ru", "ZH_CN2RU"),
        ("es", "zh-CN", "SP2ZH_CN"),
        ("zh-CN", "es", "ZH_CN2SP"),
        ("auto", "zh-CN", "AUTO"),
        ("de", "zh-CN", "AUTO"),
    ],
)
def test_youdao_language_pair_mapping(
    source: str,
    target: str,
    expected: str,
) -> None:
    assert YoudaoWebTranslationProvider._translation_type(source, target) == expected


def test_youdao_auto_source_uses_detected_language() -> None:
    provider = YoudaoWebTranslationProvider(
        min_interval_seconds=0,
        requester=lambda *_args: YoudaoWebResponse(
            200,
            _success_body(translation_type="EN2ZH_CN"),
        ),
    )

    result = provider.translate(_request(source="auto"))

    assert result.source_language == "en"
    assert result.target_language == "zh-CN"


def test_youdao_retries_transient_status_without_logging_source_text() -> None:
    responses = iter(
        [
            YoudaoWebResponse(429, ""),
            YoudaoWebResponse(200, _success_body()),
        ]
    )
    sleep_calls: list[float] = []
    logger = MagicMock()

    provider = YoudaoWebTranslationProvider(
        min_interval_seconds=0,
        max_retries=1,
        requester=lambda *_args: next(responses),
        sleep_function=sleep_calls.append,
        logger=logger,
    )

    result = provider.translate(_request())

    assert result.translated_text == "你好世界"
    assert sleep_calls == [pytest.approx(0.25)]
    assert all("Hello world" not in str(call) for call in logger.mock_calls)


def test_youdao_nonzero_error_code_is_rejected() -> None:
    logger = MagicMock()
    provider = YoudaoWebTranslationProvider(
        min_interval_seconds=0,
        requester=lambda *_args: YoudaoWebResponse(
            200,
            json.dumps({"errorCode": 50, "translateResult": []}),
        ),
        logger=logger,
    )

    with pytest.raises(WebTranslationError, match="request failed"):
        provider.translate(_request())

    assert all("Hello world" not in str(call) for call in logger.mock_calls)


def test_youdao_rejects_malformed_or_empty_responses() -> None:
    malformed = YoudaoWebTranslationProvider(
        min_interval_seconds=0,
        requester=lambda *_args: YoudaoWebResponse(200, "not json"),
    )
    with pytest.raises(WebTranslationError, match="unsupported"):
        malformed.translate(_request())

    empty = YoudaoWebTranslationProvider(
        min_interval_seconds=0,
        requester=lambda *_args: YoudaoWebResponse(
            200,
            json.dumps({"errorCode": 0, "translateResult": []}),
        ),
    )
    with pytest.raises(WebTranslationError, match="unsupported"):
        empty.translate(_request())


def test_youdao_can_be_disabled_without_network_access() -> None:
    provider = YoudaoWebTranslationProvider(
        enabled=False,
        requester=lambda *_args: pytest.fail("network must not be called"),
    )

    with pytest.raises(WebTranslationError, match="disabled"):
        provider.translate(_request())


def test_youdao_http_endpoint_is_only_used_when_explicitly_configured() -> None:
    provider = YoudaoWebTranslationProvider(
        endpoint="http://fanyi.youdao.com/translate",
        min_interval_seconds=0,
        requester=lambda *_args: YoudaoWebResponse(200, _success_body()),
    )
    try:
        assert provider.endpoint == "http://fanyi.youdao.com/translate"
    finally:
        provider.close()


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
endpoint = "https://fanyi.youdao.com/translate"
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
    finally:
        manager.close()
