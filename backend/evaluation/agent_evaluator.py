from __future__ import annotations

from dataclasses import dataclass

from backend.services.agent_trace_store_service import StoredAgentRun


@dataclass(frozen=True, slots=True)
class AgentEvaluationExpectation:
    case_id: str
    expected_intent: str = ""
    expected_tool_name: str = ""
    expected_status: str = "completed"
    max_total_duration_ms: int = 0
    max_retry_count: int = 0
    require_zero_failures: bool = True


@dataclass(frozen=True, slots=True)
class AgentEvaluationResult:
    case_id: str
    run_id: str
    trace_id: str
    passed: bool
    score: float
    intent_match: bool
    tool_match: bool
    status_match: bool
    latency_pass: bool
    retry_pass: bool
    failure_pass: bool
    failures: tuple[str, ...]


def _normalized(value: str) -> str:
    return str(value or "").strip().lower()


def evaluate_agent_run(
    run: StoredAgentRun,
    expectation: AgentEvaluationExpectation,
) -> AgentEvaluationResult:
    intent_match = (
        not expectation.expected_intent
        or _normalized(run.intent) == _normalized(expectation.expected_intent)
    )
    tool_match = (
        not expectation.expected_tool_name
        or _normalized(run.tool_name) == _normalized(expectation.expected_tool_name)
    )
    status_match = (
        not expectation.expected_status
        or _normalized(run.status) == _normalized(expectation.expected_status)
    )
    latency_pass = (
        expectation.max_total_duration_ms <= 0
        or run.total_duration_ms <= expectation.max_total_duration_ms
    )
    retry_pass = run.retry_count <= max(0, expectation.max_retry_count)
    failure_pass = not expectation.require_zero_failures or run.failure_count == 0

    checks = (
        intent_match,
        tool_match,
        status_match,
        latency_pass,
        retry_pass,
        failure_pass,
    )
    failures: list[str] = []
    if not intent_match:
        failures.append(
            f"intent expected={expectation.expected_intent!r} actual={run.intent!r}"
        )
    if not tool_match:
        failures.append(
            f"tool expected={expectation.expected_tool_name!r} actual={run.tool_name!r}"
        )
    if not status_match:
        failures.append(
            f"status expected={expectation.expected_status!r} actual={run.status!r}"
        )
    if not latency_pass:
        failures.append(
            f"latency max={expectation.max_total_duration_ms} actual={run.total_duration_ms}"
        )
    if not retry_pass:
        failures.append(
            f"retry_count max={expectation.max_retry_count} actual={run.retry_count}"
        )
    if not failure_pass:
        failures.append(f"failure_count actual={run.failure_count}")

    score = round(sum(1 for check in checks if check) / len(checks), 4)
    return AgentEvaluationResult(
        case_id=expectation.case_id,
        run_id=run.run_id,
        trace_id=run.trace_id,
        passed=all(checks),
        score=score,
        intent_match=intent_match,
        tool_match=tool_match,
        status_match=status_match,
        latency_pass=latency_pass,
        retry_pass=retry_pass,
        failure_pass=failure_pass,
        failures=tuple(failures),
    )


__all__ = [
    "AgentEvaluationExpectation",
    "AgentEvaluationResult",
    "evaluate_agent_run",
]
