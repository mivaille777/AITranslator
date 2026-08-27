from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.services.agent_trace_store_service import StoredAgentEvent, StoredAgentRun


@dataclass(frozen=True, slots=True)
class AgentEvaluationExpectation:
    case_id: str
    expected_intent: str = ""
    expected_tool_name: str = ""
    expected_tool_sequence: tuple[str, ...] = ()
    expected_status: str = "completed"
    max_total_duration_ms: int = 0
    max_retry_count: int = 0
    require_zero_failures: bool = True
    expect_react: bool | None = None
    max_react_iterations: int = 0
    max_tool_calls: int = 0
    max_redundant_actions: int | None = None
    require_no_react_limit: bool = False
    require_grounded_response: bool = False
    require_confirmation_guard: bool = False


@dataclass(frozen=True, slots=True)
class AgentTrajectoryMetrics:
    available: bool = False
    react_started: bool = False
    react_iteration_count: int = 0
    decision_count: int = 0
    tool_call_count: int = 0
    observation_count: int = 0
    tool_sequence: tuple[str, ...] = ()
    redundant_action_count: int = 0
    react_limit_reached: bool = False
    react_limit_reason: str = ""
    grounded: bool = False
    evidence_count: int = 0
    citation_count: int = 0
    knowledge_search_count: int = 0
    query_reformulation_count: int = 0
    novel_evidence_count: int = 0
    no_novel_evidence_search_count: int = 0
    retrieval_fallback_count: int = 0
    confirmation_required_action_count: int = 0
    write_result_count: int = 0
    confirmation_guard_pass: bool = True


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
    react_mode_pass: bool
    tool_sequence_pass: bool
    react_iteration_pass: bool
    tool_call_pass: bool
    redundancy_pass: bool
    react_limit_pass: bool
    grounding_pass: bool
    confirmation_pass: bool
    trajectory: AgentTrajectoryMetrics
    failures: tuple[str, ...]


def _normalized(value: str) -> str:
    return str(value or "").strip().lower()


def _safe_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _event_payload(event: StoredAgentEvent) -> dict[str, object]:
    return event.payload if isinstance(event.payload, dict) else {}


