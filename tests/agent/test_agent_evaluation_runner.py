from __future__ import annotations

from backend.evaluation.agent_evaluator import AgentEvaluationExpectation
from backend.evaluation.runner import evaluate_agent_batch
from backend.services.agent_trace_store_service import StoredAgentRun


def stored_run(*, run_id: str, intent: str, tool_name: str, status: str) -> StoredAgentRun:
    return StoredAgentRun(
        run_id=run_id,
        trace_id=f"trace-{run_id}",
        session_id="session",
        created_at="2026-08-22T00:00:00+00:00",
        status=status,
        intent=intent,
        ui_mode="assistant",
        tool_name=tool_name,
        provider="stub",
        model="stub-model",
        total_duration_ms=100,
        planning_duration_ms=20,
        tool_duration_ms=30,
        synthesis_duration_ms=50,
        retry_count=0,
        failure_count=0,
        timeout_count=0,
        fallback_reason="",
        event_count=6,
    )


def test_agent_evaluation_batch_reports_pass_rate_and_missing_run() -> None:
    cases = (
        AgentEvaluationExpectation(
            case_id="translate",
            expected_intent="translate_selection",
            expected_tool_name="translate_selection",
        ),
        AgentEvaluationExpectation(
            case_id="missing",
            expected_intent="explain_selection",
            expected_tool_name="explain_selection",
        ),
    )
    runs = {
        "translate": stored_run(
            run_id="run-1",
            intent="translate_selection",
            tool_name="translate_selection",
            status="completed",
        )
    }

    result = evaluate_agent_batch(cases, resolve_run=lambda case: runs.get(case.case_id))

    assert result.total_cases == 2
    assert result.passed_cases == 1
    assert result.pass_rate == 0.5
    assert result.average_score == 0.5
    assert result.results[1].passed is False
    assert "no persisted run" in result.results[1].failures[0]
