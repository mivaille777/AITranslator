from backend.agent_core.events import AgentEventType
from backend.agent_core.runtime import AgentRuntime
from backend.agent_core.state import AgentState


def test_agent_runtime_flow():
    runtime = AgentRuntime(
        context_provider=lambda state: {"source": "browser"},
        planner=lambda state: {"intent": "translate"},
        tool_executor=lambda state: {"translation": "ok"},
    )

    result = runtime.execute(AgentState(user_input="hello"))

    assert result.browser_context["source"] == "browser"
    assert result.intent == "translate"
    assert result.tool_results[0]["translation"] == "ok"
    assert [event.event_type for event in runtime.events] == [
        AgentEventType.AGENT_START,
        AgentEventType.CONTEXT_READY,
        AgentEventType.PLAN_READY,
        AgentEventType.TOOL_CALL,
        AgentEventType.TOOL_RESULT,
        AgentEventType.AGENT_END,
    ]
