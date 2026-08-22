from __future__ import annotations

from dataclasses import dataclass
import json
from time import monotonic
from typing import Any, Callable

from app.ai.errors import AIConfigurationError, AIError
from backend.agent_core.exceptions import (
    AgentBudgetExceededError,
    AgentCancelledError,
    AgentRuntimeError,
    AgentToolError,
    AgentToolTimeoutError,
)
from backend.agent_core.reliability import AgentRunControl, run_safe_tool_with_timeout
from backend.models.agent_tools import AgentPlan
from backend.services.agent_planner_service import AgentPlannerService
from backend.services.agent_tool_registry import (
    AgentToolExecutionResult,
    AgentToolRegistry,
)
from backend.services.companion_chat_service import CompanionChatService

_ALLOWED_PLANNER_ARGUMENTS = frozenset({"target_language", "style", "user_note"})
AgentLifecycleSink = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class ProductAgentRunResult:
    status: str
    plan: AgentPlan
    output_text: str = ""
    provider: str = ""
    model: str = ""
    request_id: int = 0
    tool_result: AgentToolExecutionResult | None = None


def _duration_ms(started: float) -> int:
    return max(0, int((monotonic() - started) * 1000))


def _retryable_tool_error(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            AIConfigurationError,
            AgentCancelledError,
            AgentBudgetExceededError,
            AgentToolTimeoutError,
        ),
    ):
        return False
    return isinstance(exc, (AIError, OSError, TimeoutError, AgentRuntimeError))


