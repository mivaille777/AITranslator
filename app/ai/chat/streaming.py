"""Streaming conversational AI execution for the legacy Overlay chat."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from threading import Event
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal

from app.agent.workflow import DEFAULT_AGENT_GRAPH
from app.ai.chat.models import ChatRequest, ChatResult
from app.ai.chat.stream_service import ProviderStreamingAIChatService
from app.ai.chat.task import AIChatTaskFailure
from app.ai.errors import AIError, AIResponseError


@dataclass(frozen=True, slots=True)
class AIChatStreamChunk:
    """One ordered UI update from a LangGraph chat stream."""

    request_id: int
    session_id: str
    delta: str
    accumulated_text: str


class StreamingAIChatService(ProviderStreamingAIChatService):
    """Backward-compatible legacy name for the shared provider stream core."""


class StreamingAIChatTaskSignals(QObject):
    chunk = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal(object)


class StreamingAIChatTask(QRunnable):
    """Execute the chat branch of the shared LangGraph on a Qt worker."""

    def __init__(
        self,
        chat_service: StreamingAIChatService | Any,
        request: ChatRequest,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self.chat_service = chat_service
        self.request = request
        self.logger = logger or logging.getLogger("desktop_translator")
        self.signals = StreamingAIChatTaskSignals()
        self._cancel_event = Event()
        self.setAutoDelete(False)

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """Request cooperative cancellation of the LangGraph chat node."""

        self._cancel_event.set()

    def run(self) -> None:
        final_result: ChatResult | None = None
        try:
            if self.is_cancelled:
                return
            for part in DEFAULT_AGENT_GRAPH.stream_chat(
                self.chat_service,
                self.request,
                cancel_event=self._cancel_event,
            ):
                if self.is_cancelled:
                    continue
                part_type = str(part.get("type", "")) if isinstance(part, dict) else ""
                data = part.get("data") if isinstance(part, dict) else None

                if part_type == "custom" and isinstance(data, dict):
                    if data.get("kind") != "chat_chunk":
                        continue
                    self.signals.chunk.emit(
                        AIChatStreamChunk(
                            request_id=int(data.get("request_id", self.request.request_id)),
                            session_id=str(data.get("session_id", self.request.session_id)),
                            delta=str(data.get("delta", "")),
                            accumulated_text=str(data.get("accumulated_text", "")),
                        )
                    )
                    continue

                if part_type != "updates" or not isinstance(data, dict):
                    continue
                for update in data.values():
                    if not isinstance(update, dict):
                        continue
                    candidate = update.get("chat_result")
                    if isinstance(candidate, ChatResult):
                        final_result = candidate

            if self.is_cancelled:
                return
            if final_result is None:
                raise AIResponseError("LangGraph chat workflow produced no result.")
            self.signals.succeeded.emit(final_result)
        except AIError as exc:
            if not self.is_cancelled:
                self.signals.failed.emit(
                    AIChatTaskFailure(
                        request_id=self.request.request_id,
                        error=exc,
                    )
                )
        except Exception as exc:
            if not self.is_cancelled:
                error = AIResponseError("AI chat LangGraph execution failed.")
                error.__cause__ = exc
                self.signals.failed.emit(
                    AIChatTaskFailure(
                        request_id=self.request.request_id,
                        error=error,
                    )
                )
        finally:
            self.signals.finished.emit(self)


__all__ = [
    "AIChatStreamChunk",
    "StreamingAIChatService",
    "StreamingAIChatTask",
    "StreamingAIChatTaskSignals",
]
