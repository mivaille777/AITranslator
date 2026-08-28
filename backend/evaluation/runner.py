from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from backend.evaluation.agent_evaluator import (
    AgentEvaluationExpectation,
    AgentEvaluationResult,
    AgentTrajectoryMetrics,
    evaluate_agent_run,
)
from backend.services.agent_trace_store_service import StoredAgentEvent, StoredAgentRun


@dataclass(frozen=True, slots=True)
class AgentEvaluationBatchResult:
    total_cases: int
    passed_cases: int
    pass_rate: float
    average_score: float
    intent_accuracy: float
    tool_accuracy: float
    status_accuracy: float
    fallback_accuracy: float
    evidence_gate_accuracy: float
    latency_pass_rate: float
    retry_pass_rate: float
    failure_pass_rate: float
    trajectory_case_count: int
    react_run_rate: float
    average_react_iterations: float
    average_tool_calls: float
    average_knowledge_searches: float
    average_query_reformulations: float
    average_novel_evidence: float
    no_novel_evidence_run_rate: float
    retrieval_fallback_run_rate: float
    redundant_action_rate: float
    react_limit_rate: float
    grounded_rate: float
    grounding_verification_run_rate: float
    grounding_verification_pass_rate: float
    grounding_verification_fallback_rate: float
    average_citation_coverage: float
    average_claim_support_rate: float
    invalid_citation_run_rate: float
    unsupported_claim_run_rate: float
    confirmation_guard_rate: float
    results: tuple[AgentEvaluationResult, ...]


def _missing_result(case: AgentEvaluationExpectation) -> AgentEvaluationResult:
    return AgentEvaluationResult(
        case_id=case.case_id,
        run_id="",
        trace_id="",
        passed=False,
        score=0.0,
        intent_match=False,
        tool_match=False,
        status_match=False,
        fallback_match=False,
        latency_pass=False,
        retry_pass=False,
        failure_pass=False,
        react_mode_pass=False,
        tool_sequence_pass=False,
        react_iteration_pass=False,
        tool_call_pass=False,
        redundancy_pass=False,
        react_limit_pass=False,
        grounding_pass=False,
        evidence_gate_pass=False,
        grounding_verification_pass=False,
        confirmation_pass=False,
        trajectory=AgentTrajectoryMetrics(),
        failures=("no persisted run mapped to evaluation case",),
    )


def evaluate_agent_batch(
    cases: Iterable[AgentEvaluationExpectation],
    *,
    resolve_run: Callable[[AgentEvaluationExpectation], StoredAgentRun | None],
    resolve_events: Callable[[StoredAgentRun], Iterable[StoredAgentEvent]] | None = None,
) -> AgentEvaluationBatchResult:
    results: list[AgentEvaluationResult] = []
    for case in cases:
        run = resolve_run(case)
        if run is None:
            results.append(_missing_result(case))
            continue
        events = tuple(resolve_events(run)) if resolve_events is not None else ()
        results.append(evaluate_agent_run(run, case, events=events))

    total = len(results)
    passed = sum(result.passed for result in results)

    def rate(predicate: Callable[[AgentEvaluationResult], bool]) -> float:
        return round(sum(predicate(result) for result in results) / total, 4) if total else 0.0

    average_score = (
        round(sum(result.score for result in results) / total, 4) if total else 0.0
    )
    trajectories = [result.trajectory for result in results if result.trajectory.available]
    trajectory_count = len(trajectories)
    verified_trajectories = [
        item for item in trajectories if item.grounding_verification_count > 0
    ]
    verified_count = len(verified_trajectories)

    def trajectory_rate(predicate: Callable[[AgentTrajectoryMetrics], bool]) -> float:
        if not trajectory_count:
            return 0.0
        return round(sum(predicate(item) for item in trajectories) / trajectory_count, 4)

    def trajectory_average(
        value: Callable[[AgentTrajectoryMetrics], int | float]
    ) -> float:
        if not trajectory_count:
            return 0.0
        return round(sum(value(item) for item in trajectories) / trajectory_count, 2)

    def verified_rate(predicate: Callable[[AgentTrajectoryMetrics], bool]) -> float:
        if not verified_count:
            return 0.0
        return round(
            sum(predicate(item) for item in verified_trajectories) / verified_count,
            4,
        )

    def verified_average(
        value: Callable[[AgentTrajectoryMetrics], int | float]
    ) -> float:
        if not verified_count:
            return 0.0
        return round(
            sum(value(item) for item in verified_trajectories) / verified_count,
            4,
        )

    return AgentEvaluationBatchResult(
        total_cases=total,
        passed_cases=passed,
        pass_rate=round(passed / total, 4) if total else 0.0,
        average_score=average_score,
        intent_accuracy=rate(lambda result: result.intent_match),
        tool_accuracy=rate(lambda result: result.tool_match),
        status_accuracy=rate(lambda result: result.status_match),
        fallback_accuracy=rate(lambda result: result.fallback_match),
        evidence_gate_accuracy=rate(lambda result: result.evidence_gate_pass),
        latency_pass_rate=rate(lambda result: result.latency_pass),
        retry_pass_rate=rate(lambda result: result.retry_pass),
        failure_pass_rate=rate(lambda result: result.failure_pass),
        trajectory_case_count=trajectory_count,
        react_run_rate=trajectory_rate(lambda item: item.react_started),
        average_react_iterations=trajectory_average(
            lambda item: item.react_iteration_count
        ),
        average_tool_calls=trajectory_average(lambda item: item.tool_call_count),
        average_knowledge_searches=trajectory_average(
            lambda item: item.knowledge_search_count
        ),
        average_query_reformulations=trajectory_average(
            lambda item: item.query_reformulation_count
        ),
        average_novel_evidence=trajectory_average(
            lambda item: item.novel_evidence_count
        ),
        no_novel_evidence_run_rate=trajectory_rate(
            lambda item: item.no_novel_evidence_search_count > 0
        ),
        retrieval_fallback_run_rate=trajectory_rate(
            lambda item: item.retrieval_fallback_count > 0
        ),
        redundant_action_rate=trajectory_rate(
            lambda item: item.redundant_action_count > 0
        ),
        react_limit_rate=trajectory_rate(lambda item: item.react_limit_reached),
        grounded_rate=trajectory_rate(lambda item: item.grounded),
        grounding_verification_run_rate=(
            round(verified_count / trajectory_count, 4) if trajectory_count else 0.0
        ),
        grounding_verification_pass_rate=verified_rate(
            lambda item: item.final_grounding_verification_passed is True
        ),
        grounding_verification_fallback_rate=verified_rate(
            lambda item: item.grounding_verification_fallback_count > 0
        ),
        average_citation_coverage=verified_average(
            lambda item: item.average_citation_coverage
        ),
        average_claim_support_rate=verified_average(
            lambda item: item.average_claim_support_rate
        ),
        invalid_citation_run_rate=verified_rate(
            lambda item: item.invalid_citation_count > 0
        ),
        unsupported_claim_run_rate=verified_rate(
            lambda item: item.unsupported_claim_count > 0
        ),
        confirmation_guard_rate=trajectory_rate(
            lambda item: item.confirmation_guard_pass
        ),
        results=tuple(results),
    )


__all__ = ["AgentEvaluationBatchResult", "evaluate_agent_batch"]
