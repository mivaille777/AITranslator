"""Step10 in-memory translation cache tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.infrastructure.config import ConfigManager
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.cache import TranslationCache
from app.translation.errors import TranslationError
from app.translation.manager import TranslationManager


class CountingProvider(TranslationProvider):
    def __init__(self) -> None:
        self.calls: list[TranslationRequest] = []

    def translate(self, request: TranslationRequest) -> TranslationResult:
        self.calls.append(request)
        return TranslationResult(
            source_text=request.source_text,
            translated_text=f"translated:{request.source_text}",
            source_language=request.source_language,
            target_language=request.target_language,
            provider="counting",
            request_id=request.request_id,
        )


class FailingProvider(TranslationProvider):
    def __init__(self) -> None:
        self.calls = 0

    def translate(self, _request: TranslationRequest) -> TranslationResult:
        self.calls += 1
        raise TranslationError("temporary provider failure")


def test_repeated_text_uses_cache_and_refreshes_request_id() -> None:
    provider = CountingProvider()
    logger = MagicMock()
    manager = TranslationManager(
        provider=provider,
        cache=TranslationCache(max_size=4),
        logger=logger,
    )

    first = manager.translate("hello", request_id=1)
    second = manager.translate("hello", request_id=2)

    assert len(provider.calls) == 1
    assert first.translated_text == second.translated_text
    assert second.request_id == 2
    cache_events = [
        call.args[0]
        for call in logger.info.call_args_list
        if call.args and call.args[0].startswith("CACHE_")
    ]
    assert cache_events == ["CACHE_MISS request_id=%s", "CACHE_HIT request_id=%s"]


def test_different_target_language_is_a_cache_miss() -> None:
    provider = CountingProvider()
    manager = TranslationManager(
        provider=provider,
        cache=TranslationCache(max_size=4),
    )

    manager.translate("hello", target_language="zh-CN")
    manager.translate("hello", target_language="de")

    assert len(provider.calls) == 2


def test_normalized_cache_key_hits_for_outer_whitespace_and_newlines() -> None:
    provider = CountingProvider()
    manager = TranslationManager(
        provider=provider,
        cache=TranslationCache(max_size=4),
    )

    manager.translate("  hello\r\n")
    cached = manager.translate("hello")

    assert len(provider.calls) == 1
    assert cached.source_text == "hello"


def test_lru_cache_evicts_least_recently_used_entry() -> None:
    provider = CountingProvider()
    manager = TranslationManager(
        provider=provider,
        cache=TranslationCache(max_size=2),
    )

    manager.translate("a")
    manager.translate("b")
    manager.translate("a")  # Refresh a, so b is the LRU entry.
    manager.translate("c")
    manager.translate("b")  # b was evicted and must call the provider again.

    assert [request.source_text for request in provider.calls] == [
        "a",
        "b",
        "c",
        "b",
    ]


def test_provider_failures_are_not_cached() -> None:
    provider = FailingProvider()
    manager = TranslationManager(
        provider=provider,
        cache=TranslationCache(max_size=4),
    )

    with pytest.raises(TranslationError):
        manager.translate("hello")
    with pytest.raises(TranslationError):
        manager.translate("hello")

    assert provider.calls == 2
    assert manager.cache.size == 0


def test_cache_can_be_disabled_by_constructor() -> None:
    provider = CountingProvider()
    manager = TranslationManager(
        provider=provider,
        cache=TranslationCache(max_size=4, enabled=False),
    )

    manager.translate("hello")
    manager.translate("hello")

    assert len(provider.calls) == 2
    assert manager.cache.size == 0


def test_cache_configuration_can_disable_cache(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        "[translation]\n"
        "cache_enabled = false\n"
        "cache_max_size = 3\n"
        "max_text_length = 7\n",
        encoding="utf-8",
    )
    config = ConfigManager(config_path)

    manager = TranslationManager(
        provider=CountingProvider(),
        config_manager=config,
    )

    assert manager.cache.enabled is False
    assert manager.cache.max_size == 3
    assert manager.text_normalizer.max_length == 7
