import json
from pathlib import Path
from types import SimpleNamespace

from backend.agent_core.product_adapter import ProductAgentRuntimeAdapter
from backend.agent_core.state import AgentState
from backend.agent_graph.reading_agent_graph import ReadingAgentGraph
from backend.agent_graph.studio import make_graph
from backend.models.agent_tools import AgentPlan


class FakeProductAgentService:
    def run(self, *, event_sink=None, control=None, **payload):
        if event_sink is not None:
            event_sink(
                "plan_ready",
                {
                    "action": "answer",
                    "tool_name": "",
                    "request_id": payload.get("request_id", 0),
                },
            )
        return SimpleNamespace(
            status="completed",
            plan=AgentPlan(
                action="answer",
                tool_name="",
                user_visible_reason="Answer from current context.",
                arguments={},
            ),
            output_text="Studio-ready answer",
            provider="fake",
            model="fake-model",
            request_id=payload.get("request_id", 0),
            tool_result=None,
            route=None,
        )


def test_graph_state_is_json_serializable_without_runtime_objects() -> None:
    graph = ReadingAgentGraph(
        ProductAgentRuntimeAdapter(FakeProductAgentService())
    ).compiled_graph
    state = AgentState(
        session_id="studio-session",
        user_input="What does this mean?",
        selected_text="Gaussian Process",
        browser_context={
            "resource_title": "Control Paper",
            "source_kind": "desktop",
            "request_id": 9,
        },
    )

    result = graph.invoke({"agent_state": state.model_dump(mode="json")})

    json.dumps(result)
    assert isinstance(result["agent_state"], dict)
    assert result["agent_state"]["response"]["output_text"] == "Studio-ready answer"
    assert result["emitted_event_types"] == ["plan_ready"]
    assert "event_sink" not in result
    assert "control" not in result


def test_langgraph_config_exposes_reading_agent_factory() -> None:
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / "langgraph.json").read_text(encoding="utf-8"))

    assert config["graphs"] == {
        "reading_agent": "./backend/agent_graph/studio.py:make_graph"
    }
    assert config["dependencies"] == ["."]
    assert config["env"]["LANGSMITH_TRACING"] == "false"
    assert callable(make_graph)


def test_repository_ignores_local_studio_credentials() -> None:
    root = Path(__file__).resolve().parents[2]
    ignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert ".env" in ignore