def derive_agent_trajectory_metrics(
    events: Iterable[StoredAgentEvent],
    *,
    run_status: str = "",
) -> AgentTrajectoryMetrics:
    frozen = tuple(events)
    if not frozen:
        return AgentTrajectoryMetrics()

    by_type: dict[str, list[StoredAgentEvent]] = {}
    for event in frozen:
        by_type.setdefault(event.event_type, []).append(event)

    decision_events = by_type.get("decision_ready", [])
    tool_events = by_type.get("tool_call", [])
    observation_events = by_type.get("observation_ready", [])
    limit_events = by_type.get("react_limit_reached", [])

    iterations = [
        _safe_int(_event_payload(event).get("iteration"))
        for event in (*decision_events, *observation_events, *limit_events)
    ]
    tool_sequence = tuple(
        str(_event_payload(event).get("name", "") or "").strip()
        for event in tool_events
        if str(_event_payload(event).get("name", "") or "").strip()
    )

    fingerprints = [
        str(_event_payload(event).get("action_fingerprint", "") or "").strip()
        for event in decision_events
        if str(_event_payload(event).get("kind", "") or "") == "tool"
    ]
    seen: set[str] = set()
    redundant_action_count = 0
    for fingerprint in fingerprints:
        if not fingerprint:
            continue
        if fingerprint in seen:
            redundant_action_count += 1
        else:
            seen.add(fingerprint)

    evidence_count = max(
        [0]
        + [
            _safe_int(_event_payload(event).get("final_count"))
            for event in by_type.get("rag_evidence_selected", [])
        ]
        + [
            _safe_int(_event_payload(event).get("evidence_count"))
            for event in observation_events
        ]
    )
    citation_count = max(
        [0]
        + [
            _safe_int(_event_payload(event).get("citation_count"))
            for event in observation_events
        ]
    )
    grounded = evidence_count > 0 or any(
        _event_payload(event).get("grounded") is True
        for event in by_type.get("synthesis_ready", [])
    )

    knowledge_observations = [
        event
        for event in observation_events
        if str(_event_payload(event).get("tool_name", "") or "")
        == "search_knowledge_base"
    ]
    query_fingerprints = [
        str(_event_payload(event).get("query_fingerprint", "") or "").strip()
        for event in knowledge_observations
    ]
    query_reformulation_count = sum(
        bool(current and previous and current != previous)
        for previous, current in zip(query_fingerprints, query_fingerprints[1:])
    )
    novel_evidence_count = sum(
        _safe_int(_event_payload(event).get("novel_evidence_count"))
        for event in knowledge_observations
    )
    no_novel_evidence_search_count = sum(
        _safe_int(_event_payload(event).get("novel_evidence_count")) == 0
        for event in knowledge_observations
    )
    retrieval_fallback_count = sum(
        _event_payload(event).get("retrieval_fallback") is True
        for event in knowledge_observations
    )

    confirmation_required_actions = sum(
        str(_event_payload(event).get("effect", "") or "") == "write"
        and _event_payload(event).get("requires_confirmation") is True
        for event in tool_events
    )
    write_result_count = sum(
        str(_event_payload(event).get("effect", "") or "") == "write"
        for event in by_type.get("tool_result", [])
    )
    confirmation_guard_pass = not (
        write_result_count > 0 and confirmation_required_actions == 0
    )
    if _normalized(run_status) == "confirmation_required" and write_result_count > 0:
        confirmation_guard_pass = False

    limit_reason = ""
    if limit_events:
        limit_reason = str(
            _event_payload(limit_events[-1]).get("reason", "") or ""
        ).strip()

    return AgentTrajectoryMetrics(
        available=True,
        react_started=bool(by_type.get("react_started")),
        react_iteration_count=max(iterations, default=0),
        decision_count=len(decision_events),
        tool_call_count=len(tool_events),
        observation_count=len(observation_events),
        tool_sequence=tool_sequence,
        redundant_action_count=redundant_action_count,
        react_limit_reached=bool(limit_events),
        react_limit_reason=limit_reason,
        grounded=grounded,
        evidence_count=evidence_count,
        citation_count=citation_count,
        knowledge_search_count=len(knowledge_observations),
        query_reformulation_count=query_reformulation_count,
        novel_evidence_count=novel_evidence_count,
        no_novel_evidence_search_count=no_novel_evidence_search_count,
        retrieval_fallback_count=retrieval_fallback_count,
        confirmation_required_action_count=confirmation_required_actions,
        write_result_count=write_result_count,
        confirmation_guard_pass=confirmation_guard_pass,
    )


