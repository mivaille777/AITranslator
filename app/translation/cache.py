"""Two-level cache for successful translations.

The memory LRU is the fast path.  An optional SQLite store provides a small
cross-process/cross-manager L2 cache, while remaining best-effort: a damaged
or locked database is disabled and never prevents the L1 cache or provider
from serving a request.
"""

from __future__ import annotations

import logging
from pathlib import Path
from threading import RLock

from cachetools import LRUCache

from app.models.translation import TranslationResult
from app.translation.sqlite_cache import HistoryEntry, SQLiteTranslationStore

DEFAULT_CACHE_MAX_SIZE = 128
CacheKey = tuple[str, str, str]
LOGGER_NAME = "desktop_translator"


class TranslationCache:
    """Store successful results using language-aware normalized text keys."""

    def __init__(
        self,
        max_size: int = DEFAULT_CACHE_MAX_SIZE,
        *,
        enabled: bool = True,
        sqlite_enabled: bool = False,
        sqlite_path: str | Path | None = None,
        history_enabled: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        try:
            normalized_size = int(max_size)
        except (TypeError, ValueError) as exc:
            raise ValueError("cache max_size must be a positive integer") from exc
        if normalized_size < 1:
            raise ValueError("cache max_size must be a positive integer")

        self.max_size = normalized_size
        self.enabled = bool(enabled)
        self.sqlite_enabled = bool(sqlite_enabled)
        self.sqlite_path = Path(sqlite_path) if sqlite_path is not None else None
        self.history_enabled = bool(history_enabled)
        self.logger = logger or logging.getLogger(LOGGER_NAME)
        self._entries: LRUCache[CacheKey, TranslationResult] = LRUCache(
            maxsize=normalized_size,
        )
        self._lock = RLock()
        self._sqlite_store: SQLiteTranslationStore | None = None
        self._open_sqlite_store()

    def _open_sqlite_store(self) -> None:
        if not self.sqlite_enabled or self.sqlite_path is None:
            return
        self._sqlite_store = SQLiteTranslationStore(
            self.sqlite_path,
            history_enabled=self.history_enabled,
            logger=self.logger,
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        """Create the Step10 cache-key form without changing provider input."""

        return str(text).replace("\r\n", "\n").replace("\r", "\n").strip()

    @classmethod
    def make_key(
        cls,
        source_language: str,
        target_language: str,
        source_text: str,
    ) -> CacheKey:
        """Build a key from the required language and normalized-text fields."""

        return (
            str(source_language),
            str(target_language),
            cls.normalize_text(source_text),
        )

    def get(
        self,
        source_language: str,
        target_language: str,
        source_text: str,
    ) -> TranslationResult | None:
        """Return a cached result and mark it recently used, if present."""

        if not self.enabled:
            return None

        key = self.make_key(source_language, target_language, source_text)
        with self._lock:
            try:
                result = self._entries[key]
            except KeyError:
                result = None

            if result is not None:
                store = self._sqlite_store
                if store is not None and store.available:
                    store.touch(source_language, target_language, source_text)
                return result

            store = self._sqlite_store
            if store is None or not store.available:
                return None
            result = store.get(source_language, target_language, source_text)
            if result is not None:
                self._entries[key] = result
            return result

    def set(
        self,
        source_language: str,
        target_language: str,
        source_text: str,
        result: TranslationResult,
    ) -> None:
        """Cache one successful result unless caching is disabled."""

        if not self.enabled:
            return

        key = self.make_key(source_language, target_language, source_text)
        with self._lock:
            store = self._sqlite_store
            if store is not None and store.available:
                # L2 is written before L1 so a successful provider result is
                # durable before a later manager can observe the hot entry.
                store.set(source_language, target_language, source_text, result)
            self._entries[key] = result

    def clear(self) -> None:
        """Remove all cached successful results."""

        with self._lock:
            self._entries.clear()
            store = self._sqlite_store
            if store is not None:
                store.clear()

    def configure_persistence(
        self,
        *,
        sqlite_enabled: bool | None = None,
        sqlite_path: str | Path | None = None,
        history_enabled: bool | None = None,
    ) -> None:
        """Reconfigure the optional L2 store without losing the L1 cache."""

        with self._lock:
            next_enabled = (
                self.sqlite_enabled
                if sqlite_enabled is None
                else bool(sqlite_enabled)
            )
            next_path = (
                self.sqlite_path
                if sqlite_path is None
                else Path(sqlite_path)
            )
            next_history = (
                self.history_enabled
                if history_enabled is None
                else bool(history_enabled)
            )
            path_changed = next_path != self.sqlite_path
            enabled_changed = next_enabled != self.sqlite_enabled

            if path_changed or enabled_changed:
                old_store = self._sqlite_store
                self._sqlite_store = None
                if old_store is not None:
                    old_store.close()
                self.sqlite_enabled = next_enabled
                self.sqlite_path = next_path
                self.history_enabled = next_history
                self._open_sqlite_store()
                return

            self.sqlite_enabled = next_enabled
            self.sqlite_path = next_path
            if next_history != self.history_enabled:
                self.history_enabled = next_history
                store = self._sqlite_store
                if store is not None:
                    store.set_history_enabled(next_history)

    @property
    def persistent_available(self) -> bool:
        """Whether the configured SQLite L2 is currently usable."""

        with self._lock:
            return bool(self._sqlite_store and self._sqlite_store.available)

    @property
    def persistent_size(self) -> int:
        """Return the number of persisted records, or zero when unavailable."""

        store = self._sqlite_store
        if store is None or not store.available:
            return 0
        # The persistence layer intentionally exposes history rows only when
        # the user opted in.  This property is therefore a safe health hint,
        # not a way to enumerate private source text.
        if not self.history_enabled:
            return 0
        return len(store.list_history(limit=1000))

    def list_history(self, limit: int = 100) -> list[HistoryEntry]:
        """Return persisted history only when explicitly enabled."""

        store = self._sqlite_store
        if store is None:
            return []
        return store.list_history(limit)

    def close(self) -> None:
        """Release the optional SQLite connection."""

        with self._lock:
            store = self._sqlite_store
            self._sqlite_store = None
            if store is not None:
                store.close()

    @property
    def size(self) -> int:
        """Return the current number of cached entries."""

        with self._lock:
            return len(self._entries)


__all__ = [
    "DEFAULT_CACHE_MAX_SIZE",
    "HistoryEntry",
    "TranslationCache",
]
