from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from backend.models.agent_tools import AgentPlan
from backend.services.agent_planner_service import AgentPlannerService
from backend.services.agent_tool_registry import (
    AgentToolExecutionResult,
    AgentToolRegistry,
)
from backend.services.companion_chat_service import CompanionChatService

_ALLOWED_PLANNER_ARGUMENTS = frozenset({"target_language", "style", "user_note"})


@dataclass(frozen=True, slots=True)
class ProductAgentRunResult:
    status: str
    plan: AgentPlan
    output_text: str = ""
    provider: str = ""
    model: str = ""
    request_id: int = 0
    tool_result: AgentToolExecutionResult | None = None


class ProductAgentService:
    """Bounded Plan -> Validate -> Execute -> Synthesize agent loop.

    Tool execution is always delegated to AgentToolRegistry. Planner output can
    select only registered tools and can override only a small allow-list of
    non-sensitive arguments. Write tools stop at a confirmation gate unless the
    caller explicitly confirms that tool for the current request.
    """

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

    def run(self, **payload: Any) -> ProductAgentRunResult:
        reading = self._reading_fields(payload)
        tools = self._registry.list_tools()
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
        request_id = max(0, int(payload.get("request_id", 0) or 0))

        if plan.action == "answer":
            answer = self._chat_service.send(
                session_id=str(payload.get("session_id", "agent-session")),
                user_message=str(payload["user_message"]),
                **reading,
                request_id=request_id,
                context_mode="reading",
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

        tool_result = self._registry.execute(spec.name, **execution_payload)
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

        observation = json.dumps(
            {
                "tool_name": tool_result.tool_name,
                "output_text": tool_result.output_text,
                "data": tool_result.data or {},
            },
            ensure_ascii=False,
        )
        answer = self._chat_service.send(
            session_id=str(payload.get("session_id", "agent-session")),
            user_message=str(payload["user_message"]),
            **reading,
            request_id=request_id,
            context_mode="reading",
            tool_name=tool_result.tool_name,
            tool_context=observation,
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
        close = getattr(self._planner, "close", None)
        if callable(close):
            close()
