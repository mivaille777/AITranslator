"""In-memory, non-persistent chat session state."""

from __future__ import annotations

from uuid import uuid4

from app.ai.chat.models import (
    ChatContext,
    ChatMessage,
    ChatRequest,
    ChatRole,
    ReadingContext,
)


DEFAULT_MAX_CHAT_MESSAGES = 20


class ChatSession:
    """Own one active Overlay conversation without persisting private text."""

    def __init__(self, *, max_messages: int = DEFAULT_MAX_CHAT_MESSAGES) -> None:
        self.session_id = uuid4().hex
        self.max_messages = max(2, int(max_messages))
        self.context = ChatContext()
        self._messages: list[ChatMessage] = []

    @property
    def messages(self) -> tuple[ChatMessage, ...]:
        return tuple(self._messages)

    def set_context(self, context: ChatContext) -> bool:
        """Replace context and rotate session identity when reading context changes."""

        reading = (
            context.reading
            if isinstance(context.reading, ReadingContext)
            else ReadingContext()
        )
        normalized = ChatContext(
            source_text=str(context.source_text or "").strip(),
            translated_text=str(context.translated_text or "").strip(),
            reading=ReadingContext(
                resource_url=str(reading.resource_url or "").strip(),
                resource_title=str(reading.resource_title or "").strip(),
                section_heading=str(reading.section_heading or "").strip(),
                context_before=str(reading.context_before or "").strip(),
                context_after=str(reading.context_after or "").strip(),
                source_kind=str(reading.source_kind or "").strip(),
            ),
        )
        changed = normalized != self.context
        if changed:
            self.context = normalized
            self.session_id = uuid4().hex
            self.clear()
        return changed

    def clear(self) -> None:
        self._messages.clear()

    def request(self, user_message: str, *, request_id: int) -> ChatRequest:
        message = str(user_message).strip()
        if not message:
            raise ValueError("Chat message must not be empty.")
        return ChatRequest(
            session_id=self.session_id,
            user_message=message,
            context=self.context,
            history=self.messages,
            request_id=int(request_id),
        )

    def commit_exchange(self, user_message: str, assistant_message: str) -> None:
        user = str(user_message).strip()
        assistant = str(assistant_message).strip()
        if not user or not assistant:
            return
        self._messages.extend(
            (
                ChatMessage(ChatRole.USER, user),
                ChatMessage(ChatRole.ASSISTANT, assistant),
            )
        )
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages :]


__all__ = ["ChatSession", "DEFAULT_MAX_CHAT_MESSAGES"]
