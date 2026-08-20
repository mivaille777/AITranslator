"""LangGraph orchestration for deterministic translation and agentic chat."""

from __future__ import annotations

from dataclasses import replace
from threading import Event
from typing import Any, Literal, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.ai.chat.models import ChatRequest, ChatResult
from app.ai.errors import AIResponseError
from app.models.translation import TranslationResult
from app.translation.errors import TranslationError
from app.translation.manager import TranslationManager


class AgentWorkflowState(TypedDict, total=False):
    """Shared graph state for one foreground user intent."""

    intent: Literal["translation", "chat"]
    request_id: int
    status: str
    source_text: str
    source_language: str | None
    target_language: str | None
    translation_manager: Any
    translation_result: TranslationResult
    chat_request: ChatRequest
    chat_service: Any
    cancel_event: Event
    chat_result: ChatResult
    partial_text: str
    cancelled: bool


class AITranslatorAgentGraph:
    """One state graph for AITranslator's translation and chat execution.

    The UI/controller owns presentation, persistence and request-version
    invalidation. This graph owns execution routing and state transitions. Chat
    nodes expose arbitrary provider tokens through LangGraph's ``custom``
    stream channel, allowing the current OpenAI-compatible clients to remain
    unchanged while still gaining an explicit agent runtime.
    """

    def __init__(self) -> None:
        builder = StateGraph(AgentWorkflowState)
        builder.add_node("prepare", self._prepare)
        builder.add_node("translation", self._translation_node)
        builder.add_node("chat", self._chat_node)
        builder.add_edge(START, "prepare")
        builder.add_conditional_edges(
            "prepare",
            self._route,
            {
                "translation": "translation",
                "chat": "chat",
            },
        )
        builder.add_edge("translation", END)
        builder.add_edge("chat", END)
        self.graph = builder.compile()

    @staticmethod
    def _prepare(state: AgentWorkflowState) -> AgentWorkflowState:
        intent = state.get("intent")
        if intent not in {"translation", "chat"}:
            raise ValueError("unsupported AITranslator agent intent")
        return {
            "status": "prepared",
            "request_id": int(state.get("request_id", 0)),
        }

    @staticmethod
    def _route(state: AgentWorkflowState) -> Literal["translation", "chat"]:
        intent = state.get("intent")
        if intent == "translation":
            return "translation"
        return "chat"

    @staticmethod
    def _translation_node(state: AgentWorkflowState) -> AgentWorkflowState:
        manager = state.get("translation_manager")
        source_text = str(state.get("source_text", ""))
        source_language = state.get("source_language")
        target_language = state.get("target_language")
        request_id = int(state.get("request_id", 0))
        if manager is None:
            raise TranslationError("translation manager is unavailable")

        if isinstance(manager, TranslationManager):
            result = manager.translate(
                source_text,
                source_language=source_language,
                target_language=target_language,
                request_id=request_id,
            )
        elif source_language is None and target_language is None:
            result = manager.translate(source_text)
        else:
            result = manager.translate(
                source_text,
                source_language=source_language,
                target_language=target_language,
            )

        if not isinstance(result, TranslationResult):
            raise TranslationError("translation graph returned unsupported result")
        if result.request_id != request_id:
            result = replace(result, request_id=request_id)
        return {
            "status": "completed",
            "translation_result": result,
            "cancelled": False,
        }

    @staticmethod
    def _chat_node(state: AgentWorkflowState) -> AgentWorkflowState:
        service = state.get("chat_service")
        request = state.get("chat_request")
        cancel_event = state.get("cancel_event")
        if service is None or not isinstance(request, ChatRequest):
            raise AIResponseError("chat graph input is unavailable")
        if cancel_event is None:
            cancel_event = Event()

        writer = get_stream_writer()
        pieces: list[str] = []
        stream = getattr(service, "stream", None)
        iterator: Any | None = None
        try:
            if cancel_event.is_set():
                return {
                    "status": "cancelled",
                    "cancelled": True,
                    "partial_text": "",
                }

            if callable(stream):
                iterator = iter(stream(request))
                for delta in iterator:
                    if cancel_event.is_set():
                        break
                    if not isinstance(delta, str) or not delta:
                        continue
                    pieces.append(delta)
                    accumulated = "".join(pieces)
                    writer(
                        {
                            "kind": "chat_chunk",
                            "request_id": request.request_id,
                            "session_id": request.session_id,
                            "delta": delta,
                            "accumulated_text": accumulated,
                        }
                    )
            else:
                result = service.execute(request)
                if cancel_event.is_set():
                    return {
                        "status": "cancelled",
                        "cancelled": True,
                        "partial_text": "",
                    }
                output = str(getattr(result, "output_text", ""))
                if output:
                    pieces.append(output)
                    writer(
                        {
                            "kind": "chat_chunk",
                            "request_id": request.request_id,
                            "session_id": request.session_id,
                            "delta": output,
                            "accumulated_text": output,
                        }
                    )
        finally:
            if cancel_event.is_set():
                close = getattr(iterator, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass

        output = "".join(pieces).strip()
        if cancel_event.is_set():
            return {
                "status": "cancelled",
                "cancelled": True,
                "partial_text": output,
            }
        if not output:
            raise AIResponseError("AI chat provider returned empty content.")

        return {
            "status": "completed",
            "cancelled": False,
            "partial_text": output,
            "chat_result": ChatResult(
                session_id=request.session_id,
                user_message=request.user_message,
                output_text=output,
                provider=str(getattr(service, "provider_name", "unknown")),
                model=str(getattr(service, "model", "unknown")),
                request_id=request.request_id,
            ),
        }

    def run_translation(
        self,
        translation_manager: Any,
        source_text: str,
        *,
        source_language: str | None = None,
        target_language: str | None = None,
        request_id: int = 0,
    ) -> TranslationResult:
        state = self.graph.invoke(
            {
                "intent": "translation",
                "request_id": int(request_id),
                "translation_manager": translation_manager,
                "source_text": str(source_text),
                "source_language": source_language,
                "target_language": target_language,
            }
        )
        result = state.get("translation_result")
        if not isinstance(result, TranslationResult):
            raise TranslationError("translation graph produced no result")
        return result

    def stream_chat(
        self,
        chat_service: Any,
        request: ChatRequest,
        *,
        cancel_event: Event | None = None,
    ):
        """Yield LangGraph v2 custom/update stream parts for one chat run."""

        event = cancel_event or Event()
        yield from self.graph.stream(
            {
                "intent": "chat",
                "request_id": int(request.request_id),
                "chat_service": chat_service,
                "chat_request": request,
                "cancel_event": event,
            },
            stream_mode=["custom", "updates"],
            version="v2",
        )


# This compiled graph has no checkpointer or mutable per-run state. Every
# invocation receives an isolated input state, so worker threads can share it.
DEFAULT_AGENT_GRAPH = AITranslatorAgentGraph()


__all__ = [
    "AITranslatorAgentGraph",
    "AgentWorkflowState",
    "DEFAULT_AGENT_GRAPH",
]
