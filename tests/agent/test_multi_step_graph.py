from __future__ import annotations

from types import SimpleNamespace

from backend.agent_core.events import AgentEventType
from backend.agent_core.product_adapter import ProductAgentRuntimeAdapter
from backend.agent_core.runtime import AgentRuntime
from backend.agent_core.state import AgentState
from backend.agent_graph.reading_agent_graph import ReadingAgentGraph
from backend.models.agent_runtime import (
    AgentPlanContext,
    AgentPlanStep,
    AgentRouteDecision,
)
from backend.models.agent_tools import AgentPlan
from backend.services.agent_tool_registry import AgentToolExecutionResult


class FakeComplexProductAgentService:
    def __init__(self) -> None:
        self.route_calls = 0
        self.plan_calls = 0
        self.step_tools: list[str] = []
        self.synthesis_calls = 0

    def resolve_route(self, *, control=None, **_payload):
        self.route_calls += 1
        return (
            AgentRouteDecision(
                kind="complex",
                source="semantic_router",
                intent="complex",
                user_visible_reason="This request combines multiple reading actions.",
            ),
            {
                "duration_ms": 1,
                "provider": "",
                "model": "",
                "prompt_id": "",
                "llm_called": False,
            },
        )

    def plan_multi_step(self, *, control=None, **_payload):
        self.plan_calls += 1
        return (
            AgentPlanContext(
                goal="Translate and explain the selection.",
                mode="multi_step",
                steps=[
                    AgentPlanStep(
                        step_id="step-1",
                        tool_name="translate_selection",
                        arguments={"target_language": "zh-CN"},
                    ),
                    AgentPlanStep(
                        step_id="step-2",
                        tool_name="explain_selection",
                        depends_on=["step-1"],
                    ),
                ],
                current_step_id="step-1",
            ),
            {
                "duration_ms": 2,
                "provider": "fake-planner",
                "model": "fake-planner-model",
                "prompt_id": "agent.multi_step_planner@test",
                "llm_called": True,
            },
        )

    def run(self, *, event_sink=None, control=None, **payload):
        route = AgentRouteDecision.model_validate(payload["_resolved_route"])
        tool_name = route.tool_name
        self.step_tools.append(tool_name)
        if event_sink is not None:
            event_sink(
                "tool_call",
                {
                    "name": tool_name,
                    "arguments": dict(route.arguments),
                    "effect": "compute",
                    "request_id": payload.get("request_id", 0),
                },
            )
        result = AgentToolExecutionResult(
            tool_name=tool_name,
            output_text=f"result:{tool_name}",
            effect="compute",
            provider="fake-tool",
            model="fake-tool-model",
            request_id=payload.get("request_id", 0),
            data={"step_tool": tool_name},
        )
        if event_sink is not None:
            event_sink(
                "tool_result",
                {
                    "tool_name": tool_name,
                    "output_text": result.output_text,
                    "effect": "compute",
                    "provider": result.provider,
                    "model": result.model,
                    "request_id": result.request_id,
                    "data": result.data,
                },
            )
        return SimpleNamespace(
            status="completed",
            plan=AgentPlan(
                action="tool",
                tool_name=tool_name,
                user_visible_reason=f"Execute {tool_name}.",
                arguments=dict(route.arguments),
            ),
            output_text=result.output_text,
            provider=result.provider,
            model=result.model,
            request_id=result.request_id,
            tool_result=result,
            route=route,
        )

    def synthesize_multi_step(
        self,
        *,
        tool_results,
        event_sink=None,
        control=None,
        **payload,
    ):
        self.synthesis_calls += 1
        assert [item["tool_name"] for item in tool_results] == [
            "translate_selection",
            "explain_selection",
        ]
        if event_sink is not None:
            event_sink(
                "synthesis_ready",
                {
                    "provider": "fake-chat",
                    "model": "fake-chat-model",
                    "request_id": payload.get("request_id", 0),
                    "duration_ms": 3,
                },
            )
        return SimpleNamespace(
            status="completed",
            plan=AgentPlan(
                action="answer",
                user_visible_reason="Synthesize completed plan.",
            ),
            output_text="final multi-step answer",
            provider="fake-chat",
            model="fake-chat-model",
            request_id=payload.get("request_id", 0),
            tool_result=None,
            route=AgentRouteDecision(
                kind="complex",
                source="planner",
                intent="complex",
                user_visible_reason="Completed multi-step plan.",
            ),
        )


def _state() -> AgentState:
    return AgentState(
        session_id="multi-step-session",
        user_input="先翻译，然后解释一下",
        selected_text="Gaussian processes model uncertainty.",
        browser_context={
            "source_language": "en",
            "target_language": "zh-CN",
            "resource_title": "Paper",
            "source_kind": "pdf",
            "request_id": 41,
        },
    )


def test_reading_agent_graph_executes_bounded_multi_step_plan_and_synthesizes_once() -> None:
    service = FakeComplexProductAgentService()
    runtime = AgentRuntime(
        context_provider=lambda state: dict(state.browser_context),
        workflow_adapter=ReadingAgentGraph(ProductAgentRuntimeAdapter(service)),
    )

    result = runtime.execute(_state())

    assert service.route_calls == 1
    assert service.plan_calls == 1
    assert service.step_tools == ["translate_selection", "explain_selection"]
    assert service.synthesis_calls == 1
    assert result.route.kind == "complex"
    assert result.plan.mode == "multi_step"
    assert [step.status for step in result.plan.steps] == ["completed", "completed"]
    assert [item["step_id"] for item in result.tool_results] == ["step-1", "step-2"]
    assert result.response["status"] == "completed"
    assert result.response["output_text"] == "final multi-step answer"
    assert [event.event_type for event in runtime.events] == [
        AgentEventType.AGENT_START,
        AgentEventType.CONTEXT_READY,
        AgentEventType.PLAN_READY,
        AgentEventType.TOOL_CALL,
        AgentEventType.TOOL_RESULT,
        AgentEventType.TOOL_CALL,
        AgentEventType.TOOL_RESULT,
        AgentEventType.SYNTHESIS_READY,
        AgentEventType.AGENT_END,
    ]


def test_multi_step_plan_survives_legacy_tool_state_synchronization() -> None:
    state = _state()
    state.apply_route(
        AgentRouteDecision(
            kind="complex",
            source="semantic_router",
            intent="complex",
        )
    )
    state.apply_multi_step_plan(
        AgentPlanContext(
            goal="Translate and explain.",
            mode="multi_step",
            steps=[
                AgentPlanStep(step_id="step-1", tool_name="translate_selection"),
                AgentPlanStep(
                    step_id="step-2",
                    tool_name="explain_selection",
                    depends_on=["step-1"],
                ),
            ],
            current_step_id="step-1",
        )
    )

    state.record_tool_call({"name": "translate_selection", "step_id": "step-1"})
    state.record_tool_result(
        {
            "tool_name": "translate_selection",
            "output_text": "结果",
            "effect": "compute",
            "step_id": "step-1",
        }
    )

    assert state.route.kind == "complex"
    assert state.plan.mode == "multi_step"
    assert [step.tool_name for step in state.plan.steps] == [
        "translate_selection",
        "explain_selection",
    ]
