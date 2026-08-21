from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4

from app.infrastructure.paths import writable_config_dir

DEFAULT_CONVERSATION_FILENAME = "web_chat.sqlite3"
DEFAULT_MAX_CONVERSATIONS = 50
SCHEMA_VERSION = 1
TERMINAL_MESSAGE_STATUSES = frozenset({"complete", "cancelled", "error"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compact_title(text: str, *, max_chars: int = 42) -> str:
    compact = " ".join(str(text or "").strip().split())
    if not compact:
        return "New conversation"
    return compact if len(compact) <= max_chars else compact[: max_chars - 1].rstrip() + "…"


@dataclass(frozen=True, slots=True)
class StoredMessage:
    message_id: str
    conversation_id: str
    request_id: int
    role: str
    content: str
    status: str
    provider: str
    model: str
    error_code: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class StoredConversation:
    conversation_id: str
    session_id: str
    title: str
    created_at: str
    updated_at: str
    provider: str
    model: str
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    resource_url: str
    resource_title: str
    section_heading: str
    context_before: str
    context_after: str
    source_kind: str
    messages: tuple[StoredMessage, ...] = ()


@dataclass(frozen=True, slots=True)
class ExchangeStart:
    conversation_id: str
    user_message_id: str
    assistant_message_id: str


class ConversationStoreService:
    """WebReBuild-owned durable conversation and message lifecycle store.

    This store intentionally uses a separate SQLite file from the legacy Qt
    ConversationManager. Streaming assistant messages are created as
    ``streaming`` and committed to one of the terminal statuses so a WebView or
    process restart can distinguish completed, cancelled, errored and
    interrupted generations.
    """

    def __init__(
        self,
        *,
        storage_path: str | Path | None = None,
        max_conversations: int = DEFAULT_MAX_CONVERSATIONS,
    ) -> None:
        self.storage_path = (
            Path(storage_path)
            if storage_path is not None
            else writable_config_dir() / DEFAULT_CONVERSATION_FILENAME
        )
        self.max_conversations = max(1, int(max_conversations))
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.storage_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL DEFAULT '',
                translated_text TEXT NOT NULL DEFAULT '',
                source_language TEXT NOT NULL DEFAULT 'auto',
                target_language TEXT NOT NULL DEFAULT 'zh-CN',
                resource_url TEXT NOT NULL DEFAULT '',
                resource_title TEXT NOT NULL DEFAULT '',
                section_heading TEXT NOT NULL DEFAULT '',
                context_before TEXT NOT NULL DEFAULT '',
                context_after TEXT NOT NULL DEFAULT '',
                source_kind TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_web_conversations_updated_at
                ON conversations(updated_at DESC);

            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                request_id INTEGER NOT NULL DEFAULT 0,
                role TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                error_code TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id)
                    REFERENCES conversations(conversation_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_web_messages_conversation_created
                ON messages(conversation_id, created_at ASC);
            CREATE INDEX IF NOT EXISTS idx_web_messages_request
                ON messages(conversation_id, request_id);
            """
        )
        connection.execute(
            "INSERT OR REPLACE INTO app_state(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )

    def _initialize(self) -> None:
        with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    now = _now_iso()
                    connection.execute(
                        """
                        UPDATE messages
                        SET status = 'cancelled', error_code = 'interrupted', updated_at = ?
                        WHERE status = 'streaming'
                        """,
                        (now,),
                    )

    @staticmethod
    def _message_from_row(row: sqlite3.Row) -> StoredMessage:
        return StoredMessage(
            message_id=str(row["message_id"]),
            conversation_id=str(row["conversation_id"]),
            request_id=int(row["request_id"]),
            role=str(row["role"]),
            content=str(row["content"]),
            status=str(row["status"]),
            provider=str(row["provider"]),
            model=str(row["model"]),
            error_code=str(row["error_code"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def _conversation_from_row(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        include_messages: bool,
    ) -> StoredConversation:
        messages: tuple[StoredMessage, ...] = ()
        if include_messages:
            message_rows = connection.execute(
                """
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (str(row["conversation_id"]),),
            ).fetchall()
            messages = tuple(self._message_from_row(item) for item in message_rows)
        return StoredConversation(
            conversation_id=str(row["conversation_id"]),
            session_id=str(row["session_id"]),
            title=str(row["title"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            provider=str(row["provider"]),
            model=str(row["model"]),
            source_text=str(row["source_text"]),
            translated_text=str(row["translated_text"]),
            source_language=str(row["source_language"]),
            target_language=str(row["target_language"]),
            resource_url=str(row["resource_url"]),
            resource_title=str(row["resource_title"]),
            section_heading=str(row["section_heading"]),
            context_before=str(row["context_before"]),
            context_after=str(row["context_after"]),
            source_kind=str(row["source_kind"]),
            messages=messages,
        )

    def list_recent(self, *, limit: int = 30) -> tuple[StoredConversation, ...]:
        bounded = max(1, min(int(limit), self.max_conversations))
        with self._lock:
            with closing(self._connect()) as connection:
                self._ensure_schema(connection)
                rows = connection.execute(
                    "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
                    (bounded,),
                ).fetchall()
                return tuple(
                    self._conversation_from_row(connection, row, include_messages=False)
                    for row in rows
                )

    def get(self, conversation_id: str) -> StoredConversation | None:
        candidate = str(conversation_id or "").strip()
        if not candidate:
            return None
        with self._lock:
            with closing(self._connect()) as connection:
                self._ensure_schema(connection)
                row = connection.execute(
                    "SELECT * FROM conversations WHERE conversation_id = ?",
                    (candidate,),
                ).fetchone()
                if row is None:
                    return None
                return self._conversation_from_row(
                    connection,
                    row,
                    include_messages=True,
                )

    def begin_exchange(
        self,
        *,
        conversation_id: str = "",
        session_id: str,
        user_message: str,
        request_id: int,
        source_text: str,
        translated_text: str = "",
        source_language: str = "auto",
        target_language: str = "zh-CN",
        resource_url: str = "",
        resource_title: str = "",
        section_heading: str = "",
        context_before: str = "",
        context_after: str = "",
        source_kind: str = "browser_selection",
    ) -> ExchangeStart:
        user_text = str(user_message or "").strip()
        if not user_text:
            raise ValueError("Conversation user message must not be empty.")
        candidate_id = str(conversation_id or "").strip()
        now = _now_iso()
        with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    row = None
                    if candidate_id:
                        row = connection.execute(
                            "SELECT conversation_id FROM conversations WHERE conversation_id = ?",
                            (candidate_id,),
                        ).fetchone()
                    if row is None:
                        candidate_id = uuid4().hex
                        connection.execute(
                            """
                            INSERT INTO conversations(
                                conversation_id, session_id, title, created_at, updated_at,
                                source_text, translated_text, source_language, target_language,
                                resource_url, resource_title, section_heading,
                                context_before, context_after, source_kind
                            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                candidate_id,
                                str(session_id).strip() or uuid4().hex,
                                _compact_title(user_text),
                                now,
                                now,
                                str(source_text or "").strip(),
                                str(translated_text or "").strip(),
                                str(source_language or "auto").strip() or "auto",
                                str(target_language or "zh-CN").strip() or "zh-CN",
                                str(resource_url or "").strip(),
                                str(resource_title or "").strip(),
                                str(section_heading or "").strip(),
                                str(context_before or "").strip(),
                                str(context_after or "").strip(),
                                str(source_kind or "").strip(),
                            ),
                        )
                    else:
                        connection.execute(
                            "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                            (now, candidate_id),
                        )

                    user_message_id = uuid4().hex
                    assistant_message_id = uuid4().hex
                    connection.execute(
                        """
                        INSERT INTO messages(
                            message_id, conversation_id, request_id, role, content,
                            status, created_at, updated_at
                        ) VALUES(?, ?, ?, 'user', ?, 'complete', ?, ?)
                        """,
                        (
                            user_message_id,
                            candidate_id,
                            int(request_id),
                            user_text,
                            now,
                            now,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO messages(
                            message_id, conversation_id, request_id, role, content,
                            status, created_at, updated_at
                        ) VALUES(?, ?, ?, 'assistant', '', 'streaming', ?, ?)
                        """,
                        (
                            assistant_message_id,
                            candidate_id,
                            int(request_id),
                            now,
                            now,
                        ),
                    )
                    self._trim_locked(connection)
                    return ExchangeStart(
                        conversation_id=candidate_id,
                        user_message_id=user_message_id,
                        assistant_message_id=assistant_message_id,
                    )

    def update_stream(self, message_id: str, content: str) -> None:
        now = _now_iso()
        with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    row = connection.execute(
                        "SELECT conversation_id, status FROM messages WHERE message_id = ?",
                        (message_id,),
                    ).fetchone()
                    if row is None or str(row["status"]) != "streaming":
                        return
                    connection.execute(
                        "UPDATE messages SET content = ?, updated_at = ? WHERE message_id = ?",
                        (str(content or ""), now, message_id),
                    )
                    connection.execute(
                        "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                        (now, str(row["conversation_id"])),
                    )

    def finalize_message(
        self,
        message_id: str,
        *,
        status: str,
        content: str | None = None,
        provider: str = "",
        model: str = "",
        error_code: str = "",
    ) -> StoredMessage | None:
        normalized_status = str(status).strip().lower()
        if normalized_status not in TERMINAL_MESSAGE_STATUSES:
            raise ValueError(f"Unsupported terminal message status: {status!r}")
        now = _now_iso()
        with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    row = connection.execute(
                        "SELECT * FROM messages WHERE message_id = ?",
                        (message_id,),
                    ).fetchone()
                    if row is None:
                        return None
                    final_content = str(row["content"]) if content is None else str(content)
                    connection.execute(
                        """
                        UPDATE messages
                        SET content = ?, status = ?, provider = ?, model = ?,
                            error_code = ?, updated_at = ?
                        WHERE message_id = ?
                        """,
                        (
                            final_content,
                            normalized_status,
                            str(provider or "").strip(),
                            str(model or "").strip(),
                            str(error_code or "").strip(),
                            now,
                            message_id,
                        ),
                    )
                    conversation_id = str(row["conversation_id"])
                    connection.execute(
                        """
                        UPDATE conversations
                        SET updated_at = ?,
                            provider = CASE WHEN ? <> '' THEN ? ELSE provider END,
                            model = CASE WHEN ? <> '' THEN ? ELSE model END
                        WHERE conversation_id = ?
                        """,
                        (
                            now,
                            str(provider or "").strip(),
                            str(provider or "").strip(),
                            str(model or "").strip(),
                            str(model or "").strip(),
                            conversation_id,
                        ),
                    )
                    updated = connection.execute(
                        "SELECT * FROM messages WHERE message_id = ?",
                        (message_id,),
                    ).fetchone()
                    return self._message_from_row(updated) if updated is not None else None

    def rename(self, conversation_id: str, title: str) -> StoredConversation | None:
        normalized = " ".join(str(title or "").strip().split())[:120]
        if not normalized:
            raise ValueError("Conversation title must not be empty.")
        now = _now_iso()
        with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    cursor = connection.execute(
                        "UPDATE conversations SET title = ?, updated_at = ? WHERE conversation_id = ?",
                        (normalized, now, conversation_id),
                    )
                    if cursor.rowcount < 1:
                        return None
        return self.get(conversation_id)

    def delete(self, conversation_id: str) -> bool:
        with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    cursor = connection.execute(
                        "DELETE FROM conversations WHERE conversation_id = ?",
                        (str(conversation_id or "").strip(),),
                    )
                    return cursor.rowcount > 0

    def _trim_locked(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT conversation_id FROM conversations
            ORDER BY updated_at DESC
            LIMIT -1 OFFSET ?
            """,
            (self.max_conversations,),
        ).fetchall()
        if rows:
            connection.executemany(
                "DELETE FROM conversations WHERE conversation_id = ?",
                [(str(row[0]),) for row in rows],
            )


__all__ = [
    "ConversationStoreService",
    "DEFAULT_CONVERSATION_FILENAME",
    "DEFAULT_MAX_CONVERSATIONS",
    "ExchangeStart",
    "SCHEMA_VERSION",
    "StoredConversation",
    "StoredMessage",
    "TERMINAL_MESSAGE_STATUSES",
]
