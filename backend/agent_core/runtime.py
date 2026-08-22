from __future__ import annotations

from typing import Any, Callable

from backend.agent_core.events import AgentEvent, AgentEventType
from backend.agent_core.state import AgentState

AgentEventSink = Callable[[AgentEvent], None]


class AgentRuntime:
    """State-oriented orchestration layer around existing agent services.

    Existing planner/tool/context services remain the implementation layer.
    Agent Core standardizes state flow and events. A product workflow adapter
    can wrap the established ProductAgentService without duplicating its
    bounded Plan -> Validate -> Execute -> Synthesize loop.
    """

    def __init__(
        self,
        *,
        context_provider: Callable[[AgentState], dict[str, Any]] | None = None,
        planner: Callable[[AgentState], dict[str, Any]] | None = None,
        tool_executor: Callable[[AgentState], dict[str, Any]] | None = None,
        workflow_adapter: Callable[[AgentState], AgentState] | None = None,
    ) -> None:
        self.context_provider = context_provider
        self.planner = planner
        self.tool_executor = tool_executor
        self.workflow_adapter = workflow_adapter
        self.events: list[AgentEvent] = []
        self._event_sink: AgentEventSink | None = None

    def _emit(self, event_type: AgentEventType, payload: dict[str, Any]) -> None:
        event = AgentEvent(event_type=event_type, payload=payload)
        self.events.append(event)
        if self._event_sink is not None:
            self._event_sink(event)

    def execute(
        self,
        state: AgentState,
        *,
        event_sink: AgentEventSink | None = None,
    ) -> AgentState:
        previous_sink = self._event_sink
        self._event_sink = event_sink
        self.events.clear()
        try:
            self._emit(AgentEventType.AGENT_START, {"session_id": state.session_id})

            if self.context_provider:
                state.browser_context = self.context_provider(state)
            self._emit(AgentEventType.CONTEXT_READY, state.browser_context)

            if self.workflow_adapter is not None:
                previous_call_count = len(state.tool_calls)
                previous_result_count = len(state.tool_results)
                eventful_run = getattr(self.workflow_adapter, "run_with_events", None)
                if callable(eventful_run):
                    state = eventful_run(state, self._emit)
                else:
                    state = self.workflow_adapter(state)
                    for call in state.tool_calls[previous_call_count:]:
                        self._emit(AgentEventType.TOOL_CALL, call)
                    for result in state.tool_results[previous_result_count:]:
                        self._emit(AgentEventType.TOOL_RESULT, result)

                self._emit(
                    AgentEventType.AGENT_END,
                    {
                        "intent": state.intent,
                        "status": state.response.get("status", ""),
                        "ui_mode": state.ui_mode,
                    },
                )
                return state

            if self.planner:
                state.planned_action = self.planner(state)
                state.intent = state.planned_action.get("intent", state.intent)
                self._emit(AgentEventType.PLAN_READY, state.planned_action)

            if self.tool_executor:
                self._emit(
                    AgentEventType.TOOL_CALL,
                    {
                        "name": state.planned_action.get("tool_name", ""),
                        "arguments": state.planned_action.get("arguments", {}),
                    },
                )
                result = self.tool_executor(state)
                state.tool_results.append(result)
                self._emit(AgentEventType.TOOL_RESULT, result)

            self._emit(AgentEventType.AGENT_END, {"intent": state.intent})
            return state
        finally:
            self._event_sink = previous_sink
