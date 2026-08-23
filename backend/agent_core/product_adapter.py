from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from backend.agent_core.events import AgentEventType
from backend.agent_core.exceptions import AgentCancelledError
from backend.agent_core.reliability import AgentRunControl
from backend.agent_core.state import AgentState
from backend.services.agent_conversation_service import AgentConversationService


_UI_MODE_BY_TOOL = {
    "translate_selection": "translation",
    "explain_selection": "explanation",
    "summarize_selection": "summary",
    "analyze_section_role": "research",
    "polish_selection": "assistant",
    "save_research_note": "note",
    "inspect_reading_context": "assistant",
}


def _structured(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {"value": dumped}
    if is_dataclass(value):
        dumped = asdict(value)
        return dumped if isinstance(dumped, dict) else {"value": dumped}
    if isinstance(value, dict):
        return dict(value)
    return {"value": value}


class ProductAgentRuntimeAdapter:
    """Compatibility bridge between ProductAgentService and AgentState.

    Production orchestration now lives in ``ReadingAgentGraph``. This adapter
    keeps the state projection, product-service invocation and Conversation
    lifecycle primitives reusable while preserving the pre-graph callable API
    for focused unit tests and migration compatibility.
    """

    def __init__(
        self,
        service: Any,
        conversation_service: AgentConversationService | Any | None = None,
    ) -> None:
        self._service = service
        self._conversation_service = conversation_service

    @staticmethod
    def build_payload(state: AgentState) -> dict[str, Any]:
        context = state.browser_context
        confirmed = context.get("confirmed_write_tools", ())
        if not isinstance(confirmed, (list, tuple, set, frozenset)):
            confirmed = ()
        history = tuple(
            (item.role, item.content)
            for item in state.conversation.history
            if item.role in {"user", "assistant"} and item.content.strip()
        )
        return {
            "session_id": state.session_id or "agent-session",
            "user_message": state.user_input,
            "source_text": state.selected_text,
            "translated_text": str(context.get("translated_text", "") or ""),
            "source_language": str(context.get("source_language", "auto") or "auto"),
            "target_language": str(context.get("target_language", "zh-CN") or "zh-CN"),
            "resource_url": str(context.get("resource_url", "") or ""),
            "resource_title": str(context.get("resource_title", "") or ""),
            "section_heading": str(context.get("section_heading", "") or ""),
            "context_before": str(context.get("context_before", "") or ""),
            "context_after": str(context.get("context_after", "") or ""),
            "source_kind": str(context.get("source_kind", "desktop") or "desktop"),
            "style": str(context.get("style", "academic") or "academic"),
            "conversation_id": state.conversation.conversation_id,
            "history": history,
            "confirmed_write_tools": [str(item) for item in confirmed if str(item).strip()],
            "request_id": max(0, int(context.get("request_id", 0) or 0)),
        }

    _payload = build_payload

    @staticmethod
    def apply_result(state: AgentState, result: Any) -> AgentState:
        plan = _structured(result.plan)
        state.apply_plan(plan)

        route = _structured(getattr(result, "route", None))
        if route:
            state.apply_route(route)
        else:
            action = str(plan.get("action", "answer") or "answer")
            tool_name = str(plan.get("tool_name", "") or "")
            state.intent = tool_name if action == "tool" and tool_name else "answer"

        tool_name = str(plan.get("tool_name", "") or "")
        if tool_name:
            state.record_tool_call(
                {
                    "name": tool_name,
                    "arguments": dict(plan.get("arguments", {}) or {}),
                }
            )

        tool_result = getattr(result, "tool_result", None)
        if tool_result is not None:
            state.record_tool_result(_structured(tool_result))

        state.ui_mode = _UI_MODE_BY_TOOL.get(tool_name, "assistant")
        state.apply_response(
            {
                "status": str(getattr(result, "status", "completed") or "completed"),
                "output_text": str(getattr(result, "output_text", "") or ""),
                "provider": str(getattr(result, "provider", "") or ""),
                "model": str(getattr(result, "model", "") or ""),
                "request_id": max(0, int(getattr(result, "request_id", 0) or 0)),
            }
        )
        return state

    _apply_result = apply_result

    def begin_conversation(self, state: AgentState):
        service = self._conversation_service
        if service is None:
            return None
        run = service.begin(state)
        service.apply_to_state(state, run)
        return run

    _begin_conversation = begin_conversation

    def complete_conversation(self, run: Any, state: AgentState) -> None:
        if run is not None and self._conversation_service is not None:
            self._conversation_service.complete(run, state)

    _complete_conversation = complete_conversation

    def abort_conversation(self, run: Any, exc: Exception) -> None:
        if run is None or self._conversation_service is None:
            return
        if isinstance(exc, AgentCancelledError):
            self._conversation_service.cancel(run)
        else:
            self._conversation_service.fail(run, exc)

    _abort_conversation = abort_conversation

    def execute_product(
        self,
        state: AgentState,
        emit: Callable[[AgentEventType, dict[str, Any]], None] | None = None,
        *,
        control: AgentRunControl | None = None,
    ) -> tuple[AgentState, set[AgentEventType]]:
        emitted: set[AgentEventType] = set()

        def forward(event_type: str, payload: dict[str, Any]) -> None:
            try:
                core_type = AgentEventType(event_type)
            except ValueError:
                return
            emitted.add(core_type)
            if emit is not None:
                emit(core_type, payload)

        result = self._service.run(
            event_sink=forward,
            control=control,
            **self.build_payload(state),
        )
        return self.apply_result(state, result), emitted

    @staticmethod
    def emit_compatibility_events(
        state: AgentState,
        emitted: set[AgentEventType],
        emit: Callable[[AgentEventType, dict[str, Any]], None],
    ) -> None:
        if AgentEventType.PLAN_READY not in emitted:
            emit(AgentEventType.PLAN_READY, dict(state.planned_action))
        if state.tool_calls and AgentEventType.TOOL_CALL not in emitted:
            emit(AgentEventType.TOOL_CALL, dict(state.tool_calls[-1]))
        if state.tool_results and AgentEventType.TOOL_RESULT not in emitted:
            emit(AgentEventType.TOOL_RESULT, dict(state.tool_results[-1]))

    def __call__(self, state: AgentState) -> AgentState:
        conversation_run = self.begin_conversation(state)
        try:
            result = self._service.run(**self.build_payload(state))
            state = self.apply_result(state, result)
            self.complete_conversation(conversation_run, state)
            return state
        except Exception as exc:
            self.abort_conversation(conversation_run, exc)
            raise

    def run_with_events(
        self,
        state: AgentState,
        emit: Callable[[AgentEventType, dict[str, Any]], None],
        *,
        control: AgentRunControl | None = None,
    ) -> AgentState:
        conversation_run = self.begin_conversation(state)
        try:
            state, emitted = self.execute_product(state, emit, control=control)
            self.complete_conversation(conversation_run, state)
        except Exception as exc:
            self.abort_conversation(conversation_run, exc)
            raise

        self.emit_compatibility_events(state, emitted, emit)
        return state

    def close(self) -> None:
        close = getattr(self._service, "close", None)
        if callable(close):
            close()


__all__ = ["ProductAgentRuntimeAdapter"]
