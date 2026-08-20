from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.chat.models import (
    ChatContext,
    ChatMessage,
    ChatRequest,
    ChatRole,
    ReadingContext,
)
from app.ai.chat.service import AIChatService
from app.ai.errors import AIConfigurationError
from app.ai.service import AITextService


@dataclass(frozen=True, slots=True)
class CompanionChatResult:
    session_id: str
    user_message: str
    output_text: str
    provider: str
    model: str
    request_id: int = 0


class CompanionChatService:
    """Non-streaming WebReBuild bridge to the existing provider-neutral chat core.

    This keeps Stage 2E useful without introducing LangGraph or persistent chat
    session ownership. Streaming and durable conversation history remain a later
    chat-stage concern.
    """

    def __init__(
        self,
        *,
        text_service: AITextService | Any | None = None,
        chat_service: AIChatService | Any | None = None,
    ) -> None:
        self._text_service = text_service
        self._chat_service = chat_service

    def _ensure_text_service(self) -> AITextService | Any:
        if self._text_service is None:
            self._text_service = AITextService()
        return self._text_service

    def _ensure_chat_service(self) -> AIChatService | Any:
        if self._chat_service is None:
            self._chat_service = AIChatService(self._ensure_text_service())
        return self._chat_service

    def status(self) -> tuple[bool, str, str, str]:
        try:
            service = self._ensure_text_service()
            return True, service.provider_name, service.model, ""
        except AIConfigurationError as exc:
            return False, "deepseek", "", str(exc)

    def send(
        self,
        *,
        session_id: str,
        user_message: str,
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
        history: tuple[tuple[str, str], ...] = (),
        request_id: int = 0,
    ) -> CompanionChatResult:
        _ = (source_language, target_language)

        messages: list[ChatMessage] = []
        for role_value, content in history[-32:]:
            text = str(content or "").strip()
            if not text:
                continue
            messages.append(
                ChatMessage(
                    role=ChatRole(str(role_value)),
                    content=text,
                )
            )

        context = ChatContext(
            source_text=source_text,
            translated_text=translated_text,
            reading=ReadingContext(
                resource_url=resource_url,
                resource_title=resource_title,
                section_heading=section_heading,
                context_before=context_before,
                context_after=context_after,
                source_kind=source_kind,
            ),
        )
        result = self._ensure_chat_service().execute(
            ChatRequest(
                session_id=session_id,
                user_message=user_message,
                context=context,
                history=tuple(messages),
                request_id=request_id,
            )
        )
        return CompanionChatResult(
            session_id=result.session_id,
            user_message=result.user_message,
            output_text=result.output_text,
            provider=result.provider,
            model=result.model,
            request_id=result.request_id,
        )

    def close(self) -> None:
        service = self._text_service
        self._chat_service = None
        self._text_service = None
        if service is not None:
            service.close()
