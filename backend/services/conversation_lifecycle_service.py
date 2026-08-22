from __future__ import annotations

from contextlib import closing
from typing import Any

from backend.services.conversation_store_service import (
    ConversationStoreService,
    ExchangeStart,
    StoredConversation,
    _now_iso,
)

_CONTEXT_MODES = frozenset({"general", "reading"})


def _branch_title(value: object, *, max_chars: int = 42) -> str:
    compact = " ".join(str(value or "").strip().split())
    if not compact:
        return "New conversation"
    return compact if len(compact) <= max_chars else compact[: max_chars - 1].rstrip() + "…"


class ConversationLifecycleService(ConversationStoreService):
    """Durable chat store with branch rewriting and explicit context modes.

    ``ConversationStoreService`` remains the persistence/lifecycle foundation.
    This layer adds ChatGPT-style branch rewriting plus a small per-conversation
    mode table. Reading context is preserved when a conversation is detached so
    the user can later re-attach it without losing the frozen evidence.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ensure_context_mode_schema()

    def _ensure_context_mode_schema(self) -> None:
        with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS conversation_context_modes (
                            conversation_id TEXT PRIMARY KEY,
                            context_mode TEXT NOT NULL DEFAULT 'reading',
                            FOREIGN KEY(conversation_id)
                                REFERENCES conversations(conversation_id)
                                ON DELETE CASCADE
                        );
                        """
                    )
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO conversation_context_modes(
                            conversation_id, context_mode
                        )
                        SELECT conversation_id,
                               CASE
                                   WHEN TRIM(source_text) <> '' THEN 'reading'
                                   ELSE 'general'
                               END
                        FROM conversations
                        """
                    )

    def context_mode(self, conversation_id: str) -> str:
        candidate = str(conversation_id or "").strip()
        if not candidate:
            return "general"
        with self._lock:
            with closing(self._connect()) as connection:
                self._ensure_schema(connection)
                row = connection.execute(
                    """
                    SELECT context_mode
                    FROM conversation_context_modes
                    WHERE conversation_id = ?
                    """,
                    (candidate,),
                ).fetchone()
                if row is not None and str(row["context_mode"]) in _CONTEXT_MODES:
                    return str(row["context_mode"])
                conversation = connection.execute(
                    "SELECT source_text FROM conversations WHERE conversation_id = ?",
                    (candidate,),
                ).fetchone()
                if conversation is None:
                    return "general"
                return "reading" if str(conversation["source_text"] or "").strip() else "general"

    def _set_context_mode(self, conversation_id: str, context_mode: str) -> None:
        normalized = str(context_mode or "").strip().lower()
        if normalized not in _CONTEXT_MODES:
            raise ValueError(f"Unsupported conversation context mode: {context_mode!r}")
        with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS conversation_context_modes (
                            conversation_id TEXT PRIMARY KEY,
                            context_mode TEXT NOT NULL DEFAULT 'reading',
                            FOREIGN KEY(conversation_id)
                                REFERENCES conversations(conversation_id)
                                ON DELETE CASCADE
                        )
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO conversation_context_modes(conversation_id, context_mode)
                        VALUES(?, ?)
                        ON CONFLICT(conversation_id) DO UPDATE SET
                            context_mode = excluded.context_mode
                        """,
                        (conversation_id, normalized),
                    )

    def begin_exchange_with_context_mode(
        self,
        *,
        context_mode: str,
        **kwargs: Any,
    ) -> ExchangeStart:
        exchange = self.begin_exchange(**kwargs)
        self._set_context_mode(exchange.conversation_id, context_mode)
        return exchange

    def begin_exchange(self, **kwargs: Any) -> ExchangeStart:
        conversation_id = str(kwargs.get("conversation_id") or "").strip()
        user_message = str(kwargs.get("user_message") or "").strip()
        existing_was_empty = False

        if conversation_id:
            with self._lock:
                with closing(self._connect()) as connection:
                    self._ensure_schema(connection)
                    row = connection.execute(
                        """
                        SELECT COUNT(*) AS message_count
                        FROM messages
                        WHERE conversation_id = ?
                        """,
                        (conversation_id,),
                    ).fetchone()
                    existing_was_empty = row is not None and int(row["message_count"]) == 0

        exchange = super().begin_exchange(**kwargs)

        if existing_was_empty and user_message:
            with self._lock:
                with closing(self._connect()) as connection:
                    with connection:
                        self._ensure_schema(connection)
                        connection.execute(
                            "UPDATE conversations SET title = ? WHERE conversation_id = ?",
                            (_branch_title(user_message), exchange.conversation_id),
                        )

        return exchange

    def update_context(
        self,
        conversation_id: str,
        *,
        context_mode: str,
        source_text: str | None = None,
        translated_text: str | None = None,
        source_language: str | None = None,
        target_language: str | None = None,
        resource_url: str | None = None,
        resource_title: str | None = None,
        section_heading: str | None = None,
        context_before: str | None = None,
        context_after: str | None = None,
        source_kind: str | None = None,
    ) -> StoredConversation | None:
        candidate = str(conversation_id or "").strip()
        mode = str(context_mode or "").strip().lower()
        if mode not in _CONTEXT_MODES:
            raise ValueError(f"Unsupported conversation context mode: {context_mode!r}")
        if not candidate:
            return None

        values = {
            "source_text": source_text,
            "translated_text": translated_text,
            "source_language": source_language,
            "target_language": target_language,
            "resource_url": resource_url,
            "resource_title": resource_title,
            "section_heading": section_heading,
            "context_before": context_before,
            "context_after": context_after,
            "source_kind": source_kind,
        }

        with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    existing = connection.execute(
                        "SELECT source_text FROM conversations WHERE conversation_id = ?",
                        (candidate,),
                    ).fetchone()
                    if existing is None:
                        return None

                    effective_source = (
                        str(source_text or "").strip()
                        if source_text is not None
                        else str(existing["source_text"] or "").strip()
                    )
                    if mode == "reading" and not effective_source:
                        raise ValueError(
                            "Reading-grounded chat requires selected source text."
                        )

                    assignments: list[str] = ["updated_at = ?"]
                    parameters: list[object] = [_now_iso()]
                    for column, value in values.items():
                        if value is None:
                            continue
                        assignments.append(f"{column} = ?")
                        parameters.append(str(value).strip())
                    parameters.append(candidate)
                    connection.execute(
                        f"UPDATE conversations SET {', '.join(assignments)} WHERE conversation_id = ?",
                        parameters,
                    )
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS conversation_context_modes (
                            conversation_id TEXT PRIMARY KEY,
                            context_mode TEXT NOT NULL DEFAULT 'reading',
                            FOREIGN KEY(conversation_id)
                                REFERENCES conversations(conversation_id)
                                ON DELETE CASCADE
                        )
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO conversation_context_modes(conversation_id, context_mode)
                        VALUES(?, ?)
                        ON CONFLICT(conversation_id) DO UPDATE SET
                            context_mode = excluded.context_mode
                        """,
                        (candidate, mode),
                    )

        return self.get(candidate)

    def rewind_from_user_message(
        self,
        conversation_id: str,
        user_message_id: str,
    ) -> StoredConversation | None:
        """Delete one user message and every later branch message."""

        candidate_conversation = str(conversation_id or "").strip()
        candidate_message = str(user_message_id or "").strip()
        if not candidate_conversation or not candidate_message:
            return None

        with self._lock:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    conversation = connection.execute(
                        "SELECT conversation_id FROM conversations WHERE conversation_id = ?",
                        (candidate_conversation,),
                    ).fetchone()
                    if conversation is None:
                        return None

                    active_stream = connection.execute(
                        """
                        SELECT 1 FROM messages
                        WHERE conversation_id = ? AND status = 'streaming'
                        LIMIT 1
                        """,
                        (candidate_conversation,),
                    ).fetchone()
                    if active_stream is not None:
                        raise ValueError(
                            "Cannot rewrite a conversation while generation is active."
                        )

                    target = connection.execute(
                        """
                        SELECT rowid, role
                        FROM messages
                        WHERE conversation_id = ? AND message_id = ?
                        """,
                        (candidate_conversation, candidate_message),
                    ).fetchone()
                    if target is None:
                        return None
                    if str(target["role"]) != "user":
                        raise ValueError(
                            "Conversation branch rewrites must start from a user message."
                        )

                    connection.execute(
                        """
                        DELETE FROM messages
                        WHERE conversation_id = ? AND rowid >= ?
                        """,
                        (candidate_conversation, int(target["rowid"])),
                    )

                    remaining = connection.execute(
                        "SELECT COUNT(*) AS message_count FROM messages WHERE conversation_id = ?",
                        (candidate_conversation,),
                    ).fetchone()
                    if remaining is not None and int(remaining["message_count"]) == 0:
                        connection.execute(
                            "UPDATE conversations SET title = 'New conversation' WHERE conversation_id = ?",
                            (candidate_conversation,),
                        )

        return self.get(candidate_conversation)


__all__ = ["ConversationLifecycleService"]
