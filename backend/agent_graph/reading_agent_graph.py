from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from backend.agent_core.events import AgentEventType
from backend.agent_core.exceptions import AgentRuntimeError
from backend.agent_core.product_adapter import ProductAgentRuntimeAdapter
from backend.agent_core.reliability import AgentRunControl
from backend.agent_core.state import AgentState
from backend.models.agent_runtime import AgentRouteDecision


GraphEventSink = Callable[[AgentEventType, dict[str, Any]], None]


class ReadingAgentGraphState(TypedDict, total=False):
    """Serializable public state for production and LangSmith Studio."""

    agent_state: dict[str, Any]
    conversation_run: dict[str, Any]
    route: dict[str, Any]
    route_metadata: dict[str, Any]
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


def _merge_emitted(existing: object, new_items: set[AgentEventType]) -> list[str]:
    values: set[str] = set()
    if isinstance(existing, (list, tuple, set, frozenset)):
        values.update(str(item) for item in existing if str(item))
    values.update(item.value for item in new_items)
    return sorted(values)


class ReadingAgentGraph:
    """Bounded LangGraph workflow for the AITrans Reading Agent.

    Stage 10.6 keeps deterministic/single-step requests on the established fast
    path and expands only ``complex`` routes into a bounded multi-step plan.
    Retrieval, citations, and web research remain later stages.
    """

    node_names = (
        "prepare_conversation",
        "route_request",
        "execute_direct",
        "plan_multi_step",
        "execute_plan_step",
        "synthesize_multi_step",
        "finalize_conversation",
    )

    def __init__(self, adapter: ProductAgentRuntimeAdapter) -> None:
        self._adapter = adapter
        builder = StateGraph(
            ReadingAgentGraphState,
            context_schema=ReadingAgentRuntimeContext,
        )
        builder.add_node("prepare_conversation", self._prepare_conversation)
        builder.add_node("route_request", self._route_request)
        builder.add_node("execute_direct", self._execute_direct)
        builder.add_node("plan_multi_step", self._plan_multi_step)
        builder.add_node("execute_plan_step", self._execute_plan_step)
        builder.add_node("synthesize_multi_step", self._synthesize_multi_step)
        builder.add_node("finalize_conversation", self._finalize_conversation)

        builder.add_edge(START, "prepare_conversation")
        builder.add_edge("prepare_conversation", "route_request")
        builder.add_conditional_edges(
            "route_request",
            self._route_branch,
            {
                "complex": "plan_multi_step",
                "direct": "execute_direct",
            },
        )
        builder.add_edge("execute_direct", "finalize_conversation")
        builder.add_edge("plan_multi_step", "execute_plan_step")
        builder.add_conditional_edges(
            "execute_plan_step",
            self._plan_step_branch,
            {
                "continue": "execute_plan_step",
                "synthesize": "synthesize_multi_step",
                "finalize": "finalize_conversation",
            },
        )
        builder.add_edge("synthesize_multi_step", "finalize_conversation")
        builder.add_edge("finalize_conversation", END)
        self._compiled = builder.compile()

    @property
    def compiled_graph(self):
        return self._compiled

    @staticmethod
    def _runtime(
        runtime: Runtime[ReadingAgentRuntimeContext],
    ) -> tuple[GraphEventSink | None, AgentRunControl]:
        context = runtime.context or {}
        return context.get("event_sink"), context.get("control") or AgentRunControl()

    def _abort(self, graph_state: ReadingAgentGraphState, exc: Exception) -> None:
        self._adapter.abort_conversation(
            _load_conversation_run(graph_state.get("conversation_run")),
            exc,
        )

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

    def _route_request(
        self,
        graph_state: ReadingAgentGraphState,
        runtime: Runtime[ReadingAgentRuntimeContext],
    ) -> dict[str, Any]:
        state = _coerce_agent_state(graph_state["agent_state"])
        _, control = self._runtime(runtime)
        try:
            route, metadata = self._adapter.resolve_route(state, control=control)
        except Exception as exc:
            self._abort(graph_state, exc)
            raise
        return {
            "agent_state": _dump_agent_state(state),
            "route": route.model_dump(mode="json"),
            "route_metadata": dict(metadata),
        }

    @staticmethod
    def _route_branch(graph_state: ReadingAgentGraphState) -> str:
        route = AgentRouteDecision.model_validate(graph_state.get("route", {}))
        return "complex" if route.kind == "complex" else "direct"

    def _execute_direct(
        self,
        graph_state: ReadingAgentGraphState,
        runtime: Runtime[ReadingAgentRuntimeContext],
    ) -> dict[str, Any]:
        state = _coerce_agent_state(graph_state["agent_state"])
        route = AgentRouteDecision.model_validate(graph_state.get("route", {}))
        emit, control = self._runtime(runtime)
        try:
            state, emitted = self._adapter.execute_product(
                state,
                emit,
                control=control,
                resolved_route=route,
                route_metadata=dict(graph_state.get("route_metadata", {}) or {}),
            )
        except Exception as exc:
            self._abort(graph_state, exc)
            raise
        return {
            "agent_state": _dump_agent_state(state),
            "emitted_event_types": _merge_emitted(
                graph_state.get("emitted_event_types", ()),
                emitted,
            ),
        }

    def _plan_multi_step(
        self,
        graph_state: ReadingAgentGraphState,
        runtime: Runtime[ReadingAgentRuntimeContext],
    ) -> dict[str, Any]:
        state = _coerce_agent_state(graph_state["agent_state"])
        emit, control = self._runtime(runtime)
        try:
            plan, metadata = self._adapter.plan_multi_step(state, control=control)
        except Exception as exc:
            self._abort(graph_state, exc)
            raise

        if emit is not None:
            emit(
                AgentEventType.PLAN_READY,
                {
                    "mode": "multi_step",
                    "goal": plan.goal,
                    "steps": [step.model_dump(mode="json") for step in plan.steps],
                    "route_kind": state.route.kind,
                    "route_source": state.route.source,
                    "request_id": state.execution.request_id,
                    **metadata,
                },
            )
        emitted = {AgentEventType.PLAN_READY} if emit is not None else set()
        return {
            "agent_state": _dump_agent_state(state),
            "emitted_event_types": _merge_emitted(
                graph_state.get("emitted_event_types", ()),
                emitted,
            ),
        }

    def _execute_plan_step(
        self,
        graph_state: ReadingAgentGraphState,
        runtime: Runtime[ReadingAgentRuntimeContext],
    ) -> dict[str, Any]:
        state = _coerce_agent_state(graph_state["agent_state"])
        emit, control = self._runtime(runtime)
        pending = next(
            (
                step
                for step in state.plan.steps
                if step.step_id == state.plan.current_step_id
            ),
            None,
        )
        if pending is None:
            pending = next((step for step in state.plan.steps if step.status == "pending"), None)
        if pending is None:
            return {"agent_state": _dump_agent_state(state)}

        if len(state.tool_calls) >= control.policy.max_tool_calls:
            exc = AgentRuntimeError(
                "Multi-step Agent tool-call budget exhausted.",
                stage="planner",
                fallback_reason="tool_call_budget_exhausted",
            )
            self._abort(graph_state, exc)
            raise exc

        completed_ids = {
            step.step_id for step in state.plan.steps if step.status == "completed"
        }
        if any(dependency not in completed_ids for dependency in pending.depends_on):
            exc = AgentRuntimeError(
                f"Plan step {pending.step_id} has unsatisfied dependencies.",
                stage="planner",
                fallback_reason="invalid_plan_dependency",
            )
            self._abort(graph_state, exc)
            raise exc

        state.mark_plan_step(pending.step_id, "running")
        try:
            state, emitted = self._adapter.execute_plan_step(
                state,
                pending,
                emit,
                control=control,
            )
        except Exception as exc:
            state.mark_plan_step(pending.step_id, "failed")
            self._abort(graph_state, exc)
            raise

        if state.response_state.status == "confirmation_required":
            state.mark_plan_step(pending.step_id, "pending")
        else:
            state.mark_plan_step(pending.step_id, "completed")

        return {
            "agent_state": _dump_agent_state(state),
            "emitted_event_types": _merge_emitted(
                graph_state.get("emitted_event_types", ()),
                emitted,
            ),
        }

    @staticmethod
    def _plan_step_branch(graph_state: ReadingAgentGraphState) -> str:
        state = _coerce_agent_state(graph_state["agent_state"])
        if state.response_state.status == "confirmation_required":
            return "finalize"
        if any(step.status == "pending" for step in state.plan.steps):
            return "continue"
        return "synthesize"

    def _synthesize_multi_step(
        self,
        graph_state: ReadingAgentGraphState,
        runtime: Runtime[ReadingAgentRuntimeContext],
    ) -> dict[str, Any]:
        state = _coerce_agent_state(graph_state["agent_state"])
        emit, control = self._runtime(runtime)
        try:
            state, emitted = self._adapter.synthesize_multi_step(
                state,
                emit,
                control=control,
            )
        except Exception as exc:
            self._abort(graph_state, exc)
            raise
        return {
            "agent_state": _dump_agent_state(state),
            "emitted_event_types": _merge_emitted(
                graph_state.get("emitted_event_types", ()),
                emitted,
            ),
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
            "route": {},
            "route_metadata": {},
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
