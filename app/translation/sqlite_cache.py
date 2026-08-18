"""Best-effort SQLite L2 storage for translation results.

The persistent layer is deliberately optional and never sits on the critical
path for application startup. A damaged, locked, or unwritable database is
disabled for the current process; the in-memory L1 cache continues to work.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path
import sqlite3
from threading import RLock
from time import time

from app.infrastructure.logging import sanitized_exception_info
from app.models.translation import TranslationResult

LOGGER_NAME = "desktop_translator"
DEFAULT_SQLITE_CACHE_FILENAME = "translation_cache.sqlite3"


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """A persisted translation record returned only when history is enabled."""

    normalized_text_hash: str
    source_language: str
    target_language: str
    source_text: str
    translated_text: str
    provider: str
    created_at: float
    last_used_at: float


def normalized_text_hash(text: str) -> str:
    """Return a stable non-reversible cache key for normalized text."""

    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class SQLiteTranslationStore:
    """Thread-safe, best-effort SQLite storage used by ``TranslationCache``."""

    def __init__(
        self,
        path: str | Path,
        *,
        history_enabled: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self.path = Path(path)
        self.history_enabled = bool(history_enabled)
        self.logger = logger or logging.getLogger(LOGGER_NAME)
        self._lock = RLock()
        self._connection: sqlite3.Connection | None = None
        self._available = False
        self._open()

    @property
    def available(self) -> bool:
        """Whether the persistent store is usable in this process."""

        with self._lock:
            return self._available and self._connection is not None

    def _open(self) -> None:
        connection: sqlite3.Connection | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                str(self.path),
                timeout=0.5,
                check_same_thread=False,
            )
            connection.execute("PRAGMA busy_timeout = 500")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS translations (
                    normalized_text_hash TEXT NOT NULL,
                    source_language TEXT NOT NULL,
                    target_language TEXT NOT NULL,
                    source_text TEXT,
                    translated_text TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT 'unknown',
                    created_at REAL NOT NULL,
                    last_used_at REAL NOT NULL,
                    PRIMARY KEY (
                        normalized_text_hash,
                        source_language,
                        target_language
                    )
                )
                """
            )
            self._migrate_columns(connection)
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_translations_last_used
                ON translations(last_used_at DESC)
                """
            )
            connection.commit()
        except Exception as exc:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
            self._record_failure("sqlite_cache_open_failed", exc)
            return

        with self._lock:
            self._connection = connection
            self._available = True

        if not self.history_enabled:
            self._remove_persisted_source_text()

    @staticmethod
    def _migrate_columns(connection: sqlite3.Connection) -> None:
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(translations)")
        }
        if "source_text" not in columns:
            connection.execute("ALTER TABLE translations ADD COLUMN source_text TEXT")
        if "provider" not in columns:
            connection.execute(
                "ALTER TABLE translations ADD COLUMN provider TEXT NOT NULL DEFAULT 'unknown'"
            )

    def get(
        self,
        source_language: str,
        target_language: str,
        source_text: str,
    ) -> TranslationResult | None:
        """Read one L2 result and update its last-use timestamp."""

        key_hash = normalized_text_hash(source_text)
        with self._lock:
            connection = self._connection if self._available else None
            if connection is None:
                return None
            try:
                row = connection.execute(
                    """
                    SELECT translated_text, provider
                    FROM translations
                    WHERE normalized_text_hash = ?
                      AND source_language = ?
                      AND target_language = ?
                    """,
                    (key_hash, str(source_language), str(target_language)),
                ).fetchone()
                if row is None:
                    return None
                connection.execute(
                    """
                    UPDATE translations
                    SET last_used_at = ?
                    WHERE normalized_text_hash = ?
                      AND source_language = ?
                      AND target_language = ?
                    """,
                    (
                        time(),
                        key_hash,
                        str(source_language),
                        str(target_language),
                    ),
                )
                connection.commit()
                return TranslationResult(
                    source_text=str(source_text),
                    translated_text=str(row[0]),
                    source_language=str(source_language),
                    target_language=str(target_language),
                    provider=str(row[1] or "persistent_cache"),
                    request_id=0,
                )
            except Exception as exc:
                self._record_failure("sqlite_cache_read_failed", exc)
                return None

    def set(
        self,
        source_language: str,
        target_language: str,
        source_text: str,
        result: TranslationResult,
    ) -> None:
        """Upsert a successful result without exposing the full text by default."""

        key_hash = normalized_text_hash(source_text)
        persisted_source = str(source_text) if self.history_enabled else None
        now = time()
        with self._lock:
            connection = self._connection if self._available else None
            if connection is None:
                return
            try:
                connection.execute(
                    """
                    INSERT INTO translations (
                        normalized_text_hash,
                        source_language,
                        target_language,
                        source_text,
                        translated_text,
                        provider,
                        created_at,
                        last_used_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(
                        normalized_text_hash,
                        source_language,
                        target_language
                    ) DO UPDATE SET
                        source_text = CASE
                            WHEN ? THEN excluded.source_text
                            ELSE translations.source_text
                        END,
                        translated_text = excluded.translated_text,
                        provider = excluded.provider,
                        last_used_at = excluded.last_used_at
                    """,
                    (
                        key_hash,
                        str(source_language),
                        str(target_language),
                        persisted_source,
                        str(result.translated_text),
                        str(result.provider),
                        now,
                        now,
                        self.history_enabled,
                    ),
                )
                connection.commit()
            except Exception as exc:
                self._record_failure("sqlite_cache_write_failed", exc)

    def touch(
        self,
        source_language: str,
        target_language: str,
        source_text: str,
    ) -> None:
        """Refresh last-use metadata for an L1 hit when the row exists."""

        key_hash = normalized_text_hash(source_text)
        with self._lock:
            connection = self._connection if self._available else None
            if connection is None:
                return
            try:
                connection.execute(
                    """
                    UPDATE translations
                    SET last_used_at = ?
                    WHERE normalized_text_hash = ?
                      AND source_language = ?
                      AND target_language = ?
                    """,
                    (
                        time(),
                        key_hash,
                        str(source_language),
                        str(target_language),
                    ),
                )
                connection.commit()
            except Exception as exc:
                self._record_failure("sqlite_cache_touch_failed", exc)

    def clear(self) -> None:
        """Clear persistent cache entries without raising to the app."""

        with self._lock:
            connection = self._connection if self._available else None
            if connection is None:
                return
            try:
                connection.execute("DELETE FROM translations")
                connection.commit()
            except Exception as exc:
                self._record_failure("sqlite_cache_clear_failed", exc)

    def set_history_enabled(self, enabled: bool) -> None:
        """Toggle raw-text persistence and erase stored raw text when disabled."""

        next_enabled = bool(enabled)
        with self._lock:
            self.history_enabled = next_enabled
            if next_enabled:
                return
            self._remove_persisted_source_text()

    def _remove_persisted_source_text(self) -> None:
        connection = self._connection if self._available else None
        if connection is None:
            return
        try:
            connection.execute("UPDATE translations SET source_text = NULL")
            connection.commit()
        except Exception as exc:
            self._record_failure("sqlite_cache_history_cleanup_failed", exc)

    def list_history(self, limit: int = 100) -> list[HistoryEntry]:
        """Return recent records only when explicit history mode is enabled."""

        if not self.history_enabled:
            return []
        safe_limit = min(1000, max(1, int(limit)))
        with self._lock:
            connection = self._connection if self._available else None
            if connection is None:
                return []
            try:
                rows = connection.execute(
                    """
                    SELECT normalized_text_hash, source_language,
                           target_language, source_text, translated_text,
                           provider, created_at, last_used_at
                    FROM translations
                    WHERE source_text IS NOT NULL
                    ORDER BY last_used_at DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()
            except Exception as exc:
                self._record_failure("sqlite_history_read_failed", exc)
                return []

        return [
            HistoryEntry(
                normalized_text_hash=str(row[0]),
                source_language=str(row[1]),
                target_language=str(row[2]),
                source_text=str(row[3]),
                translated_text=str(row[4]),
                provider=str(row[5]),
                created_at=float(row[6]),
                last_used_at=float(row[7]),
            )
            for row in rows
        ]

    def close(self) -> None:
        """Close the database connection safely."""

        with self._lock:
            connection = self._connection
            self._connection = None
            self._available = False
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    def _record_failure(self, event: str, exc: Exception) -> None:
        with self._lock:
            self._available = False
            connection = self._connection
            self._connection = None
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
        self.logger.error(
            "%s error_type=%s path=%s",
            event,
            type(exc).__name__,
            self.path,
            exc_info=sanitized_exception_info(exc),
        )


__all__ = [
    "DEFAULT_SQLITE_CACHE_FILENAME",
    "HistoryEntry",
    "SQLiteTranslationStore",
    "normalized_text_hash",
]
