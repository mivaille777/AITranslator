"""Persistent ChatGPT-style conversation history for Overlay chat."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from app.ai.chat.models import ChatContext, ChatMessage, ChatRole
from app.infrastructure.paths import writable_config_dir


DEFAULT_MAX_CONVERSATIONS = 30
DEFAULT_HISTORY_FILENAME = "chat_history.json"


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

    def to_dict(self) -> dict[str, object]:
        return {
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "context": {
                "source_text": self.context.source_text,
                "translated_text": self.context.translated_text,
            },
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in self.messages
            ],
        }

    @classmethod
    def from_dict(cls, payload: object) -> "Conversation | None":
        if not isinstance(payload, dict):
            return None
        try:
            context_payload = payload.get("context", {})
            if not isinstance(context_payload, dict):
                context_payload = {}
            messages: list[ChatMessage] = []
            raw_messages = payload.get("messages", [])
            if isinstance(raw_messages, list):
                for item in raw_messages:
                    if not isinstance(item, dict):
                        continue
                    try:
                        role = ChatRole(str(item.get("role", "")))
                    except ValueError:
                        continue
                    content = str(item.get("content", "")).strip()
                    if content:
                        messages.append(ChatMessage(role, content))
            conversation_id = str(payload.get("conversation_id", "")).strip() or uuid4().hex
            session_id = str(payload.get("session_id", "")).strip() or uuid4().hex
            return cls(
                conversation_id=conversation_id,
                session_id=session_id,
                title=str(payload.get("title", "新对话")).strip() or "新对话",
                created_at=str(payload.get("created_at", "")).strip() or _now_iso(),
                updated_at=str(payload.get("updated_at", "")).strip() or _now_iso(),
                provider=str(payload.get("provider", "")).strip(),
                model=str(payload.get("model", "")).strip(),
                base_url=str(payload.get("base_url", "")).strip(),
                context=ChatContext(
                    source_text=str(context_payload.get("source_text", "")).strip(),
                    translated_text=str(context_payload.get("translated_text", "")).strip(),
                ),
                messages=messages,
            )
        except Exception:
            return None


class ConversationManager:
    """Maintain recent conversations and persist them as local user state.

    The ordering mirrors ChatGPT-style recency: the active/recently updated
    conversation is first. Titles are derived from the first user message, and
    storage is local JSON under the writable AITranslator config directory.
    API credentials are never written here.
    """

    def __init__(
        self,
        max_sessions: int = DEFAULT_MAX_CONVERSATIONS,
        *,
        storage_path: str | Path | None = None,
    ) -> None:
        self.max_sessions = max(1, int(max_sessions))
        self.storage_path = Path(storage_path) if storage_path is not None else _default_history_path()
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

    def load(self) -> None:
        self._sessions = []
        self._active_id = None
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        raw_items = payload.get("conversations", [])
        if isinstance(raw_items, list):
            for raw in raw_items:
                item = Conversation.from_dict(raw)
                if item is not None:
                    self._sessions.append(item)
        self._active_id = str(payload.get("active_id", "")).strip() or None
        self._trim()

    def save(self) -> None:
        self._trim()
        payload = {
            "version": 1,
            "active_id": self._active_id,
            "conversations": [item.to_dict() for item in self._sessions],
        }
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path: Path | None = None
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{self.storage_path.stem}-",
                suffix=".tmp",
                dir=self.storage_path.parent,
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.storage_path)
        except OSError:
            try:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


__all__ = [
    "Conversation",
    "ConversationManager",
    "DEFAULT_HISTORY_FILENAME",
    "DEFAULT_MAX_CONVERSATIONS",
]
