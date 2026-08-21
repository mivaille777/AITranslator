from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from app.ai.chat.models import (
    ChatContext,
    ChatMessage,
    ChatRequest,
    ChatRole,
    ReadingContext,
)
from app.ai.chat.service import AIChatService
from app.ai.chat.stream_service import ProviderStreamingAIChatService
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
    """WebReBuild boundary around the existing provider-neutral chat core.

    REST requests keep using the stable non-streaming service for compatibility.
    WebSocket requests use the UI-independent streaming core. Neither path
    introduces LangGraph or desktop UI ownership into normal Companion chat.
    """

    def __init__(
        self,
        *,
        text_service: AITextService | Any | None = None,
        chat_service: AIChatService | Any | None = None,
        stream_service: ProviderStreamingAIChatService | Any | None = None,
    ) -> None:
        self._text_service = text_service
        self._chat_service = chat_service
        self._stream_service = stream_service

    def _ensure_text_service(self) -> AITextService | Any:
        if self._text_service is None:
            self._text_service = AITextService()
        return self._text_service

    def _ensure_chat_service(self) -> AIChatService | Any:
        if self._chat_service is None:
            self._chat_service = AIChatService(self._ensure_text_service())
        return self._chat_service

    def _ensure_stream_service(self) -> ProviderStreamingAIChatService | Any:
        if self._stream_service is None:
            self._stream_service = ProviderStreamingAIChatService(
                self._ensure_text_service()
            )
        return self._stream_service

    @property
    def provider_name(self) -> str:
        service = self._ensure_text_service()
        return str(getattr(service, "provider_name", "")).strip() or "unknown"

    @property
    def model(self) -> str:
        service = self._ensure_text_service()
        return str(getattr(service, "model", "")).strip() or "unknown"

    def status(self) -> tuple[bool, str, str, str]:
        try:
            return True, self.provider_name, self.model, ""
        except AIConfigurationError as exc:
            return False, "deepseek", "", str(exc)

    @staticmethod
    def _build_request(
        *,
        session_id: str,
        user_message: str,
        source_text: str = "",
        translated_text: str = "",
        source_language: str = "auto",
        target_language: str = "zh-CN",
        resource_url: str = "",
        resource_title: str = "",
        section_heading: str = "",
        context_before: str = "",
        context_after: str = "",
        source_kind: str = "",
        history: tuple[tuple[str, str], ...] = (),
        request_id: int = 0,
        context_mode: str = "reading",
    ) -> ChatRequest:
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

        grounded = str(context_mode or "").strip().lower() == "reading"
        context = ChatContext(
            source_text=source_text if grounded else "",
            translated_text=translated_text if grounded else "",
            reading=ReadingContext(
                resource_url=resource_url if grounded else "",
                resource_title=resource_title if grounded else "",
                section_heading=section_heading if grounded else "",
                context_before=context_before if grounded else "",
                context_after=context_after if grounded else "",
                source_kind=source_kind if grounded else "",
            ),
        )
        return ChatRequest(
            session_id=session_id,
            user_message=user_message,
            context=context,
            history=tuple(messages),
            request_id=request_id,
        )

    def send(self, **kwargs: Any) -> CompanionChatResult:
        request = self._build_request(**kwargs)
        result = self._ensure_chat_service().execute(request)
        return CompanionChatResult(
            session_id=result.session_id,
            user_message=result.user_message,
            output_text=result.output_text,
            provider=result.provider,
            model=result.model,
            request_id=result.request_id,
        )

    def stream(self, **kwargs: Any) -> Iterator[str]:
        request = self._build_request(**kwargs)
        yield from self._ensure_stream_service().stream(request)

    def close(self) -> None:
        service = self._text_service
        self._stream_service = None
        self._chat_service = None
        self._text_service = None
        if service is not None:
            service.close()
