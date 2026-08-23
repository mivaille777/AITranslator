from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from backend.agent_core.events import AgentEventType
from backend.agent_core.product_adapter import ProductAgentRuntimeAdapter
from backend.agent_core.reliability import AgentRunControl
from backend.agent_core.state import AgentState


GraphEventSink = Callable[[AgentEventType, dict[str, Any]], None]


class ReadingAgentGraphState(TypedDict, total=False):
    """Serializable state exposed by the Reading Agent graph.

    Runtime-only objects such as callbacks and cancellation controls are passed
    through LangGraph runtime context instead of being persisted in graph state.
    """

    agent_state: dict[str, Any]
    conversation_run: dict[str, Any]
    emitted_event_types: list[str]


class ReadingAgentRuntimeContext(TypedDict, total=False):
    """Per-invocation objects that must never become Studio/checkpoint state."""

    event_sink: GraphEventSink | None
    control: AgentRunControl


def _coerce_agent_state(value: AgentState | dict[str, Any]) -> AgentState:
    if isinstance(value, AgentState):
        return value
    return AgentState.model_validate(value)


def _dump_agent_state(state: AgentState) -> dict[str, Any]:
    return state.model_dump(mode="json")


def _dump_conversation_run(run: Any) -> dict[str, Any]:
    if run is None:
        return {}
    history = getattr(run, "history", ()) or ()
    return {
        "conversation_id": str(getattr(run, "conversation_id", "") or ""),
        "user_message_id": str(getattr(run, "user_message_id", "") or ""),
        "assistant_message_id": str(getattr(run, "assistant_message_id", "") or ""),
        "history": [
            [str(item[0]), str(item[1])]
            for item in history
            if isinstance(item, (list, tuple)) and len(item) >= 2
        ],
        "owner_id": str(getattr(run, "owner_id", "") or ""),
        "request_id": max(0, int(getattr(run, "request_id", 0) or 0)),
    }


def _load_conversation_run(payload: dict[str, Any] | None) -> Any:
    if not payload:
        return None
    history = tuple(
        (str(item[0]), str(item[1]))
        for item in payload.get("history", ())
        if isinstance(item, (list, tuple)) and len(item) >= 2
    )
    return SimpleNamespace(
        conversation_id=str(payload.get("conversation_id", "") or ""),
        user_message_id=str(payload.get("user_message_id", "") or ""),
        assistant_message_id=str(payload.get("assistant_message_id", "") or ""),
        history=history,
        owner_id=str(payload.get("owner_id", "") or ""),
        request_id=max(0, int(payload.get("request_id", 0) or 0)),
    )


class ReadingAgentGraph:
    """LangGraph orchestration shell for the production Reading Agent.

    Stage 10.5 preserves the existing single-step ProductAgent behavior while
    LangGraph owns the workflow boundaries. Stage 10.5.1 keeps graph state
    JSON-serializable for LangSmith Studio/checkpoint inspection and moves
    runtime-only callbacks/control objects into LangGraph runtime context.

    Stage 10.6 can replace ``execute_single_step`` with explicit router/planner/
    tool branches without changing the outer AgentRuntime or API contracts.
    """

    node_names = (
        "prepare_conversation",
        "execute_single_step",
        "finalize_conversation",
    )

    def __init__(self, adapter: ProductAgentRuntimeAdapter) -> None:
        self._adapter = adapter
        builder = StateGraph(
            ReadingAgentGraphState,
            context_schema=ReadingAgentRuntimeContext,
        )
        builder.add_node("prepare_conversation", self._prepare_conversation)
        builder.add_node("execute_single_step", self._execute_single_step)
        builder.add_node("finalize_conversation", self._finalize_conversation)
        builder.add_edge(START, "prepare_conversation")
        builder.add_edge("prepare_conversation", "execute_single_step")
        builder.add_edge("execute_single_step", "finalize_conversation")
        builder.add_edge("finalize_conversation", END)
        self._compiled = builder.compile()

    @property
    def compiled_graph(self):
        return self._compiled

    def _prepare_conversation(
        self,
        graph_state: ReadingAgentGraphState,
    ) -> dict[str, Any]:
        state = _coerce_agent_state(graph_state["agent_state"])
        conversation_run = self._adapter.begin_conversation(state)
        return {
            "agent_state": _dump_agent_state(state),
            "conversation_run": _dump_conversation_run(conversation_run),
        }

    def _execute_single_step(
        self,
        graph_state: ReadingAgentGraphState,
        runtime: Runtime[ReadingAgentRuntimeContext],
    ) -> dict[str, Any]:
        state = _coerce_agent_state(graph_state["agent_state"])
        conversation_run = _load_conversation_run(graph_state.get("conversation_run"))
        runtime_context = runtime.context or {}
        emit = runtime_context.get("event_sink")
        control = runtime_context.get("control") or AgentRunControl()

        try:
            state, emitted = self._adapter.execute_product(
                state,
                emit,
                control=control,
            )
        except Exception as exc:
            self._adapter.abort_conversation(conversation_run, exc)
            raise

        return {
            "agent_state": _dump_agent_state(state),
            "emitted_event_types": sorted(item.value for item in emitted),
        }

    def _finalize_conversation(
        self,
        graph_state: ReadingAgentGraphState,
    ) -> dict[str, Any]:
        state = _coerce_agent_state(graph_state["agent_state"])
        self._adapter.complete_conversation(
            _load_conversation_run(graph_state.get("conversation_run")),
            state,
        )
        return {"agent_state": _dump_agent_state(state)}

    def _invoke(
        self,
        state: AgentState,
        *,
        emit: GraphEventSink | None,
        control: AgentRunControl | None,
    ) -> tuple[AgentState, set[AgentEventType]]:
        initial: ReadingAgentGraphState = {
            "agent_state": _dump_agent_state(state),
            "conversation_run": {},
            "emitted_event_types": [],
        }
        result = self._compiled.invoke(
            initial,
            context={
                "event_sink": emit,
                "control": control or AgentRunControl(),
            },
        )
        final_state = _coerce_agent_state(result.get("agent_state", initial["agent_state"]))
        emitted = {
            AgentEventType(item)
            for item in result.get("emitted_event_types", ())
        }
        return final_state, emitted

    def __call__(self, state: AgentState) -> AgentState:
        final_state, _ = self._invoke(state, emit=None, control=None)
        return final_state

    def run_with_events(
        self,
        state: AgentState,
        emit: GraphEventSink,
        *,
        control: AgentRunControl | None = None,
    ) -> AgentState:
        final_state, emitted = self._invoke(state, emit=emit, control=control)
        self._adapter.emit_compatibility_events(final_state, emitted, emit)
        return final_state

    def close(self) -> None:
        self._adapter.close()


__all__ = [
    "ReadingAgentGraph",
    "ReadingAgentGraphState",
    "ReadingAgentRuntimeContext",
]
