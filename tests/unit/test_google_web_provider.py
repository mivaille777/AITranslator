"""Offline tests for the optional Google Translate web-compatible provider."""

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
    assert urlparse(DEFAULT_WEB_ENDPOINT).hostname == "translate.googleapis.com"


def test_legacy_translate_google_endpoint_is_migrated_in_memory() -> None:
    provider = GoogleWebTranslationProvider(
        endpoint="https://translate.google.com/translate_a/single",
        requester=lambda *_args: WebResponse(200, "[]"),
    )

    assert provider.endpoint == DEFAULT_WEB_ENDPOINT


def test_web_provider_builds_current_gtx_request_and_parses_segments() -> None:
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
    assert len(calls) == 1
    query = parse_qs(urlparse(calls[0][0]).query)
    assert query == {
        "client": ["gtx"],
        "sl": ["en"],
        "tl": ["zh-CN"],
        "dt": list(WEB_TRANSLATION_TYPES),
        "q": ["Hello world"],
    }
    assert "tk" not in query
    assert "source" not in query
    assert "ssel" not in query
    assert "tsel" not in query
    assert "kc" not in query
    assert "Hello world" not in calls[0][1].get("User-Agent", "")
    assert calls[0][2] == 3


def test_web_provider_retries_transient_status_without_logging_source_text() -> None:
    responses = iter(
        [
            WebResponse(429, ""),
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


def test_persistent_requester_reuses_the_warm_connection(monkeypatch) -> None:
    created: list[object] = []

    class FakeResponse:
        status = 200
        will_close = False

        def read(self):
            return b"[]"

    class FakeConnection:
        def __init__(self, *_args, **_kwargs) -> None:
            self.request_count = 0
            self.timeout = None

        def request(self, *_args, **_kwargs) -> None:
            self.request_count += 1

        def getresponse(self):
            return FakeResponse()

        def close(self) -> None:
            pass

    def make_connection(*_args, **_kwargs):
        connection = FakeConnection()
        created.append(connection)
        return connection

    monkeypatch.setattr(web_module, "HTTPSConnection", make_connection)
    transport = web_module._PersistentWebRequester()

    first = transport("https://example.test/translate?q=one", {}, 2.0)
    second = transport("https://example.test/translate?q=two", {}, 2.0)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(created) == 1
    assert created[0].request_count == 2
    transport.close()


def test_persistent_requester_reconnects_once_when_reused_socket_is_stale(monkeypatch) -> None:
    created: list[object] = []

    class FakeResponse:
        status = 200
        will_close = False

        def read(self):
            return b"[]"

    class FakeConnection:
        def __init__(self, ordinal: int) -> None:
            self.ordinal = ordinal
            self.request_count = 0
            self.timeout = None

        def request(self, *_args, **_kwargs) -> None:
            self.request_count += 1
            if self.ordinal == 0 and self.request_count == 2:
                raise OSError("stale keep-alive")

        def getresponse(self):
            return FakeResponse()

        def close(self) -> None:
            pass

    def make_connection(*_args, **_kwargs):
        connection = FakeConnection(len(created))
        created.append(connection)
        return connection

    monkeypatch.setattr(web_module, "HTTPSConnection", make_connection)
    transport = web_module._PersistentWebRequester()

    assert transport("https://example.test/translate?q=one", {}, 2.0).status_code == 200
    second = transport("https://example.test/translate?q=two", {}, 2.0)

    assert second.status_code == 200
    assert len(created) == 2
    assert created[0].request_count == 2
    assert created[1].request_count == 1
    transport.close()


def test_reconfiguring_web_provider_replaces_provider_and_clears_cache(
    tmp_path,
) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    default_path.write_text(
        """
[translation]
source_language = "auto"
target_language = "zh-CN"

[google_web]
enabled = true
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
    assert manager.cache.size == 0
