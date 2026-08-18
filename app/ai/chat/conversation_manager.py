"""Persistent ChatGPT-style conversation history backed by local SQLite."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.ai.chat.models import ChatContext, ChatMessage, ChatRole
from app.infrastructure.paths import writable_config_dir


DEFAULT_MAX_CONVERSATIONS = 30
DEFAULT_HISTORY_FILENAME = "chat_history.sqlite3"
SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_history_path() -> Path:
    return writable_config_dir() / DEFAULT_HISTORY_FILENAME


def _title_from_message(message: str, *, max_chars: int = 36) -> str:
    compact = " ".join(str(message).strip().split())
    if not compact:
        return "新对话"
    return compact if len(compact) <= max_chars else compact[: max_chars - 1].rstrip() + "…"


@dataclass
class Conversation:
    conversation_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: str = field(default_factory=lambda: uuid4().hex)
    title: str = "新对话"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    provider: str = ""
    model: str = ""
    base_url: str = ""
    context: ChatContext = field(default_factory=ChatContext)
    messages: list[ChatMessage] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def rotate_session(self) -> None:
        self.session_id = uuid4().hex
        self.touch()


class ConversationManager:
    """Maintain recent conversations and persist them in local SQLite.

    The public in-memory API intentionally stays unchanged so the Overlay UI,
    streaming controller, and history menu remain independent of the storage
    implementation. SQLite stores conversation metadata separately from
    ordered messages. No JSON history is read or migrated by this manager.
    API credentials are never stored in the database.
    """

    def __init__(
        self,
        max_sessions: int = DEFAULT_MAX_CONVERSATIONS,
        *,
        storage_path: str | Path | None = None,
    ) -> None:
        self.max_sessions = max(1, int(max_sessions))
        self.storage_path = (
            Path(storage_path) if storage_path is not None else _default_history_path()
        )
        self._sessions: list[Conversation] = []
        self._active_id: str | None = None
        self.load()

    @property
    def conversations(self) -> tuple[Conversation, ...]:
        return tuple(self._sessions)

    @property
    def active(self) -> Conversation | None:
        for item in self._sessions:
            if item.conversation_id == self._active_id:
                return item
        return None

    def ensure_active(
        self,
        *,
        context: ChatContext | None = None,
        provider: str = "",
        model: str = "",
        base_url: str = "",
    ) -> Conversation:
        active = self.active
        if active is not None:
            return active
        return self.new_conversation(
            context=context,
            provider=provider,
            model=model,
            base_url=base_url,
        )

    def new_conversation(
        self,
        *,
        context: ChatContext | None = None,
        provider: str = "",
        model: str = "",
        base_url: str = "",
    ) -> Conversation:
        session = Conversation(
            provider=str(provider).strip(),
            model=str(model).strip(),
            base_url=str(base_url).strip(),
            context=context or ChatContext(),
        )
        self._sessions.insert(0, session)
        self._active_id = session.conversation_id
        self._trim()
        self.save()
        return session

    def switch(self, conversation_id: str) -> Conversation | None:
        for item in self._sessions:
            if item.conversation_id == conversation_id:
                self._active_id = conversation_id
                item.touch()
                self._sort_recent()
                self.save()
                return item
        return None

    def remove(self, conversation_id: str) -> None:
        self._sessions = [
            item for item in self._sessions if item.conversation_id != conversation_id
        ]
        if self._active_id == conversation_id:
            self._active_id = self._sessions[0].conversation_id if self._sessions else None
        self.save()

    def clear_active(self) -> Conversation | None:
        active = self.active
        if active is None:
            return None
        active.messages.clear()
        active.rotate_session()
        active.title = "新对话"
        self._sort_recent()
        self.save()
        return active

    def set_context(self, context: ChatContext) -> Conversation:
        active = self.ensure_active(context=context)
        normalized = ChatContext(
            source_text=str(context.source_text or "").strip(),
            translated_text=str(context.translated_text or "").strip(),
        )
        if active.context != normalized and not active.messages:
            active.context = normalized
            active.rotate_session()
            self.save()
        return active

    def set_model(
        self,
        provider: str,
        model: str,
        base_url: str = "",
    ) -> Conversation:
        active = self.ensure_active()
        active.provider = str(provider).strip()
        active.model = str(model).strip()
        active.base_url = str(base_url).strip()
        active.touch()
        self._sort_recent()
        self.save()
        return active

    def append_exchange(self, user_message: str, assistant_message: str) -> Conversation:
        active = self.ensure_active()
        user = str(user_message).strip()
        assistant = str(assistant_message).strip()
        if not user or not assistant:
            return active
        if not active.messages or active.title == "新对话":
            active.title = _title_from_message(user)
        active.messages.extend(
            (
                ChatMessage(ChatRole.USER, user),
                ChatMessage(ChatRole.ASSISTANT, assistant),
            )
        )
        active.touch()
        self._sort_recent()
        self.save()
        return active

    def _sort_recent(self) -> None:
        self._sessions.sort(key=lambda item: item.updated_at, reverse=True)

    def _trim(self) -> None:
        self._sort_recent()
        if len(self._sessions) > self.max_sessions:
            self._sessions = self._sessions[: self.max_sessions]
        if self._active_id and not any(
            item.conversation_id == self._active_id for item in self._sessions
        ):
            self._active_id = self._sessions[0].conversation_id if self._sessions else None

    def _connect(self) -> sqlite3.Connection:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.storage_path, timeout=5.0)
        connection.execute("PRAGMA foreign_keys = ON")
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

            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                base_url TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL DEFAULT '',
                translated_text TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
                ON conversations(updated_at DESC);

            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY(conversation_id)
                    REFERENCES conversations(conversation_id)
                    ON DELETE CASCADE,
                UNIQUE(conversation_id, position)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation_position
                ON messages(conversation_id, position);
            """
        )
        connection.execute(
            "INSERT OR REPLACE INTO app_state(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )

    @staticmethod
    def _state_value(connection: sqlite3.Connection, key: str) -> str:
        row = connection.execute(
            "SELECT value FROM app_state WHERE key = ?",
            (key,),
        ).fetchone()
        return str(row[0]) if row else ""

    def _load_from_database(self, connection: sqlite3.Connection) -> None:
        self._sessions = []
        self._active_id = self._state_value(connection, "active_id") or None
        rows = connection.execute(
            """
            SELECT conversation_id, session_id, title, created_at, updated_at,
                   provider, model, base_url, source_text, translated_text
            FROM conversations
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (self.max_sessions,),
        ).fetchall()

        for row in rows:
            conversation_id = str(row[0])
            messages: list[ChatMessage] = []
            message_rows = connection.execute(
                """
                SELECT role, content
                FROM messages
                WHERE conversation_id = ?
                ORDER BY position ASC
                """,
                (conversation_id,),
            ).fetchall()
            for role_value, content_value in message_rows:
                try:
                    role = ChatRole(str(role_value))
                except ValueError:
                    continue
                content = str(content_value).strip()
                if content:
                    messages.append(ChatMessage(role, content))

            self._sessions.append(
                Conversation(
                    conversation_id=conversation_id,
                    session_id=str(row[1]) or uuid4().hex,
                    title=str(row[2]) or "新对话",
                    created_at=str(row[3]) or _now_iso(),
                    updated_at=str(row[4]) or _now_iso(),
                    provider=str(row[5] or ""),
                    model=str(row[6] or ""),
                    base_url=str(row[7] or ""),
                    context=ChatContext(
                        source_text=str(row[8] or ""),
                        translated_text=str(row[9] or ""),
                    ),
                    messages=messages,
                )
            )
        self._trim()

    def load(self) -> None:
        self._sessions = []
        self._active_id = None
        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                self._load_from_database(connection)
        except (OSError, sqlite3.Error):
            self._sessions = []
            self._active_id = None

    def _write_all(self, connection: sqlite3.Connection) -> None:
        self._trim()
        live_ids = [item.conversation_id for item in self._sessions]
        if live_ids:
            placeholders = ",".join("?" for _ in live_ids)
            connection.execute(
                f"DELETE FROM conversations WHERE conversation_id NOT IN ({placeholders})",
                live_ids,
            )
        else:
            connection.execute("DELETE FROM conversations")

        for item in self._sessions:
            connection.execute(
                """
                INSERT INTO conversations(
                    conversation_id, session_id, title, created_at, updated_at,
                    provider, model, base_url, source_text, translated_text
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    title = excluded.title,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    provider = excluded.provider,
                    model = excluded.model,
                    base_url = excluded.base_url,
                    source_text = excluded.source_text,
                    translated_text = excluded.translated_text
                """,
                (
                    item.conversation_id,
                    item.session_id,
                    item.title,
                    item.created_at,
                    item.updated_at,
                    item.provider,
                    item.model,
                    item.base_url,
                    item.context.source_text,
                    item.context.translated_text,
                ),
            )
            connection.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (item.conversation_id,),
            )
            if item.messages:
                connection.executemany(
                    """
                    INSERT INTO messages(conversation_id, position, role, content)
                    VALUES(?, ?, ?, ?)
                    """,
                    [
                        (
                            item.conversation_id,
                            position,
                            message.role.value,
                            message.content,
                        )
                        for position, message in enumerate(item.messages)
                    ],
                )

        connection.execute(
            "INSERT OR REPLACE INTO app_state(key, value) VALUES('active_id', ?)",
            (self._active_id or "",),
        )
        connection.execute(
            "INSERT OR REPLACE INTO app_state(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )

    def save(self) -> None:
        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                self._write_all(connection)
        except (OSError, sqlite3.Error):
            # History persistence must never take down the Overlay UI.
            return


__all__ = [
    "Conversation",
    "ConversationManager",
    "DEFAULT_HISTORY_FILENAME",
    "DEFAULT_MAX_CONVERSATIONS",
    "SCHEMA_VERSION",
]
