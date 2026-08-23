from __future__ import annotations

from typing import Any

from backend.models.agent_runtime import AgentCitationRef, AgentEvidenceItem
from backend.rag.context_builder import GroundedContextBuilder
from backend.services.companion_chat_service import CompanionChatResult

NO_KNOWLEDGE_EVIDENCE_MESSAGE = "知识库未找到足够相关证据。"


class GroundedSynthesisService:
    """Grounded synthesis policy over the existing agent_synthesis chat path."""

    def __init__(
        self,
        *,
        chat_service: Any,
        context_builder: GroundedContextBuilder | None = None,
        allow_general_without_evidence: bool = False,
    ) -> None:
        self._chat_service = chat_service
        self._context_builder = context_builder or GroundedContextBuilder()
        self._allow_general_without_evidence = allow_general_without_evidence

    @property
    def prompt_id(self) -> str:
        return str(getattr(self._chat_service, "prompt_id", "") or "")

    def send(
        self,
        *,
        evidence: list[AgentEvidenceItem],
        citations: list[AgentCitationRef],
        **kwargs: Any,
    ) -> CompanionChatResult:
        if not evidence:
            if self._allow_general_without_evidence:
                return self._chat_service.send(**kwargs)
            return CompanionChatResult(
                session_id=str(
                    kwargs.get("session_id", "agent-session") or "agent-session"
                ),
                user_message=str(kwargs.get("user_message", "") or ""),
                output_text=NO_KNOWLEDGE_EVIDENCE_MESSAGE,
                provider="policy",
                model="no-evidence",
                request_id=max(0, int(kwargs.get("request_id", 0) or 0)),
            )

        context = self._context_builder.build(evidence, citations)
        if not context.included_evidence_ids:
            return CompanionChatResult(
                session_id=str(
                    kwargs.get("session_id", "agent-session") or "agent-session"
                ),
                user_message=str(kwargs.get("user_message", "") or ""),
                output_text=NO_KNOWLEDGE_EVIDENCE_MESSAGE,
                provider="policy",
                model="context-budget",
                request_id=max(0, int(kwargs.get("request_id", 0) or 0)),
            )
        payload = dict(kwargs)
        payload["tool_name"] = "search_knowledge_base"
        payload["tool_context"] = context.text
        return self._chat_service.send(**payload)

    def close(self) -> None:
        close = getattr(self._chat_service, "close", None)
        if callable(close):
            close()


__all__ = ["NO_KNOWLEDGE_EVIDENCE_MESSAGE", "GroundedSynthesisService"]
