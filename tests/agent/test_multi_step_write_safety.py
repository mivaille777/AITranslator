from __future__ import annotations

from types import SimpleNamespace

from backend.agent_core.product_adapter import ProductAgentRuntimeAdapter
from backend.agent_core.runtime import AgentRuntime
from backend.agent_core.state import AgentState
from backend.agent_graph.reading_agent_graph import ReadingAgentGraph
from backend.models.agent_runtime import AgentPlanContext, AgentPlanStep
from backend.services.agent_router_service import AgentSemanticRouterService
from backend.services.agent_tool_registry import AgentToolExecutionResult, AgentToolSpec
from backend.services.product_agent_service import ProductAgentService


TRANSLATE_TOOL = AgentToolSpec(
    name="translate_selection",
    title="Translate",
    description="Translate selection",
    category="translation",
    effect="compute",
    requires_reading_context=True,
    requires_confirmation=False,
    input_schema={},
)
SAVE_TOOL = AgentToolSpec(
    name="save_research_note",
    title="Save note",
    description="Save selection",
    category="research",
    effect="write",
    requires_reading_context=True,
    requires_confirmation=True,
    input_schema={"user_note": {"type": "string", "maxLength": 4000}},
)


class FakeRegistry:
    def __init__(self) -> None:
        self.executions: list[str] = []
        self.tools = (TRANSLATE_TOOL, SAVE_TOOL)

    def list_tools(self):
        return self.tools

    def get_tool(self, name: str):
        return next((tool for tool in self.tools if tool.name == name), None)

    def validate_planner_arguments(self, name: str, arguments: dict):
        spec = self.get_tool(name)
        if spec is None:
            raise KeyError(name)
        return spec.validate_planner_arguments(arguments)

    def allows_safe_retry(self, name: str) -> bool:
        spec = self.get_tool(name)
        return bool(spec and spec.effect != "write")

    def execute(self, name: str, **payload):
        self.executions.append(name)
        spec = self.get_tool(name)
        assert spec is not None
        return AgentToolExecutionResult(
            tool_name=name,
            output_text=f"tool:{name}",
            effect=spec.effect,
            provider="fake-tool",
            model="fake-model",
            request_id=payload.get("request_id", 0),
            data={},
        )


class NeverSingleStepPlanner:
    provider_name = "never"
    model = "never"
    prompt_id = "never@test"

    def plan(self, **_kwargs):
        raise AssertionError("Compound request should not use the single-step planner.")


class FakeMultiStepPlanner:
    provider_name = "fake-planner"
    model = "fake-model"
    prompt_id = "agent.multi_step_planner@test"

    def plan(self, **_kwargs):
        return AgentPlanContext(
            goal="Translate and save the selection.",
            mode="multi_step",
            steps=[
                AgentPlanStep(step_id="step-1", tool_name="translate_selection"),
                AgentPlanStep(
                    step_id="step-2",
                    tool_name="save_research_note",
                    arguments={"user_note": "Keep this"},
                    depends_on=["step-1"],
                ),
            ],
            current_step_id="step-1",
        )


class FakeChatService:
    prompt_id = "chat@test"

    def __init__(self) -> None:
        self.calls = 0

    def send(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(
            output_text="unexpected synthesis",
            provider="fake-chat",
            model="fake-chat",
            request_id=0,
        )


def _runtime(registry: FakeRegistry, chat: FakeChatService) -> AgentRuntime:
    service = ProductAgentService(
        registry=registry,
        chat_service=chat,
        semantic_router=AgentSemanticRouterService(planner=NeverSingleStepPlanner()),
        multi_step_planner=FakeMultiStepPlanner(),
    )
    return AgentRuntime(
        workflow_adapter=ReadingAgentGraph(ProductAgentRuntimeAdapter(service)),
    )


def _state(*, confirmed: bool = False) -> AgentState:
    return AgentState(
        session_id="write-safety",
        user_input="先翻译，然后保存成笔记",
        selected_text="Gaussian Process",
        browser_context={
            "request_id": 51,
            "confirmed_write_tools": ["save_research_note"] if confirmed else [],
        },
    )


def test_multi_step_write_stops_for_confirmation_before_side_effect() -> None:
    registry = FakeRegistry()
    chat = FakeChatService()

    result = _runtime(registry, chat).execute(_state())

    assert result.response["status"] == "confirmation_required"
    assert registry.executions == ["translate_selection"]
    assert chat.calls == 0
    assert [step.status for step in result.plan.steps] == ["completed", "pending"]
    assert [call["name"] for call in result.tool_calls] == [
        "translate_selection",
        "save_research_note",
    ]


def test_confirmed_final_write_executes_once_without_post_write_synthesis() -> None:
    registry = FakeRegistry()
    chat = FakeChatService()

    result = _runtime(registry, chat).execute(_state(confirmed=True))

    assert registry.executions == ["translate_selection", "save_research_note"]
    assert chat.calls == 0
    assert result.response["status"] == "completed"
    assert result.response["output_text"] == "tool:save_research_note"
    assert [step.status for step in result.plan.steps] == ["completed", "completed"]
