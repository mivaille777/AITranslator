from __future__ import annotations

from contextlib import closing
from typing import Any

from backend.services.conversation_store_service import (
    ConversationStoreService,
    ExchangeStart,
    StoredConversation,
)


def _branch_title(value: object, *, max_chars: int = 42) -> str:
    compact = " ".join(str(value or "").strip().split())
    if not compact:
        return "New conversation"
    return compact if len(compact) <= max_chars else compact[: max_chars - 1].rstrip() + "…"


class ConversationLifecycleService(ConversationStoreService):
    """Add branch-editing lifecycle operations to the durable Web chat store.

    The base store remains responsible for schema, streaming message state and
    persistence. This layer owns branch rewinds used by Retry, Regenerate and
    Edit & Resend, keeping those mutations below the HTTP/UI boundary.
    """

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

    def rewind_from_user_message(
        self,
        conversation_id: str,
        user_message_id: str,
    ) -> StoredConversation | None:
        """Delete one user message and every later branch message.

        The target must be a persisted user message. Rewinding is rejected while
        any assistant message is still streaming so a provider worker cannot
        race with branch deletion. The caller can then send the original or an
        edited user message to create a replacement branch.
        """

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
                        raise ValueError("Cannot rewrite a conversation while generation is active.")

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
                        raise ValueError("Conversation branch rewrites must start from a user message.")

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
