"""Conversation history manager for ChatGPT-style overlay sessions.

The manager keeps chat history in memory only. Persistence can be added later
without coupling the Overlay UI to storage details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from app.ai.chat.models import ChatContext, ChatMessage


@dataclass
class Conversation:
    conversation_id: str = field(default_factory=lambda: uuid4().hex)
    title: str = "新对话"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    provider: str = ""
    model: str = ""
    context: ChatContext = field(default_factory=ChatContext)
    messages: list[ChatMessage] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = datetime.now()


class ConversationManager:
    """Manage multiple overlay chat conversations like ChatGPT sessions."""

    def __init__(self, max_sessions: int = 20) -> None:
        self.max_sessions = max(1, int(max_sessions))
        self._sessions: list[Conversation] = []
        self._active_id: str | None = None

    @property
    def conversations(self) -> tuple[Conversation, ...]:
        return tuple(self._sessions)

    @property
    def active(self) -> Conversation | None:
        for item in self._sessions:
            if item.conversation_id == self._active_id:
                return item
        return None

    def new_conversation(self) -> Conversation:
        session = Conversation()
        self._sessions.insert(0, session)
        self._active_id = session.conversation_id
        self._trim()
        return session

    def switch(self, conversation_id: str) -> Conversation | None:
        for item in self._sessions:
            if item.conversation_id == conversation_id:
                self._active_id = conversation_id
                item.touch()
                return item
        return None

    def remove(self, conversation_id: str) -> None:
        self._sessions = [
            item for item in self._sessions
            if item.conversation_id != conversation_id
        ]
        if self._active_id == conversation_id:
            self._active_id = None

    def _trim(self) -> None:
        if len(self._sessions) > self.max_sessions:
            self._sessions = self._sessions[: self.max_sessions]


__all__ = ["Conversation", "ConversationManager"]
