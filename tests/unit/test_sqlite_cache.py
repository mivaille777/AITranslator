"""Step18 SQLite L2 cache and privacy-boundary tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.cache import TranslationCache
from app.translation.manager import TranslationManager


class CountingProvider(TranslationProvider):
    def __init__(self) -> None:
        self.calls: list[TranslationRequest] = []

    def translate(self, request: TranslationRequest) -> TranslationResult:
        self.calls.append(request)
        return TranslationResult(
            source_text=request.source_text,
            translated_text=f"l2:{request.source_text}",
            source_language=request.source_language,
            target_language=request.target_language,
            provider="counting",
            request_id=request.request_id,
        )


def test_second_manager_reads_success_from_sqlite_l2_without_raw_source(
    tmp_path: Path,
) -> None:
    database = tmp_path / "translations.sqlite3"
    first_provider = CountingProvider()
    first_manager = TranslationManager(
        provider=first_provider,
        sqlite_enabled=True,
        sqlite_path=database,
    )

    first = first_manager.translate("  hello\r\n")
    first_manager.close()

    second_provider = CountingProvider()
    second_manager = TranslationManager(
        provider=second_provider,
        sqlite_enabled=True,
        sqlite_path=database,
    )
    second = second_manager.translate("hello")

    assert first.translated_text == second.translated_text
    assert second_provider.calls == []
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT source_text, translated_text FROM translations"
        ).fetchone()
    assert row == (None, "l2:hello")
    second_manager.close()


def test_history_mode_explicitly_persists_source_text(tmp_path: Path) -> None:
    manager = TranslationManager(
        provider=CountingProvider(),
        sqlite_enabled=True,
        sqlite_path=tmp_path / "history.sqlite3",
        history_enabled=True,
    )

    manager.translate("history text")

    entries = manager.cache.list_history()
    assert len(entries) == 1
    assert entries[0].source_text == "history text"
    assert entries[0].translated_text == "l2:history text"
    manager.close()


def test_disabling_history_removes_previously_persisted_source_text(
    tmp_path: Path,
) -> None:
    database = tmp_path / "toggle.sqlite3"
    manager = TranslationManager(
        provider=CountingProvider(),
        sqlite_enabled=True,
        sqlite_path=database,
        history_enabled=True,
    )
    manager.translate("private text")

    manager.configure_cache(history_enabled=False)

    with sqlite3.connect(database) as connection:
        source_text = connection.execute(
            "SELECT source_text FROM translations"
        ).fetchone()[0]
    assert source_text is None
    assert manager.cache.list_history() == []
    manager.close()


def test_corrupted_sqlite_database_falls_back_to_l1(tmp_path: Path) -> None:
    database = tmp_path / "corrupted.sqlite3"
    database.write_bytes(b"not a sqlite database")
    cache = TranslationCache(
        sqlite_enabled=True,
        sqlite_path=database,
    )
    result = TranslationResult(
        source_text="hello",
        translated_text="你好",
        provider="test",
    )

    cache.set("auto", "zh-CN", "hello", result)

    assert cache.persistent_available is False
    assert cache.get("auto", "zh-CN", "hello") == result
    cache.clear()
    cache.close()
