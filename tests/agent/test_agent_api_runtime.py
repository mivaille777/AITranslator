from __future__ import annotations

from backend.agent_core.state import AgentState
from backend.api.agent import run_product_agent
from backend.api.agent_dependencies import get_agent_runtime
from backend.models.agent_tools import AgentRunRequest


class FakeRuntime:
    def __init__(self, *, confirmation_required: bool = False) -> None:
        self.confirmation_required = confirmation_required
        self.received: AgentState | None = None

    def execute(self, state: AgentState) -> AgentState:
        self.received = state
        if self.confirmation_required:
            state.planned_action = {
                "action": "tool",
                "tool_name": "save_research_note",
                "user_visible_reason": "Save the selected passage as a note.",
                "arguments": {"user_note": "important"},
            }
            state.intent = "save_research_note"
            state.tool_calls.append(
                {
                    "name": "save_research_note",
                    "arguments": {"user_note": "important"},
                }
            )
            state.response = {
                "status": "confirmation_required",
                "output_text": "",
                "provider": "",
                "model": "",
                "request_id": 12,
            }
            state.ui_mode = "note"
            return state

        state.planned_action = {
            "action": "tool",
            "tool_name": "translate_selection",
            "user_visible_reason": "Translate the selected passage.",
            "arguments": {"target_language": "zh-CN"},
        }
        state.intent = "translate_selection"
        state.tool_calls.append(
            {
                "name": "translate_selection",
                "arguments": {"target_language": "zh-CN"},
            }
        )
        state.tool_results.append(
            {
                "tool_name": "translate_selection",
                "output_text": "贝叶斯优化",
                "effect": "compute",
                "provider": "fake",
                "model": "",
                "request_id": 12,
                "data": {
                    "source_language": "en",
                    "target_language": "zh-CN",
                },
            }
        )
        state.response = {
            "status": "completed",
            "output_text": "贝叶斯优化",
            "provider": "fake",
            "model": "",
            "request_id": 12,
        }
        state.ui_mode = "translation"
        return state


def _request() -> AgentRunRequest:
    return AgentRunRequest(
        session_id="session-12",
        user_message="Translate this selection",
        source_text="Bayesian optimization",
        source_language="en",
        target_language="zh-CN",
        resource_title="Paper",
        section_heading="Method",
        context_before="We tune the controller with",
        context_after="under bounded evaluations.",
        source_kind="browser_selection",
        style="academic",
        conversation_id="conversation-7",
        request_id=12,
    )


def test_agent_run_api_preserves_existing_response_contract_through_runtime() -> None:
    runtime = FakeRuntime()

    response = run_product_agent(_request(), runtime)

    assert runtime.received is not None
    assert runtime.received.session_id == "session-12"
    assert runtime.received.user_input == "Translate this selection"
    assert runtime.received.selected_text == "Bayesian optimization"
    assert runtime.received.browser_context["resource_title"] == "Paper"
    assert runtime.received.browser_context["conversation_id"] == "conversation-7"
    assert runtime.received.browser_context["request_id"] == 12

    assert response.status == "completed"
    assert response.plan.tool_name == "translate_selection"
    assert response.output_text == "贝叶斯优化"
    assert response.provider == "fake"
    assert response.request_id == 12
    assert response.tool_result is not None
    assert response.tool_result.tool_name == "translate_selection"
    assert response.tool_result.data["target_language"] == "zh-CN"


def test_agent_run_api_preserves_write_confirmation_gate() -> None:
    runtime = FakeRuntime(confirmation_required=True)

    response = run_product_agent(_request(), runtime)

    assert response.status == "confirmation_required"
    assert response.plan.tool_name == "save_research_note"
    assert response.tool_result is None
    assert runtime.received is not None
    assert runtime.received.tool_results == []


class FakeProductAgentService:
    pass


class FakeReadingSelectionResolver:
    pass


def test_agent_runtime_dependency_is_request_scoped() -> None:
    service = FakeProductAgentService()
    resolver = FakeReadingSelectionResolver()

    first = get_agent_runtime(service, resolver)
    second = get_agent_runtime(service, resolver)

    assert first is not second
    assert first.events == []
    assert second.events == []
