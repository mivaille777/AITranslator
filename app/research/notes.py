"""SQLite-backed research notes derived from bounded reading context."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.ai.chat.models import ChatContext
from app.infrastructure.paths import writable_config_dir


DEFAULT_RESEARCH_NOTES_FILENAME = "research_notes.sqlite3"
RESEARCH_NOTES_SCHEMA_VERSION = 1
DEFAULT_RECENT_NOTE_LIMIT = 10
MAX_RECENT_NOTE_LIMIT = 100


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_storage_path() -> Path:
    return writable_config_dir() / DEFAULT_RESEARCH_NOTES_FILENAME


def _clean(value: object, *, limit: int = 0) -> str:
    text = str(value or "").replace("\x00", "").strip()
    if limit > 0 and len(text) > limit:
        return text[:limit]
    return text


def _fingerprint(
    *,
    resource_url: str,
    resource_title: str,
    section_heading: str,
    source_kind: str,
    source_text: str,
) -> str:
    payload = "\x1f".join(
        (
            resource_url.casefold(),
            resource_title.casefold(),
            section_heading.casefold(),
            source_kind.casefold(),
            " ".join(source_text.split()),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ResearchNote:
    note_id: str
    fingerprint: str
    created_at: str
    updated_at: str
    resource_url: str = ""
    resource_title: str = ""
    section_heading: str = ""
    source_kind: str = ""
    source_text: str = ""
    translated_text: str = ""
    context_before: str = ""
    context_after: str = ""
    ai_content: str = ""
    ai_action: str = ""
    user_note: str = ""
    conversation_id: str = ""

    @property
    def display_title(self) -> str:
        return self.resource_title or self.section_heading or "未命名阅读笔记"

    @property
    def excerpt(self) -> str:
        compact = " ".join(self.source_text.split())
        return compact if len(compact) <= 140 else compact[:139].rstrip() + "…"


@dataclass(frozen=True, slots=True)
class ResearchNoteSaveResult:
    note: ResearchNote
    created: bool


class ResearchNoteStore:
    """Persist research notes independently from conversational chat history."""

    def __init__(self, *, storage_path: str | Path | None = None) -> None:
        self.storage_path = (
            Path(storage_path) if storage_path is not None else _default_storage_path()
        )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.storage_path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS research_notes (
                note_id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resource_url TEXT NOT NULL DEFAULT '',
                resource_title TEXT NOT NULL DEFAULT '',
                section_heading TEXT NOT NULL DEFAULT '',
                source_kind TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL,
                translated_text TEXT NOT NULL DEFAULT '',
                context_before TEXT NOT NULL DEFAULT '',
                context_after TEXT NOT NULL DEFAULT '',
                ai_content TEXT NOT NULL DEFAULT '',
                ai_action TEXT NOT NULL DEFAULT '',
                user_note TEXT NOT NULL DEFAULT '',
                conversation_id TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_research_notes_updated_at
                ON research_notes(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_research_notes_resource_url
                ON research_notes(resource_url);
            """
        )
        connection.execute(
            "INSERT OR REPLACE INTO app_state(key, value) VALUES('schema_version', ?)",
            (str(RESEARCH_NOTES_SCHEMA_VERSION),),
        )

    def _initialize(self) -> None:
        try:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
        except (OSError, sqlite3.Error):
            # Research-memory persistence must never prevent app startup.
            return

    @staticmethod
    def _row_to_note(row: tuple[object, ...]) -> ResearchNote:
        return ResearchNote(
            note_id=str(row[0]),
            fingerprint=str(row[1]),
            created_at=str(row[2]),
            updated_at=str(row[3]),
            resource_url=str(row[4] or ""),
            resource_title=str(row[5] or ""),
            section_heading=str(row[6] or ""),
            source_kind=str(row[7] or ""),
            source_text=str(row[8] or ""),
            translated_text=str(row[9] or ""),
            context_before=str(row[10] or ""),
            context_after=str(row[11] or ""),
            ai_content=str(row[12] or ""),
            ai_action=str(row[13] or ""),
            user_note=str(row[14] or ""),
            conversation_id=str(row[15] or ""),
        )

    @staticmethod
    def _select_columns() -> str:
        return (
            "note_id, fingerprint, created_at, updated_at, resource_url, "
            "resource_title, section_heading, source_kind, source_text, "
            "translated_text, context_before, context_after, ai_content, "
            "ai_action, user_note, conversation_id"
        )

    def save_context(
        self,
        context: ChatContext,
        *,
        ai_content: object = "",
        ai_action: object = "",
        user_note: object = "",
        conversation_id: object = "",
    ) -> ResearchNoteSaveResult:
        """Create or enrich one note for the exact selected reading passage."""

        source_text = _clean(context.source_text, limit=20_000)
        if not source_text:
            raise ValueError("Research note requires selected source text.")

        reading = context.reading
        values = {
            "resource_url": _clean(reading.resource_url, limit=4096),
            "resource_title": _clean(reading.resource_title, limit=1024),
            "section_heading": _clean(reading.section_heading, limit=1024),
            "source_kind": _clean(reading.source_kind, limit=128),
            "source_text": source_text,
            "translated_text": _clean(context.translated_text, limit=20_000),
            "context_before": _clean(reading.context_before, limit=4000),
            "context_after": _clean(reading.context_after, limit=4000),
            "ai_content": _clean(ai_content, limit=30_000),
            "ai_action": _clean(ai_action, limit=128),
            "user_note": _clean(user_note, limit=20_000),
            "conversation_id": _clean(conversation_id, limit=128),
        }
        fingerprint = _fingerprint(
            resource_url=values["resource_url"],
            resource_title=values["resource_title"],
            section_heading=values["section_heading"],
            source_kind=values["source_kind"],
            source_text=source_text,
        )
        now = _now_iso()

        try:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    row = connection.execute(
                        f"SELECT {self._select_columns()} FROM research_notes WHERE fingerprint = ?",
                        (fingerprint,),
                    ).fetchone()
                    if row is None:
                        note_id = uuid4().hex
                        connection.execute(
                            """
                            INSERT INTO research_notes(
                                note_id, fingerprint, created_at, updated_at,
                                resource_url, resource_title, section_heading,
                                source_kind, source_text, translated_text,
                                context_before, context_after, ai_content,
                                ai_action, user_note, conversation_id
                            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                note_id,
                                fingerprint,
                                now,
                                now,
                                values["resource_url"],
                                values["resource_title"],
                                values["section_heading"],
                                values["source_kind"],
                                values["source_text"],
                                values["translated_text"],
                                values["context_before"],
                                values["context_after"],
                                values["ai_content"],
                                values["ai_action"],
                                values["user_note"],
                                values["conversation_id"],
                            ),
                        )
                        created = True
                    else:
                        existing = self._row_to_note(row)
                        note_id = existing.note_id
                        merged = {
                            "resource_url": values["resource_url"] or existing.resource_url,
                            "resource_title": values["resource_title"] or existing.resource_title,
                            "section_heading": values["section_heading"] or existing.section_heading,
                            "source_kind": values["source_kind"] or existing.source_kind,
                            "translated_text": values["translated_text"] or existing.translated_text,
                            "context_before": values["context_before"] or existing.context_before,
                            "context_after": values["context_after"] or existing.context_after,
                            "ai_content": values["ai_content"] or existing.ai_content,
                            "ai_action": values["ai_action"] or existing.ai_action,
                            "user_note": values["user_note"] or existing.user_note,
                            "conversation_id": values["conversation_id"] or existing.conversation_id,
                        }
                        connection.execute(
                            """
                            UPDATE research_notes
                            SET updated_at = ?, resource_url = ?, resource_title = ?,
                                section_heading = ?, source_kind = ?, source_text = ?,
                                translated_text = ?, context_before = ?, context_after = ?,
                                ai_content = ?, ai_action = ?, user_note = ?, conversation_id = ?
                            WHERE note_id = ?
                            """,
                            (
                                now,
                                merged["resource_url"],
                                merged["resource_title"],
                                merged["section_heading"],
                                merged["source_kind"],
                                source_text,
                                merged["translated_text"],
                                merged["context_before"],
                                merged["context_after"],
                                merged["ai_content"],
                                merged["ai_action"],
                                merged["user_note"],
                                merged["conversation_id"],
                                note_id,
                            ),
                        )
                        created = False

                    saved_row = connection.execute(
                        f"SELECT {self._select_columns()} FROM research_notes WHERE note_id = ?",
                        (note_id,),
                    ).fetchone()
        except (OSError, sqlite3.Error) as exc:
            raise RuntimeError("Unable to persist research note.") from exc

        if saved_row is None:
            raise RuntimeError("Research note was not persisted.")
        return ResearchNoteSaveResult(self._row_to_note(saved_row), created)

    def list_recent(self, *, limit: int = DEFAULT_RECENT_NOTE_LIMIT) -> tuple[ResearchNote, ...]:
        try:
            bounded_limit = max(1, min(MAX_RECENT_NOTE_LIMIT, int(limit)))
        except (TypeError, ValueError):
            bounded_limit = DEFAULT_RECENT_NOTE_LIMIT
        try:
            with closing(self._connect()) as connection:
                self._ensure_schema(connection)
                rows = connection.execute(
                    f"SELECT {self._select_columns()} FROM research_notes "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (bounded_limit,),
                ).fetchall()
        except (OSError, sqlite3.Error):
            return ()
        return tuple(self._row_to_note(row) for row in rows)

    def get(self, note_id: object) -> ResearchNote | None:
        identifier = _clean(note_id, limit=128)
        if not identifier:
            return None
        try:
            with closing(self._connect()) as connection:
                self._ensure_schema(connection)
                row = connection.execute(
                    f"SELECT {self._select_columns()} FROM research_notes WHERE note_id = ?",
                    (identifier,),
                ).fetchone()
        except (OSError, sqlite3.Error):
            return None
        return self._row_to_note(row) if row is not None else None

    def update_user_note(self, note_id: object, user_note: object) -> ResearchNote | None:
        identifier = _clean(note_id, limit=128)
        if not identifier:
            return None
        annotation = _clean(user_note, limit=20_000)
        now = _now_iso()
        try:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    cursor = connection.execute(
                        "UPDATE research_notes SET user_note = ?, updated_at = ? WHERE note_id = ?",
                        (annotation, now, identifier),
                    )
                    if cursor.rowcount < 1:
                        return None
                    row = connection.execute(
                        f"SELECT {self._select_columns()} FROM research_notes WHERE note_id = ?",
                        (identifier,),
                    ).fetchone()
        except (OSError, sqlite3.Error) as exc:
            raise RuntimeError("Unable to update research note.") from exc
        return self._row_to_note(row) if row is not None else None

    def count(self) -> int:
        try:
            with closing(self._connect()) as connection:
                self._ensure_schema(connection)
                row = connection.execute("SELECT COUNT(*) FROM research_notes").fetchone()
        except (OSError, sqlite3.Error):
            return 0
        return int(row[0]) if row else 0

    def delete(self, note_id: object) -> bool:
        identifier = _clean(note_id, limit=128)
        if not identifier:
            return False
        try:
            with closing(self._connect()) as connection:
                with connection:
                    cursor = connection.execute(
                        "DELETE FROM research_notes WHERE note_id = ?",
                        (identifier,),
                    )
                    return bool(cursor.rowcount)
        except (OSError, sqlite3.Error):
            return False


__all__ = [
    "DEFAULT_RECENT_NOTE_LIMIT",
    "DEFAULT_RESEARCH_NOTES_FILENAME",
    "MAX_RECENT_NOTE_LIMIT",
    "RESEARCH_NOTES_SCHEMA_VERSION",
    "ResearchNote",
    "ResearchNoteSaveResult",
    "ResearchNoteStore",
]
