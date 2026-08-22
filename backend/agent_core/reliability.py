from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event
from time import monotonic

from backend.agent_core.exceptions import AgentBudgetExceededError, AgentCancelledError


@dataclass(frozen=True, slots=True)
class AgentExecutionPolicy:
    """Bounded execution policy for one Agent run.

    Retries are intentionally limited to read/compute tools by ProductAgentService.
    Write tools are never automatically retried.
    """

    total_timeout_seconds: float = 45.0
    tool_timeout_seconds: float = 20.0
    max_safe_retries: int = 1

    def __post_init__(self) -> None:
        if self.total_timeout_seconds <= 0:
            raise ValueError("total_timeout_seconds must be positive")
        if self.tool_timeout_seconds <= 0:
            raise ValueError("tool_timeout_seconds must be positive")
        if self.max_safe_retries < 0:
            raise ValueError("max_safe_retries must be non-negative")


@dataclass(slots=True)
class AgentRunControl:
    policy: AgentExecutionPolicy = field(default_factory=AgentExecutionPolicy)
    cancel_event: Event = field(default_factory=Event)
    started_at: float = field(default_factory=monotonic)

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, monotonic() - self.started_at)

    @property
    def elapsed_ms(self) -> int:
        return int(self.elapsed_seconds * 1000)

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.policy.total_timeout_seconds - self.elapsed_seconds)

    def cancel(self) -> None:
        self.cancel_event.set()

    def checkpoint(self, stage: str) -> None:
        if self.cancel_event.is_set():
            raise AgentCancelledError(f"Agent run cancelled before {stage}.")
        if self.remaining_seconds <= 0:
            raise AgentBudgetExceededError(
                f"Agent execution budget exceeded before {stage}."
            )

    def bounded_tool_timeout(self) -> float:
        return min(self.policy.tool_timeout_seconds, self.remaining_seconds)


__all__ = ["AgentExecutionPolicy", "AgentRunControl"]
