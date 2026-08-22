from __future__ import annotations

from types import SimpleNamespace

from backend.models.agent_tools import AgentPlan
from backend.services.agent_tool_registry import AgentToolExecutionResult, AgentToolSpec
from backend.services.product_agent_service import ProductAgentService


TRANSLATE_TOOL = AgentToolSpec(
    name="translate_selection",
    title="Translate selection",
    description="Translate the current selection.",
    category="translation",
    effect="compute",
    requires_reading_context=True,
    requires_confirmation=False,
    input_schema={},
)
WRITE_TOOL = AgentToolSpec(
    name="save_research_note",
    title="Save research note",
    description="Persist the current selection.",
    category="research",
    effect="write",
    requires_reading_context=True,
    requires_confirmation=True,
    input_schema={},
)


class FakePlanner:
    def __init__(self, plan: AgentPlan) -> None:
        self.plan_result = plan

    def plan(self, **_kwargs):
        return self.plan_result


class FakeRegistry:
    def __init__(self, spec: AgentToolSpec) -> None:
        self.spec = spec
        self.executions: list[tuple[str, dict]] = []

    def list_tools(self):
        return (self.spec,)

    def get_tool(self, name: str):
        return self.spec if name == self.spec.name else None

    def execute(self, name: str, **payload):
        self.executions.append((name, payload))
        return AgentToolExecutionResult(
            tool_name=name,
            output_text="工具结果",
            effect=self.spec.effect,
            provider="fake-tool",
            model="fake-model",
            request_id=payload.get("request_id", 0),
            data={"grounded": True},
        )


class FakeChatService:
    def send(self, **kwargs):
        return SimpleNamespace(
            output_text="最终回答",
            provider="fake-chat",
            model="fake-model",
            request_id=kwargs.get("request_id", 0),
        )


def payload(**overrides):
    return {
        "session_id": "session-live",
        "user_message": "Translate this",
        "source_text": "Gaussian Process",
        "translated_text": "",
        "source_language": "en",
        "target_language": "zh-CN",
        "resource_url": "file:///paper.pdf",
        "resource_title": "Paper",
        "section_heading": "Method",
        "context_before": "Before",
        "context_after": "After",
        "source_kind": "pdf_uia",
        "request_id": 19,
        **overrides,
    }


def test_product_agent_emits_plan_tool_and_result_at_execution_boundaries() -> None:
    registry = FakeRegistry(TRANSLATE_TOOL)
    service = ProductAgentService(
        registry=registry,
        chat_service=FakeChatService(),
        planner=FakePlanner(
            AgentPlan(
                action="tool",
                tool_name="translate_selection",
                user_visible_reason="Use the translation tool.",
            )
        ),
    )
    events: list[tuple[str, dict]] = []

    result = service.run(
        event_sink=lambda event_type, data: events.append((event_type, data)),
        **payload(),
    )

    assert result.status == "completed"
    assert [event_type for event_type, _ in events] == [
        "plan_ready",
        "tool_call",
        "tool_result",
    ]
    assert events[1][1]["name"] == "translate_selection"
    assert events[2][1]["tool_name"] == "translate_selection"
    assert registry.executions[0][0] == "translate_selection"


def test_product_agent_confirmation_stops_before_live_tool_result() -> None:
    registry = FakeRegistry(WRITE_TOOL)
    service = ProductAgentService(
        registry=registry,
        chat_service=FakeChatService(),
        planner=FakePlanner(
            AgentPlan(
                action="tool",
                tool_name="save_research_note",
                user_visible_reason="The note must be explicitly confirmed.",
            )
        ),
    )
    events: list[tuple[str, dict]] = []

    result = service.run(
        event_sink=lambda event_type, data: events.append((event_type, data)),
        **payload(user_message="Save this note"),
    )

    assert result.status == "confirmation_required"
    assert [event_type for event_type, _ in events] == ["plan_ready", "tool_call"]
    assert registry.executions == []
