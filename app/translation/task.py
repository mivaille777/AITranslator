"""Qt worker task for running one translation outside the GUI thread."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal

from app.agent.workflow import DEFAULT_AGENT_GRAPH
from app.infrastructure.logging import sanitized_exception_info
from app.models.translation import TranslationResult
from app.translation.errors import TranslationError


class TranslationTaskSignals(QObject):
    """Signals emitted by :class:`TranslationTask`.

    The signals carry plain Python objects so the task does not expose a
    provider SDK or make the UI depend on a particular translation backend.
    ``AppController`` is a GUI-thread QObject; Qt therefore queues these
    deliveries back to that thread when the task emits them from a worker.
    The failure signal carries ``TranslationTaskFailure`` so errors can be
    filtered by the same request version as successful results.
    """

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal(object)


@dataclass(frozen=True, slots=True)
class TranslationTaskFailure:
    """A worker failure paired with the request version that produced it."""

    request_id: int
    error: TranslationError


class TranslationTask(QRunnable):
    """Run one translation intent through the shared LangGraph workflow."""

    def __init__(
        self,
        translation_manager: Any,
        source_text: str,
        *,
        source_language: str | None = None,
        target_language: str | None = None,
        request_id: int = 0,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        # Keep the Python task alive until the controller receives ``finished``
        # and removes it from its active-task set. This also makes it safe to
        # inspect the task in tests after QThreadPool has completed it.
        self.setAutoDelete(False)
        self.signals = TranslationTaskSignals()
        self.translation_manager = translation_manager
        self.source_text = source_text
        self.source_language = source_language
        self.target_language = target_language
        self.request_id = request_id
        self.logger = logger or logging.getLogger("desktop_translator")

    def run(self) -> None:
        """Execute the LangGraph translation branch on the pool worker."""

        try:
            result = self._translate()
            if not isinstance(result, TranslationResult):
                raise TranslationError("translation task returned unsupported result")
            self.signals.succeeded.emit(result)
        except TranslationError as exc:
            self.logger.error(
                "translation_worker_failed error_type=%s request_id=%s",
                type(exc).__name__,
                self.request_id,
                exc_info=sanitized_exception_info(exc),
            )
            self.signals.failed.emit(
                TranslationTaskFailure(request_id=self.request_id, error=exc)
            )
        except Exception as exc:
            # A plugin/provider can still fail outside the graph's expected
            # domain. Convert that failure before it reaches Qt.
            error = TranslationError("translation task failed")
            error.__cause__ = exc
            self.logger.error(
                "translation_worker_unexpected_error error_type=%s request_id=%s",
                type(exc).__name__,
                self.request_id,
                exc_info=sanitized_exception_info(exc),
            )
            self.signals.failed.emit(
                TranslationTaskFailure(request_id=self.request_id, error=error)
            )
        finally:
            self.signals.finished.emit(self)

    def _translate(self) -> TranslationResult:
        """Run the translation node while preserving injected-manager support."""

        return DEFAULT_AGENT_GRAPH.run_translation(
            self.translation_manager,
            self.source_text,
            source_language=self.source_language,
            target_language=self.target_language,
            request_id=self.request_id,
        )


__all__ = [
    "TranslationTask",
    "TranslationTaskFailure",
    "TranslationTaskSignals",
]
