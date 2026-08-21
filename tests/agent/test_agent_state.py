from backend.agent_core.state import AgentState


def test_agent_state_serialization():
    state = AgentState(user_input="translate this")

    payload = state.model_dump()

    assert payload["user_input"] == "translate this"
    assert "tool_results" in payload
