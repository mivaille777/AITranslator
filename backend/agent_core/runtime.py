from __future__ import annotations

from typing import Any, Callable

from backend.agent_core.events import AgentEvent, AgentEventType
from backend.agent_core.state import AgentState


class AgentRuntime:
    """Minimal orchestration layer around existing agent services.

    Existing planner/tool/context services remain the implementation layer.
    This runtime only standardizes state flow.
    """

    def __init__(
        self,
        *,
        context_provider: Callable[[AgentState], dict[str, Any]] | None = None,
        planner: Callable[[AgentState], dict[str, Any]] | None = None,
        tool_executor: Callable[[AgentState], dict[str, Any]] | None = None,
    ) -> None:
        self.context_provider = context_provider
        self.planner = planner
        self.tool_executor = tool_executor
        self.events: list[AgentEvent] = []

    def _emit(self, event_type: AgentEventType, payload: dict[str, Any]) -> None:
        self.events.append(AgentEvent(event_type=event_type, payload=payload))

    def execute(self, state: AgentState) -> AgentState:
        self._emit(AgentEventType.AGENT_START, {"session_id": state.session_id})

        if self.context_provider:
            state.browser_context = self.context_provider(state)
        self._emit(AgentEventType.CONTEXT_READY, state.browser_context)

        if self.planner:
            state.planned_action = self.planner(state)
            state.intent = state.planned_action.get("intent", state.intent)

        if self.tool_executor:
            result = self.tool_executor(state)
            state.tool_results.append(result)

        self._emit(AgentEventType.AGENT_END, {"intent": state.intent})
        return state
