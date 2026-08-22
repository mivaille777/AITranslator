from __future__ import annotations

from dataclasses import dataclass, field
from queue import Empty, Queue
from threading import Event, Thread
from time import monotonic
from typing import Callable, TypeVar

from backend.agent_core.exceptions import (
    AgentBudgetExceededError,
    AgentCancelledError,
    AgentToolTimeoutError,
)

T = TypeVar("T")


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


def run_safe_tool_with_timeout(
    operation: Callable[[], T],
    *,
    control: AgentRunControl,
    tool_name: str,
) -> T:
    """Run a read/compute tool with cooperative cancellation and a hard wait bound.

    The worker is daemonized because Python cannot safely interrupt a blocking
    provider call. This helper must therefore never wrap write tools or other
    side-effectful operations.
    """

    control.checkpoint(f"tool:{tool_name}")
    timeout = control.bounded_tool_timeout()
    if timeout <= 0:
        raise AgentBudgetExceededError(
            f"Agent execution budget exhausted before tool {tool_name}."
        )

    queue: Queue[tuple[bool, object]] = Queue(maxsize=1)

    def worker() -> None:
        try:
            queue.put((True, operation()))
        except Exception as exc:
            queue.put((False, exc))

    Thread(target=worker, name=f"agent-tool-{tool_name}", daemon=True).start()
    started = monotonic()
    while True:
        control.checkpoint(f"tool:{tool_name}")
        elapsed = monotonic() - started
        remaining = timeout - elapsed
        if remaining <= 0:
            raise AgentToolTimeoutError(
                f"Agent tool {tool_name} exceeded {timeout:.2f}s timeout."
            )
        try:
            ok, value = queue.get(timeout=min(0.05, remaining))
        except Empty:
            continue
        if ok:
            return value  # type: ignore[return-value]
        if isinstance(value, Exception):
            raise value
        raise RuntimeError(f"Agent tool {tool_name} failed without an exception.")


__all__ = [
    "AgentExecutionPolicy",
    "AgentRunControl",
    "run_safe_tool_with_timeout",
]