class ProductAgentService:
    """Bounded Plan -> Validate -> Execute -> Synthesize agent loop."""

    def __init__(
        self,
        *,
        registry: AgentToolRegistry,
        chat_service: CompanionChatService,
        planner: AgentPlannerService | Any | None = None,
    ) -> None:
        self._registry = registry
        self._chat_service = chat_service
        self._planner = planner or AgentPlannerService()

    @staticmethod
    def _reading_fields(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_text": payload["source_text"],
            "translated_text": payload.get("translated_text", ""),
            "source_language": payload.get("source_language", "auto"),
            "target_language": payload.get("target_language", "zh-CN"),
            "resource_url": payload.get("resource_url", ""),
            "resource_title": payload.get("resource_title", ""),
            "section_heading": payload.get("section_heading", ""),
            "context_before": payload.get("context_before", ""),
            "context_after": payload.get("context_after", ""),
            "source_kind": payload.get("source_kind", "desktop"),
        }

    @staticmethod
    def _emit(
        sink: AgentLifecycleSink | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if sink is not None:
            sink(event_type, payload)

    def run(
        self,
        *,
        event_sink: AgentLifecycleSink | None = None,
        control: AgentRunControl | None = None,
        **payload: Any,
    ) -> ProductAgentRunResult:
        control = control or AgentRunControl()
        reading = self._reading_fields(payload)
        tools = self._registry.list_tools()
        request_id = max(0, int(payload.get("request_id", 0) or 0))

        control.checkpoint("planner")
        planner_started = monotonic()
        plan = self._planner.plan(
            tools=tools,
            user_message=str(payload["user_message"]),
            source_text=str(reading["source_text"]),
            translated_text=str(reading["translated_text"]),
            resource_url=str(reading["resource_url"]),
            resource_title=str(reading["resource_title"]),
            section_heading=str(reading["section_heading"]),
            context_before=str(reading["context_before"]),
            context_after=str(reading["context_after"]),
            source_kind=str(reading["source_kind"]),
        )
        control.checkpoint("planner_result")
        self._emit(
            event_sink,
            "plan_ready",
            {
                "action": plan.action,
                "tool_name": plan.tool_name,
                "user_visible_reason": plan.user_visible_reason,
                "arguments": dict(plan.arguments),
                "request_id": request_id,
                "duration_ms": _duration_ms(planner_started),
                "provider": str(getattr(self._planner, "provider_name", "") or ""),
                "model": str(getattr(self._planner, "model", "") or ""),
                "prompt_id": str(getattr(self._planner, "prompt_id", "") or ""),
            },
        )

        if plan.action == "answer":
            control.checkpoint("synthesis")
            synthesis_started = monotonic()
            answer = self._chat_service.send(
                session_id=str(payload.get("session_id", "agent-session")),
                user_message=str(payload["user_message"]),
                **reading,
                request_id=request_id,
                context_mode="reading",
            )
            control.checkpoint("synthesis_result")
            self._emit(
                event_sink,
                "synthesis_ready",
                {
                    "provider": answer.provider,
                    "model": answer.model,
                    "request_id": answer.request_id,
                    "duration_ms": _duration_ms(synthesis_started),
                    "prompt_id": str(getattr(self._chat_service, "prompt_id", "") or ""),
                },
            )
            return ProductAgentRunResult(
                status="completed",
                plan=plan,
                output_text=answer.output_text,
                provider=answer.provider,
                model=answer.model,
                request_id=answer.request_id,
            )

        spec = self._registry.get_tool(plan.tool_name)
        if spec is None:
            raise RuntimeError(f"Validated plan references missing tool: {plan.tool_name}")

        self._emit(
            event_sink,
            "tool_call",
            {
                "name": spec.name,
                "arguments": dict(plan.arguments),
                "effect": spec.effect,
                "requires_confirmation": spec.requires_confirmation,
                "request_id": request_id,
            },
        )

        confirmed = {
            str(item).strip()
            for item in payload.get("confirmed_write_tools", ())
            if str(item).strip()
        }
        if spec.effect == "write" and spec.requires_confirmation and spec.name not in confirmed:
            return ProductAgentRunResult(
                status="confirmation_required",
                plan=plan,
                request_id=request_id,
            )

        execution_payload = {
            **reading,
            "style": str(payload.get("style", "academic") or "academic"),
            "conversation_id": str(payload.get("conversation_id", "") or ""),
            "request_id": request_id,
        }
        for key, value in plan.arguments.items():
            if key in _ALLOWED_PLANNER_ARGUMENTS:
                execution_payload[key] = value

        tool_started = monotonic()
        if spec.effect == "write":
            control.checkpoint(f"write_tool:{spec.name}")
            tool_result = self._registry.execute(spec.name, **execution_payload)
        else:
            max_attempts = 1 + control.policy.max_safe_retries
            tool_result: AgentToolExecutionResult | None = None
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                control.checkpoint(f"tool:{spec.name}:attempt:{attempt}")
                try:
                    tool_result = run_safe_tool_with_timeout(
                        lambda: self._registry.execute(spec.name, **execution_payload),
                        control=control,
                        tool_name=spec.name,
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    retryable = _retryable_tool_error(exc)
                    if not retryable or attempt >= max_attempts:
                        if isinstance(exc, AgentRuntimeError):
                            raise
                        raise AgentToolError(
                            f"Agent tool {spec.name} failed after {attempt} attempt(s): {exc}",
                            stage="tool",
                            fallback_reason=(
                                "safe_tool_retries_exhausted"
                                if retryable
                                else "tool_failure_not_retryable"
                            ),
                        ) from exc
                    self._emit(
                        event_sink,
                        "retry",
                        {
                            "tool_name": spec.name,
                            "attempt": attempt + 1,
                            "max_attempts": max_attempts,
                            "reason": str(exc) or type(exc).__name__,
                            "request_id": request_id,
                        },
                    )
            if tool_result is None:
                raise AgentToolError(
                    f"Agent tool {spec.name} failed without a result: {last_error}",
                    stage="tool",
                    fallback_reason="safe_tool_retries_exhausted",
                )

        self._emit(
            event_sink,
            "tool_result",
            {
                "tool_name": tool_result.tool_name,
                "output_text": tool_result.output_text,
                "effect": tool_result.effect,
                "provider": tool_result.provider,
                "model": tool_result.model,
                "request_id": tool_result.request_id,
                "data": tool_result.data or {},
                "duration_ms": _duration_ms(tool_started),
            },
        )
        if spec.effect == "write":
            return ProductAgentRunResult(
                status="completed",
                plan=plan,
                output_text=tool_result.output_text,
                provider=tool_result.provider,
                model=tool_result.model,
                request_id=request_id,
                tool_result=tool_result,
            )

        control.checkpoint("synthesis")
        observation = json.dumps(
            {
                "tool_name": tool_result.tool_name,
                "output_text": tool_result.output_text,
                "data": tool_result.data or {},
            },
            ensure_ascii=False,
        )
        synthesis_started = monotonic()
        answer = self._chat_service.send(
            session_id=str(payload.get("session_id", "agent-session")),
            user_message=str(payload["user_message"]),
            **reading,
            request_id=request_id,
            context_mode="reading",
            tool_name=tool_result.tool_name,
            tool_context=observation,
        )
        control.checkpoint("synthesis_result")
        self._emit(
            event_sink,
            "synthesis_ready",
            {
                "provider": answer.provider,
                "model": answer.model,
                "request_id": answer.request_id,
                "duration_ms": _duration_ms(synthesis_started),
                "prompt_id": str(getattr(self._chat_service, "prompt_id", "") or ""),
            },
        )
        return ProductAgentRunResult(
            status="completed",
            plan=plan,
            output_text=answer.output_text,
            provider=answer.provider,
            model=answer.model,
            request_id=answer.request_id,
            tool_result=tool_result,
        )

    def close(self) -> None:
        planner_close = getattr(self._planner, "close", None)
        if callable(planner_close):
            planner_close()
        chat_close = getattr(self._chat_service, "close", None)
        if callable(chat_close):
            chat_close()
