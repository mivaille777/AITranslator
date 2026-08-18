"""Immutable data models for conversational AI requests and results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: ChatRole
    content: str


@dataclass(frozen=True, slots=True)
class ChatContext:
    source_text: str = ""
    translated_text: str = ""


@dataclass(frozen=True, slots=True)
class ChatRequest:
    session_id: str
    user_message: str
    context: ChatContext
    history: tuple[ChatMessage, ...] = ()
    request_id: int = 0


@dataclass(frozen=True, slots=True)
class ChatResult:
    session_id: str
    user_message: str
    output_text: str
    provider: str
    model: str
    request_id: int = 0


__all__ = [
    "ChatContext",
    "ChatMessage",
    "ChatRequest",
    "ChatResult",
    "ChatRole",
]
