"""Offline tests for the Google Translate browser-web provider."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse
from unittest.mock import MagicMock

import pytest

from app.infrastructure.settings import SettingsManager
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.errors import WebTranslationError
from app.translation import google_web_provider as web_module
from app.translation.google_web_provider import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_MIN_INTERVAL_SECONDS,
    DEFAULT_WEB_ENDPOINT,
    GoogleWebTranslationProvider,
    WEB_TRANSLATION_TYPES,
    WebResponse,
)
from app.translation.manager import TranslationManager


def _request() -> TranslationRequest:
    return TranslationRequest(
        source_text="Hello world",
        source_language="en",
        target_language="zh-CN",
        request_id=7,
    )


def test_live_translation_defaults_include_bounded_retry_and_spacing() -> None:
    assert DEFAULT_MAX_RETRIES == 1
    assert DEFAULT_MIN_INTERVAL_SECONDS >= 0.1
    assert urlparse(DEFAULT_WEB_ENDPOINT).hostname == "translate.google.com"


def test_legacy_google_endpoints_are_migrated_to_browser_web_route() -> None:
    for legacy_endpoint in (
        "http://translate.google.com/translate_a/single",
        "http://translate.googleapis.com/translate_a/single",
        "https://translate.googleapis.com/translate_a/single",
    ):
        provider = GoogleWebTranslationProvider(
            endpoint=legacy_endpoint,
            requester=lambda *_args: WebResponse(200, "[]"),
        )
        assert provider.endpoint == DEFAULT_WEB_ENDPOINT


def test_google_token_matches_browser_algorithm_for_utf8_text() -> None:
    assert GoogleWebTranslationProvider._token("Hello world") == "814953.678685"
    assert GoogleWebTranslationProvider._token("你好") == "964583.557971"


def test_web_provider_builds_zotero_style_gtx_request_and_parses_segments() -> None:
    calls: list[tuple[str, dict[str, str], float]] = []

    def requester(url, headers, timeout):
        calls.append((url, dict(headers), timeout))
        return WebResponse(
            200,
            json.dumps(
                [
                    [["你好 &amp;", "Hello", None], ["世界", "world", None]],
                    None,
                    "en",
                ]
            ),
        )

    provider = GoogleWebTranslationProvider(
        endpoint="https://example.test/translate",
        timeout_seconds=3,
        min_interval_seconds=0,
        requester=requester,
    )

    result = provider.translate(_request())

    assert result == TranslationResult(
        source_text="Hello world",
        translated_text="你好 &世界",
        source_language="en",
        target_language="zh-CN",
        provider="google_web",
        request_id=7,
    )
    query = parse_qs(urlparse(calls[0][0]).query)
    assert query["client"] == ["gtx"]
    assert query["sl"] == ["en"]
    assert query["tl"] == ["zh-CN"]
    assert query["hl"] == ["en"]
    assert query["dt"] == list(WEB_TRANSLATION_TYPES)
    assert query["source"] == ["bh"]
    assert query["ssel"] == ["0"]
    assert query["tsel"] == ["0"]
    assert query["kc"] == ["1"]
    assert query["tk"] == ["814953.678685"]
    assert query["q"] == ["Hello world"]
    assert calls[0][1]["Referer"] == "https://translate.google.com/"
    assert "Hello world" not in calls[0][1].get("User-Agent", "")
    assert calls[0][2] == 3


def test_requests_transport_follows_redirects_and_keeps_final_metadata() -> None:
    calls = []

    class FakeResponse:
        status_code = 200
        content = b"[]"
        url = "https://translate.google.com/final"
        headers = {"content-type": "application/json"}

    class FakeSession:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse()

        def close(self):
            pass

    transport = web_module._RequestsWebRequester(FakeSession())
    response = transport("https://example.test/x", {"A": "B"}, 2.0)

    assert response.status_code == 200
    assert response.final_url == "https://translate.google.com/final"
    assert response.content_type == "application/json"
    assert calls[0][1]["allow_redirects"] is True
    assert calls[0][1]["timeout"] == 2.0
    transport.close()


def test_google_sorry_redirect_is_reported_as_challenge_without_retry() -> None:
    logger = MagicMock()
    provider = GoogleWebTranslationProvider(
        min_interval_seconds=0,
        max_retries=1,
        requester=lambda *_args: WebResponse(
            429,
            "<html>Our systems have detected unusual traffic</html>",
            final_url="https://www.google.com/sorry/index?continue=redacted",
            content_type="text/html; charset=UTF-8",
        ),
        logger=logger,
    )

    with pytest.raises(WebTranslationError, match="challenged"):
        provider.translate(_request())

    assert any("google_web_challenge" in str(call) for call in logger.mock_calls)
    assert all("Hello world" not in str(call) for call in logger.mock_calls)


def test_web_provider_retries_transient_status_without_logging_source_text() -> None:
    responses = iter(
        [
            WebResponse(503, ""),
            WebResponse(
                200,
                json.dumps([[["你好", "hello", None]], None, "en"]),
            ),
        ]
    )
    sleep_calls: list[float] = []
    logger = MagicMock()

    provider = GoogleWebTranslationProvider(
        min_interval_seconds=0,
        max_retries=1,
        requester=lambda *_args: next(responses),
        sleep_function=sleep_calls.append,
        logger=logger,
    )

    result = provider.translate(_request())

    assert result.translated_text == "你好"
    assert sleep_calls == [pytest.approx(0.25)]
    assert all("Hello world" not in str(call) for call in logger.mock_calls)


def test_non_success_status_is_logged_without_source_text() -> None:
    logger = MagicMock()
    provider = GoogleWebTranslationProvider(
        min_interval_seconds=0,
        requester=lambda *_args: WebResponse(403, "forbidden"),
        logger=logger,
    )

    with pytest.raises(WebTranslationError, match="request failed"):
        provider.translate(_request())

    assert any("google_web_http_failed" in str(call) for call in logger.mock_calls)
    assert any("403" in str(call) for call in logger.mock_calls)
    assert all("Hello world" not in str(call) for call in logger.mock_calls)


def test_web_provider_rejects_malformed_or_non_success_responses() -> None:
    malformed = GoogleWebTranslationProvider(
        min_interval_seconds=0,
        requester=lambda *_args: WebResponse(200, "not json"),
    )
    with pytest.raises(WebTranslationError, match="unsupported"):
        malformed.translate(_request())

    failed = GoogleWebTranslationProvider(
        min_interval_seconds=0,
        requester=lambda *_args: WebResponse(400, ""),
    )
    with pytest.raises(WebTranslationError, match="request failed"):
        failed.translate(_request())


def test_web_provider_can_be_disabled_without_network_access() -> None:
    provider = GoogleWebTranslationProvider(
        enabled=False,
        requester=lambda *_args: pytest.fail("network must not be called"),
    )

    with pytest.raises(WebTranslationError, match="disabled"):
        provider.translate(_request())


def test_reconfiguring_web_provider_replaces_provider_and_clears_cache(tmp_path) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    default_path.write_text(
        """
[translation]
source_language = "auto"
target_language = "zh-CN"

[google_web]
enabled = true
endpoint = "https://translate.google.com/translate_a/single"
timeout_ms = 8000
max_retries = 0
min_interval_ms = 0
""",
        encoding="utf-8",
    )
    settings = SettingsManager(default_path, user_path)
    manager = TranslationManager(config_manager=settings)
    manager.cache.set(
        "auto",
        "zh-CN",
        "hello",
        TranslationResult(
            source_text="hello",
            translated_text="你好",
            provider="google",
        ),
    )

    settings.save({"google_web": {"timeout_ms": 9000}})
    assert manager.configure_provider()

    assert isinstance(manager.provider, GoogleWebTranslationProvider)
    assert manager.provider.endpoint == DEFAULT_WEB_ENDPOINT
    assert manager.cache.size == 0
