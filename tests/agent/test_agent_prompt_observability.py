from __future__ import annotations

from backend.agent_core.events import AgentEvent, AgentEventType
from backend.agent_core.state import AgentState
from backend.services.agent_trace_store_service import AgentTraceStoreService


def test_observability_persists_prompt_ids_and_route_metadata_without_prompt_text(tmp_path) -> None:
    store = AgentTraceStoreService(storage_path=tmp_path / "agent-observability.sqlite3")
    state = AgentState(
        session_id="session-prompt",
        user_input="private user request",
        selected_text="private selected source text",
        intent="translate_selection",
        response={"status": "completed", "provider": "deepseek", "model": "deepseek-v4-pro"},
        ui_mode="translation",
    )
    events = (
        AgentEvent(
            event_type=AgentEventType.AGENT_START,
            run_id=state.run_id,
            trace_id=state.trace_id,
            payload={"budget_ms": 45000, "user_message": "must not persist"},
        ),
        AgentEvent(
            event_type=AgentEventType.PLAN_READY,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=10,
            payload={
                "action": "tool",
                "tool_name": "translate_selection",
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "prompt_id": "agent.planner@1.1.0",
                "duration_ms": 10,
                "source_text": "must not persist",
            },
        ),
        AgentEvent(
            event_type=AgentEventType.SYNTHESIS_READY,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=30,
            payload={
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "prompt_id": "chat.reading@1.1.0",
                "duration_ms": 20,
                "output_text": "must not persist",
            },
        ),
        AgentEvent(
            event_type=AgentEventType.AGENT_END,
            run_id=state.run_id,
            trace_id=state.trace_id,
            elapsed_ms=35,
            payload={
                "intent": "translate_selection",
                "status": "completed",
                "ui_mode": "translation",
                "total_duration_ms": 35,
            },
        ),
    )

    store.record(state, events)
    payloads = store.event_payloads(state.run_id)

    assert payloads[1]["prompt_id"] == "agent.planner@1.1.0"
    assert payloads[1]["model"] == "deepseek-v4-flash"
    assert payloads[2]["prompt_id"] == "chat.reading@1.1.0"
    assert payloads[2]["model"] == "deepseek-v4-pro"
    serialized = str(payloads)
    assert "private selected source text" not in serialized
    assert "private user request" not in serialized
    assert "must not persist" not in serialized
