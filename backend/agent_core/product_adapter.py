from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from backend.agent_core.events import AgentEventType
from backend.agent_core.reliability import AgentRunControl
from backend.agent_core.state import AgentState


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
    """Map the existing bounded ProductAgentService loop onto AgentState."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @staticmethod
    def _payload(state: AgentState) -> dict[str, Any]:
        context = state.browser_context
        confirmed = context.get("confirmed_write_tools", ())
        if not isinstance(confirmed, (list, tuple, set, frozenset)):
            confirmed = ()
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
            "conversation_id": str(context.get("conversation_id", "") or ""),
            "confirmed_write_tools": [str(item) for item in confirmed if str(item).strip()],
            "request_id": max(0, int(context.get("request_id", 0) or 0)),
        }

    @staticmethod
    def _apply_result(state: AgentState, result: Any) -> AgentState:
        plan = _structured(result.plan)
        state.planned_action = plan

        action = str(plan.get("action", "answer") or "answer")
        tool_name = str(plan.get("tool_name", "") or "")
        state.intent = tool_name if action == "tool" and tool_name else "answer"

        if tool_name:
            state.tool_calls.append(
                {
                    "name": tool_name,
                    "arguments": dict(plan.get("arguments", {}) or {}),
                }
            )

        tool_result = getattr(result, "tool_result", None)
        if tool_result is not None:
            state.tool_results.append(_structured(tool_result))

        state.response = {
            "status": str(getattr(result, "status", "completed") or "completed"),
            "output_text": str(getattr(result, "output_text", "") or ""),
            "provider": str(getattr(result, "provider", "") or ""),
            "model": str(getattr(result, "model", "") or ""),
            "request_id": max(0, int(getattr(result, "request_id", 0) or 0)),
        }
        state.ui_mode = _UI_MODE_BY_TOOL.get(tool_name, "assistant")
        return state

    def __call__(self, state: AgentState) -> AgentState:
        result = self._service.run(**self._payload(state))
        return self._apply_result(state, result)

    def run_with_events(
        self,
        state: AgentState,
        emit: Callable[[AgentEventType, dict[str, Any]], None],
        *,
        control: AgentRunControl | None = None,
    ) -> AgentState:
        emitted: set[AgentEventType] = set()

        def forward(event_type: str, payload: dict[str, Any]) -> None:
            try:
                core_type = AgentEventType(event_type)
            except ValueError:
                return
            emitted.add(core_type)
            emit(core_type, payload)

        result = self._service.run(
            event_sink=forward,
            control=control,
            **self._payload(state),
        )
        state = self._apply_result(state, result)

        # Compatibility fallback for lightweight mocks or alternative services.
        if AgentEventType.PLAN_READY not in emitted:
            emit(AgentEventType.PLAN_READY, dict(state.planned_action))
        if state.tool_calls and AgentEventType.TOOL_CALL not in emitted:
            emit(AgentEventType.TOOL_CALL, dict(state.tool_calls[-1]))
        if state.tool_results and AgentEventType.TOOL_RESULT not in emitted:
            emit(AgentEventType.TOOL_RESULT, dict(state.tool_results[-1]))
        return state

    def close(self) -> None:
        close = getattr(self._service, "close", None)
        if callable(close):
            close()


__all__ = ["ProductAgentRuntimeAdapter"]
