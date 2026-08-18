"""Qt worker task for running one AI text request outside the GUI thread."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal

from app.ai.errors import AIError, AIResponseError
from app.ai.models import AITextAction, AITextRequest, AITextResult
from app.ai.service import AITextService
from app.infrastructure.logging import sanitized_exception_info


class AITextTaskSignals(QObject):
    """Signals emitted by :class:`AITextTask` from a QThreadPool worker."""

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal(object)


@dataclass(frozen=True, slots=True)
class AITextTaskFailure:
    """A worker failure paired with the request version and operation."""

    request_id: int
    action: AITextAction
    error: AIError


class AITextTask(QRunnable):
    """Execute one structured AI request without blocking the Qt GUI thread."""

    def __init__(
        self,
        ai_service: AITextService | Any,
        request: AITextRequest,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        # Match TranslationTask lifetime semantics: the controller will keep
        # the Python wrapper alive until ``finished`` removes it from its
        # active task set.
        self.setAutoDelete(False)
        self.signals = AITextTaskSignals()
        self.ai_service = ai_service
        self.request = request
        self.request_id = request.request_id if isinstance(request, AITextRequest) else 0
        self.action = (
            request.action
            if isinstance(request, AITextRequest) and isinstance(request.action, AITextAction)
            else AITextAction.TRANSLATE
        )
        self.logger = logger or logging.getLogger("desktop_translator")

    def run(self) -> None:
        """Execute the synchronous service call on a QThreadPool worker."""

        try:
            if not isinstance(self.request, AITextRequest):
                raise AIResponseError("AI text task requires an AITextRequest.")
            result = self.ai_service.execute(self.request)
            if not isinstance(result, AITextResult):
                raise AIResponseError("AI text task returned an unsupported result.")
            if result.request_id != self.request_id:
                result = replace(result, request_id=self.request_id)
            self.signals.succeeded.emit(result)
        except AIError as exc:
            self.logger.error(
                "ai_text_worker_failed error_type=%s request_id=%s action=%s",
                type(exc).__name__,
                self.request_id,
                self.action.value,
                exc_info=sanitized_exception_info(exc),
            )
            self.signals.failed.emit(
                AITextTaskFailure(
                    request_id=self.request_id,
                    action=self.action,
                    error=exc,
                )
            )
        except Exception as exc:
            # Convert any contract violation before it crosses the QRunnable
            # boundary. Raw provider/SDK exception messages are not emitted to
            # the UI or included in the public error string.
            error = AIResponseError("AI text task failed.")
            error.__cause__ = exc
            self.logger.error(
                "ai_text_worker_unexpected_error error_type=%s request_id=%s action=%s",
                type(exc).__name__,
                self.request_id,
                self.action.value,
                exc_info=sanitized_exception_info(exc),
            )
            self.signals.failed.emit(
                AITextTaskFailure(
                    request_id=self.request_id,
                    action=self.action,
                    error=error,
                )
            )
        finally:
            self.signals.finished.emit(self)


__all__ = [
    "AITextTask",
    "AITextTaskFailure",
    "AITextTaskSignals",
]
