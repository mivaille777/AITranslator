"""Qt worker wrapper for non-streaming conversational AI."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from PySide6.QtCore import QObject, QRunnable, Signal

from app.ai.chat.models import ChatRequest
from app.ai.errors import AIError, AIResponseError


class AIChatTaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal(object)


@dataclass(frozen=True, slots=True)
class AIChatTaskFailure:
    request_id: int
    error: AIError


class AIChatTask(QRunnable):
    """Run one chat request away from the GUI thread."""

    def __init__(
        self,
        chat_service,
        request: ChatRequest,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self.chat_service = chat_service
        self.request = request
        self.logger = logger or logging.getLogger("desktop_translator")
        self.signals = AIChatTaskSignals()
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            result = self.chat_service.execute(self.request)
        except AIError as exc:
            self.signals.failed.emit(
                AIChatTaskFailure(
                    request_id=self.request.request_id,
                    error=exc,
                )
            )
        except Exception as exc:
            error = AIResponseError("AI chat request failed.")
            error.__cause__ = exc
            self.signals.failed.emit(
                AIChatTaskFailure(
                    request_id=self.request.request_id,
                    error=error,
                )
            )
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit(self)


__all__ = ["AIChatTask", "AIChatTaskFailure", "AIChatTaskSignals"]