def evaluate_agent_run(
    run: StoredAgentRun,
    expectation: AgentEvaluationExpectation,
    *,
    events: Iterable[StoredAgentEvent] = (),
) -> AgentEvaluationResult:
    trajectory = derive_agent_trajectory_metrics(events, run_status=run.status)
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

    react_mode_pass = (
        expectation.expect_react is None
        or (
            trajectory.available
            and trajectory.react_started is expectation.expect_react
        )
    )
    normalized_expected_sequence = tuple(
        _normalized(item) for item in expectation.expected_tool_sequence if item
    )
    normalized_actual_sequence = tuple(_normalized(item) for item in trajectory.tool_sequence)
    tool_sequence_pass = (
        not normalized_expected_sequence
        or (
            trajectory.available
            and normalized_actual_sequence == normalized_expected_sequence
        )
    )
    react_iteration_pass = (
        expectation.max_react_iterations <= 0
        or (
            trajectory.available
            and trajectory.react_iteration_count <= expectation.max_react_iterations
        )
    )
    tool_call_pass = (
        expectation.max_tool_calls <= 0
        or (
            trajectory.available
            and trajectory.tool_call_count <= expectation.max_tool_calls
        )
    )
    redundancy_pass = (
        expectation.max_redundant_actions is None
        or (
            trajectory.available
            and trajectory.redundant_action_count
            <= max(0, expectation.max_redundant_actions)
        )
    )
    react_limit_pass = (
        not expectation.require_no_react_limit
        or (trajectory.available and not trajectory.react_limit_reached)
    )
    grounding_pass = (
        not expectation.require_grounded_response
        or (trajectory.available and trajectory.grounded)
    )
    confirmation_pass = (
        not expectation.require_confirmation_guard
        or (trajectory.available and trajectory.confirmation_guard_pass)
    )

    named_checks: list[tuple[str, bool]] = [
        ("intent", intent_match),
        ("tool", tool_match),
        ("status", status_match),
        ("latency", latency_pass),
        ("retry", retry_pass),
        ("failure", failure_pass),
    ]
    if expectation.expect_react is not None:
        named_checks.append(("react_mode", react_mode_pass))
    if normalized_expected_sequence:
        named_checks.append(("tool_sequence", tool_sequence_pass))
    if expectation.max_react_iterations > 0:
        named_checks.append(("react_iterations", react_iteration_pass))
    if expectation.max_tool_calls > 0:
        named_checks.append(("tool_calls", tool_call_pass))
    if expectation.max_redundant_actions is not None:
        named_checks.append(("redundancy", redundancy_pass))
    if expectation.require_no_react_limit:
        named_checks.append(("react_limit", react_limit_pass))
    if expectation.require_grounded_response:
        named_checks.append(("grounding", grounding_pass))
    if expectation.require_confirmation_guard:
        named_checks.append(("confirmation", confirmation_pass))

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
    if not react_mode_pass:
        failures.append(
            f"react expected={expectation.expect_react!r} actual={trajectory.react_started!r}"
        )
    if not tool_sequence_pass:
        failures.append(
            f"tool_sequence expected={normalized_expected_sequence!r} actual={normalized_actual_sequence!r}"
        )
    if not react_iteration_pass:
        failures.append(
            f"react_iterations max={expectation.max_react_iterations} actual={trajectory.react_iteration_count}"
        )
    if not tool_call_pass:
        failures.append(
            f"tool_calls max={expectation.max_tool_calls} actual={trajectory.tool_call_count}"
        )
    if not redundancy_pass:
        failures.append(
            f"redundant_actions max={expectation.max_redundant_actions} actual={trajectory.redundant_action_count}"
        )
    if not react_limit_pass:
        failures.append(
            f"react_limit reached reason={trajectory.react_limit_reason or 'unknown'}"
        )
    if not grounding_pass:
        failures.append("grounded response required but no persisted evidence was observed")
    if not confirmation_pass:
        failures.append("write confirmation guard was bypassed")

    score = round(
        sum(1 for _name, check in named_checks if check) / len(named_checks),
        4,
    )
    return AgentEvaluationResult(
        case_id=expectation.case_id,
        run_id=run.run_id,
        trace_id=run.trace_id,
        passed=all(check for _name, check in named_checks),
        score=score,
        intent_match=intent_match,
        tool_match=tool_match,
        status_match=status_match,
        latency_pass=latency_pass,
        retry_pass=retry_pass,
        failure_pass=failure_pass,
        react_mode_pass=react_mode_pass,
        tool_sequence_pass=tool_sequence_pass,
        react_iteration_pass=react_iteration_pass,
        tool_call_pass=tool_call_pass,
        redundancy_pass=redundancy_pass,
        react_limit_pass=react_limit_pass,
        grounding_pass=grounding_pass,
        confirmation_pass=confirmation_pass,
        trajectory=trajectory,
        failures=tuple(failures),
    )


__all__ = [
    "AgentEvaluationExpectation",
    "AgentEvaluationResult",
    "AgentTrajectoryMetrics",
    "derive_agent_trajectory_metrics",
    "evaluate_agent_run",
]
