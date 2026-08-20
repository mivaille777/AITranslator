"""Qt worker for LangGraph document/web tool execution."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from PySide6.QtCore import QObject, QRunnable, Signal

from app.agent.tool_runtime import AgentToolCoordinator, AgentToolOutcome
from app.infrastructure.logging import sanitized_exception_info


@dataclass(frozen=True, slots=True)
class AgentToolTaskFailure:
    request_id: int
    user_message: str
    error: Exception


class AgentToolTaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal(object)


class AgentToolTask(QRunnable):
    """Execute one file/web tool graph away from the Qt GUI thread."""

    def __init__(
        self,
        coordinator: AgentToolCoordinator,
        user_message: str,
        *,
        selected_file: str = "",
        request_id: int = 0,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.coordinator = coordinator
        self.user_message = str(user_message)
        self.selected_file = str(selected_file or "")
        self.request_id = int(request_id)
        self.logger = logger or logging.getLogger("desktop_translator")
        self.signals = AgentToolTaskSignals()

    def run(self) -> None:
        try:
            outcome = self.coordinator.execute_message(
                self.user_message,
                selected_file=self.selected_file,
            )
            if not isinstance(outcome, AgentToolOutcome):
                raise RuntimeError("agent tool runtime returned unsupported output")
            self.signals.succeeded.emit((self.request_id, self.user_message, outcome))
        except Exception as exc:
            self.logger.error(
                "agent_tool_worker_failed tool_request_id=%s error_type=%s",
                self.request_id,
                type(exc).__name__,
                exc_info=sanitized_exception_info(exc),
            )
            self.signals.failed.emit(
                AgentToolTaskFailure(
                    request_id=self.request_id,
                    user_message=self.user_message,
                    error=exc,
                )
            )
        finally:
            self.signals.finished.emit(self)


__all__ = ["AgentToolTask", "AgentToolTaskFailure", "AgentToolTaskSignals"]
