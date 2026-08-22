from __future__ import annotations

from dataclasses import asdict

from fastapi.testclient import TestClient

from backend.agent_core.events import AgentEvent, AgentEventType
from backend.agent_core.runtime import AgentRuntime
from backend.agent_core.state import AgentState
from backend.api.agent_observability_dependencies import get_agent_trace_store_service
from backend.evaluation.agent_evaluator import AgentEvaluationExpectation, evaluate_agent_run
from backend.main import create_app
from backend.services.agent_trace_store_service import AgentTraceStoreService


def completed_trace(state: AgentState) -> tuple[AgentEvent, ...]:
    return (
        AgentEvent(
            event_type=AgentEventType.AGENT_START,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=0,
            payload={"session_id": state.session_id, "budget_ms": 45000},
        ),
        AgentEvent(
            event_type=AgentEventType.CONTEXT_READY,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=4,
            payload={
                "source_kind": "browser_selection",
                "source_text": "PRIVATE SOURCE TEXT",
                "context_before": "PRIVATE CONTEXT",
            },
        ),
        AgentEvent(
            event_type=AgentEventType.PLAN_READY,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=20,
            payload={
                "action": "tool",
                "tool_name": "translate_selection",
                "request_id": 7,
                "duration_ms": 16,
                "user_visible_reason": "PRIVATE REASON",
            },
        ),
        AgentEvent(
            event_type=AgentEventType.TOOL_CALL,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=21,
            payload={"name": "translate_selection", "effect": "compute", "request_id": 7},
        ),
        AgentEvent(
            event_type=AgentEventType.RETRY,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=40,
            payload={
                "tool_name": "translate_selection",
                "attempt": 2,
                "max_attempts": 2,
                "reason": "PRIVATE PROVIDER ERROR BODY",
                "request_id": 7,
            },
        ),
        AgentEvent(
            event_type=AgentEventType.TOOL_RESULT,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=70,
            payload={
                "tool_name": "translate_selection",
                "effect": "compute",
                "provider": "stub",
                "model": "stub-model",
                "request_id": 7,
                "duration_ms": 49,
                "output_text": "PRIVATE MODEL OUTPUT",
            },
        ),
        AgentEvent(
            event_type=AgentEventType.SYNTHESIS_READY,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=90,
            payload={
                "provider": "stub",
                "model": "stub-model",
                "request_id": 7,
                "duration_ms": 20,
            },
        ),
        AgentEvent(
            event_type=AgentEventType.AGENT_END,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=92,
            payload={
                "intent": "translate_selection",
                "status": "completed",
                "ui_mode": "translation",
                "total_duration_ms": 92,
            },
        ),
    )


def test_trace_store_persists_redacted_metrics_only(tmp_path) -> None:
    store = AgentTraceStoreService(storage_path=tmp_path / "agent.sqlite3")
    state = AgentState(
        session_id="session-1",
        user_input="PRIVATE USER MESSAGE",
        selected_text="PRIVATE SOURCE TEXT",
        intent="translate_selection",
        ui_mode="translation",
        response={"status": "completed", "provider": "stub", "model": "stub-model"},
    )

    stored = store.record(state, completed_trace(state))

    assert stored.status == "completed"
    assert stored.tool_name == "translate_selection"
    assert stored.retry_count == 1
    assert stored.total_duration_ms == 92
    assert stored.planning_duration_ms == 16
    assert stored.tool_duration_ms == 49
    assert stored.synthesis_duration_ms == 20

    payloads = store.event_payloads(state.run_id)
    serialized = repr(payloads)
    assert "PRIVATE SOURCE TEXT" not in serialized
    assert "PRIVATE CONTEXT" not in serialized
    assert "PRIVATE MODEL OUTPUT" not in serialized
    assert "PRIVATE USER MESSAGE" not in serialized
    assert "PRIVATE PROVIDER ERROR BODY" not in serialized


