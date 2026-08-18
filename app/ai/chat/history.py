"""Conversation history management for ChatGPT-style Overlay sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.ai.chat.models import ChatContext, ChatMessage


@dataclass
class StoredChatConversation:
    """One independent conversation thread."""

    title: str
    context: ChatContext = field(default_factory=ChatContext)
    messages: list[ChatMessage] = field(default_factory=list)
    conversation_id: str = field(default_factory=lambda: uuid4().hex)


class ChatConversationManager:
    """Manage multiple chat threads like ChatGPT sidebar conversations.

    This layer intentionally separates conversation switching from the active
    Overlay session. Persistence can be added later without changing UI APIs.
    """

    def __init__(self, max_conversations: int = 20) -> None:
        self.max_conversations = max(1, int(max_conversations))
        self._items: list[StoredChatConversation] = []
        self._active_id: str | None = None

    @property
    def conversations(self) -> tuple[StoredChatConversation, ...]:
        return tuple(self._items)

    @property
    def active(self) -> StoredChatConversation | None:
        for item in self._items:
            if item.conversation_id == self._active_id:
                return item
        return None

    def create(self, title: str = "新对话") -> StoredChatConversation:
        item = StoredChatConversation(title=title.strip() or "新对话")
        self._items.insert(0, item)
        self._active_id = item.conversation_id
        self._items = self._items[: self.max_conversations]
        return item

    def switch(self, conversation_id: str) -> StoredChatConversation | None:
        for item in self._items:
            if item.conversation_id == conversation_id:
                self._active_id = conversation_id
                return item
        return None

    def remove(self, conversation_id: str) -> None:
        self._items = [i for i in self._items if i.conversation_id != conversation_id]
        if self._active_id == conversation_id:
            self._active_id = self._items[0].conversation_id if self._items else None


__all__ = ["ChatConversationManager", "StoredChatConversation"]
