from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agent_core.events import AgentEventType
from backend.agent_core.product_adapter import ProductAgentRuntimeAdapter
from backend.agent_core.reliability import AgentRunControl
from backend.agent_core.state import AgentState


GraphEventSink = Callable[[AgentEventType, dict[str, Any]], None]


class ReadingAgentGraphState(TypedDict, total=False):
    agent_state: AgentState
    conversation_run: Any
    emitted_event_types: set[AgentEventType]
    event_sink: GraphEventSink | None
    control: AgentRunControl


class ReadingAgentGraph:
    """LangGraph orchestration shell for the production Reading Agent.

    Stage 10.5 deliberately preserves the existing single-step ProductAgent
    behavior. LangGraph now owns the durable workflow boundaries—Conversation
    preparation, one bounded product-agent execution, and Conversation
    finalization—while ``AgentRuntime`` remains responsible for correlation,
    budgets, cancellation, lifecycle telemetry and trace persistence.

    Stage 10.6 can replace ``execute_single_step`` with explicit planner/tool
    branches without changing the outer Runtime or API contracts.
    """

    node_names = (
        "prepare_conversation",
        "execute_single_step",
        "finalize_conversation",
    )

    def __init__(self, adapter: ProductAgentRuntimeAdapter) -> None:
        self._adapter = adapter
        builder = StateGraph(ReadingAgentGraphState)
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
        state = graph_state["agent_state"]
        conversation_run = self._adapter.begin_conversation(state)
        return {
            "agent_state": state,
            "conversation_run": conversation_run,
        }

    def _execute_single_step(
        self,
        graph_state: ReadingAgentGraphState,
    ) -> dict[str, Any]:
        state = graph_state["agent_state"]
        conversation_run = graph_state.get("conversation_run")
        emit = graph_state.get("event_sink")
        control = graph_state.get("control")

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
            "agent_state": state,
            "emitted_event_types": emitted,
        }

    def _finalize_conversation(
        self,
        graph_state: ReadingAgentGraphState,
    ) -> dict[str, Any]:
        state = graph_state["agent_state"]
        self._adapter.complete_conversation(
            graph_state.get("conversation_run"),
            state,
        )
        return {"agent_state": state}

    def _invoke(
        self,
        state: AgentState,
        *,
        emit: GraphEventSink | None,
        control: AgentRunControl | None,
    ) -> tuple[AgentState, set[AgentEventType]]:
        initial: ReadingAgentGraphState = {
            "agent_state": state,
            "event_sink": emit,
            "control": control or AgentRunControl(),
            "emitted_event_types": set(),
        }
        result = self._compiled.invoke(initial)
        final_state = result.get("agent_state", state)
        emitted = set(result.get("emitted_event_types", set()))
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


__all__ = ["ReadingAgentGraph", "ReadingAgentGraphState"]
