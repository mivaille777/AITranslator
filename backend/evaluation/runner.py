from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from backend.evaluation.agent_evaluator import (
    AgentEvaluationExpectation,
    AgentEvaluationResult,
    evaluate_agent_run,
)
from backend.services.agent_trace_store_service import StoredAgentRun


@dataclass(frozen=True, slots=True)
class AgentEvaluationBatchResult:
    total_cases: int
    passed_cases: int
    pass_rate: float
    average_score: float
    results: tuple[AgentEvaluationResult, ...]


def evaluate_agent_batch(
    cases: Iterable[AgentEvaluationExpectation],
    *,
    resolve_run: Callable[[AgentEvaluationExpectation], StoredAgentRun | None],
) -> AgentEvaluationBatchResult:
    results: list[AgentEvaluationResult] = []
    for case in cases:
        run = resolve_run(case)
        if run is None:
            results.append(
                AgentEvaluationResult(
                    case_id=case.case_id,
                    run_id="",
                    trace_id="",
                    passed=False,
                    score=0.0,
                    intent_match=False,
                    tool_match=False,
                    status_match=False,
                    latency_pass=False,
                    retry_pass=False,
                    failure_pass=False,
                    failures=("no persisted run mapped to evaluation case",),
                )
            )
            continue
        results.append(evaluate_agent_run(run, case))

    total = len(results)
    passed = sum(result.passed for result in results)
    average_score = round(
        sum(result.score for result in results) / total,
        4,
    ) if total else 0.0
    return AgentEvaluationBatchResult(
        total_cases=total,
        passed_cases=passed,
        pass_rate=round(passed / total, 4) if total else 0.0,
        average_score=average_score,
        results=tuple(results),
    )


__all__ = ["AgentEvaluationBatchResult", "evaluate_agent_batch"]
