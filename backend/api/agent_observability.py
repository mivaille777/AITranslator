from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.agent_observability_dependencies import get_agent_trace_store_service
from backend.evaluation.agent_evaluator import AgentEvaluationExpectation, evaluate_agent_run
from backend.models.agent_observability import (
    AgentEvaluationRequest,
    AgentEvaluationResponse,
    AgentObservabilitySummaryResponse,
    AgentRecentRunsResponse,
    AgentRunMetric,
)
from backend.services.agent_trace_store_service import AgentTraceStoreService

router = APIRouter(prefix="/api/agent", tags=["agent-observability"])
AgentTraceStoreDependency = Annotated[
    AgentTraceStoreService,
    Depends(get_agent_trace_store_service),
]


@router.get(
    "/observability/recent",
    response_model=AgentRecentRunsResponse,
)
def list_recent_agent_runs(
    store: AgentTraceStoreDependency,
    limit: int = Query(default=20, ge=1, le=200),
) -> AgentRecentRunsResponse:
    return AgentRecentRunsResponse(
        runs=[AgentRunMetric(**asdict(run)) for run in store.list_recent(limit=limit)]
    )


@router.get(
    "/observability/summary",
    response_model=AgentObservabilitySummaryResponse,
)
def get_agent_observability_summary(
    store: AgentTraceStoreDependency,
    limit: int = Query(default=100, ge=1, le=500),
) -> AgentObservabilitySummaryResponse:
    summary = asdict(store.summary(limit=limit))
    runs = store.list_recent(limit=limit)
    schema_valid_count = sum(bool(run.intent.strip()) for run in runs)
    summary["schema_valid_rate"] = (
        round(schema_valid_count / len(runs), 4) if runs else 0.0
    )
    return AgentObservabilitySummaryResponse(**summary)


@router.post(
    "/evaluation/run/{run_id}",
    response_model=AgentEvaluationResponse,
)
def evaluate_persisted_agent_run(
    run_id: str,
    payload: AgentEvaluationRequest,
    store: AgentTraceStoreDependency,
) -> AgentEvaluationResponse:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent run not found: {run_id}",
        )

    result = evaluate_agent_run(
        run,
        AgentEvaluationExpectation(
            case_id=payload.case_id,
            expected_intent=payload.expected_intent,
            expected_tool_name=payload.expected_tool_name,
            expected_status=payload.expected_status,
            max_total_duration_ms=payload.max_total_duration_ms,
            max_retry_count=payload.max_retry_count,
            require_zero_failures=payload.require_zero_failures,
        ),
    )
    return AgentEvaluationResponse(
        case_id=result.case_id,
        run_id=result.run_id,
        trace_id=result.trace_id,
        passed=result.passed,
        score=result.score,
        intent_match=result.intent_match,
        tool_match=result.tool_match,
        status_match=result.status_match,
        latency_pass=result.latency_pass,
        retry_pass=result.retry_pass,
        failure_pass=result.failure_pass,
        failures=list(result.failures),
    )


__all__ = ["router"]