def test_observability_summary_aggregates_recent_runs(tmp_path) -> None:
    store = AgentTraceStoreService(storage_path=tmp_path / "agent.sqlite3")
    first = AgentState(session_id="s1", intent="translate_selection", ui_mode="translation")
    second = AgentState(session_id="s2", intent="translate_selection", ui_mode="translation")
    store.record(first, completed_trace(first))

    failed_events = list(completed_trace(second))
    failed_events[-1] = AgentEvent(
        event_type=AgentEventType.AGENT_END,
        run_id=second.run_id,
        trace_id=second.trace_id,
        elapsed_ms=120,
        payload={
            "intent": "translate_selection",
            "status": "failed",
            "ui_mode": "translation",
            "total_duration_ms": 120,
        },
    )
    failed_events.insert(
        -1,
        AgentEvent(
            event_type=AgentEventType.FAILURE,
            run_id=second.run_id,
            trace_id=second.trace_id,
            elapsed_ms=118,
            payload={
                "code": "AgentToolTimeoutError",
                "stage": "tool",
                "fallback_reason": "tool_timeout_after_safe_retries",
            },
        ),
    )
    store.record(second, failed_events)

    summary = store.summary(limit=10)

    assert summary.sample_size == 2
    assert summary.completed_runs == 1
    assert summary.failed_runs == 1
    assert summary.success_rate == 0.5
    assert summary.failure_rate == 0.5
    assert summary.timeout_rate == 0.5
    assert summary.fallback_rate == 0.5
    assert summary.p95_total_duration_ms == 120


def test_evaluator_scores_persisted_run_deterministically(tmp_path) -> None:
    store = AgentTraceStoreService(storage_path=tmp_path / "agent.sqlite3")
    state = AgentState(session_id="s1", intent="translate_selection", ui_mode="translation")
    run = store.record(state, completed_trace(state))

    result = evaluate_agent_run(
        run,
        AgentEvaluationExpectation(
            case_id="translate",
            expected_intent="translate_selection",
            expected_tool_name="translate_selection",
            expected_status="completed",
            max_total_duration_ms=100,
            max_retry_count=1,
        ),
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.failures == ()


def test_runtime_recorder_failure_does_not_change_agent_result() -> None:
    def broken_recorder(_state: AgentState, _events: tuple[AgentEvent, ...]) -> None:
        raise OSError("disk unavailable")

    runtime = AgentRuntime(
        planner=lambda _state: {"intent": "answer"},
        run_recorder=broken_recorder,
    )

    result = runtime.execute(AgentState(user_input="hello"))

    assert result.intent == "answer"
    assert runtime.events[-1].event_type == AgentEventType.AGENT_END


def test_observability_http_endpoints_and_run_evaluation(tmp_path) -> None:
    store = AgentTraceStoreService(storage_path=tmp_path / "agent.sqlite3")
    state = AgentState(session_id="s1", intent="translate_selection", ui_mode="translation")
    run = store.record(state, completed_trace(state))

    app = create_app()
    app.dependency_overrides[get_agent_trace_store_service] = lambda: store
    client = TestClient(app)

    recent = client.get("/api/agent/observability/recent?limit=5")
    assert recent.status_code == 200
    assert recent.json()["runs"][0]["run_id"] == run.run_id

    summary = client.get("/api/agent/observability/summary?limit=5")
    assert summary.status_code == 200
    assert summary.json()["sample_size"] == 1
    assert summary.json()["success_rate"] == 1.0

    evaluation = client.post(
        f"/api/agent/evaluation/run/{run.run_id}",
        json={
            "case_id": "translate",
            "expected_intent": "translate_selection",
            "expected_tool_name": "translate_selection",
            "expected_status": "completed",
            "max_total_duration_ms": 100,
            "max_retry_count": 1,
        },
    )
    assert evaluation.status_code == 200
    assert evaluation.json()["passed"] is True
    assert evaluation.json()["score"] == 1.0
