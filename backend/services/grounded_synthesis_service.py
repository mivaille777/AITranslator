from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.models.agent_runtime import AgentCitationRef, AgentEvidenceItem
from backend.rag.context_builder import GroundedContext, GroundedContextBuilder
from backend.services.agent_claim_evidence_verifier import (
    AgentClaimEvidenceVerifier,
    ClaimEvidenceVerification,
)
from backend.services.companion_chat_service import CompanionChatResult

NO_KNOWLEDGE_EVIDENCE_MESSAGE = "知识库未找到足够相关证据。"
GROUNDING_VERIFICATION_FALLBACK_PREFIX = (
    "原始回答未通过引用与证据一致性校验。以下仅保留可直接核验的证据："
)


@dataclass(frozen=True, slots=True)
class VerifiedGroundedSynthesisResult:
    answer: CompanionChatResult
    verification: ClaimEvidenceVerification | None = None
    fallback_applied: bool = False


class GroundedSynthesisService:
    """Grounded synthesis plus deterministic post-generation verification."""

    def __init__(
        self,
        *,
        chat_service: Any,
        context_builder: GroundedContextBuilder | None = None,
        verifier: AgentClaimEvidenceVerifier | Any | None = None,
        allow_general_without_evidence: bool = False,
    ) -> None:
        self._chat_service = chat_service
        self._context_builder = context_builder or GroundedContextBuilder()
        self._verifier = verifier or AgentClaimEvidenceVerifier()
        self._allow_general_without_evidence = allow_general_without_evidence

    @property
    def prompt_id(self) -> str:
        return str(getattr(self._chat_service, "prompt_id", "") or "")

    @staticmethod
    def _policy_answer(
        kwargs: dict[str, Any],
        *,
        output_text: str,
        model: str,
    ) -> CompanionChatResult:
        return CompanionChatResult(
            session_id=str(kwargs.get("session_id", "agent-session") or "agent-session"),
            user_message=str(kwargs.get("user_message", "") or ""),
            output_text=output_text,
            provider="policy",
            model=model,
            request_id=max(0, int(kwargs.get("request_id", 0) or 0)),
        )

    @staticmethod
    def _included_grounding(
        context: GroundedContext,
        evidence: list[AgentEvidenceItem],
        citations: list[AgentCitationRef],
    ) -> tuple[list[AgentEvidenceItem], list[AgentCitationRef]]:
        included_ids = set(context.included_evidence_ids)
        included_evidence = [
            item for item in evidence if item.evidence_id in included_ids
        ]
        available_ids = {item.evidence_id for item in included_evidence}
        included_citations = [
            AgentCitationRef(
                citation_id=item.citation_id,
                evidence_ids=[
                    evidence_id
                    for evidence_id in item.evidence_ids
                    if evidence_id in available_ids
                ],
                label=item.label,
            )
            for item in citations
            if any(evidence_id in available_ids for evidence_id in item.evidence_ids)
        ]
        return included_evidence, included_citations

    @staticmethod
    def _evidence_only_fallback(
        *,
        evidence: list[AgentEvidenceItem],
        citations: list[AgentCitationRef],
    ) -> str:
        citation_by_evidence: dict[str, str] = {}
        for citation in citations:
            for evidence_id in citation.evidence_ids:
                citation_by_evidence.setdefault(evidence_id, citation.label)

        lines = [GROUNDING_VERIFICATION_FALLBACK_PREFIX]
        for item in evidence[:5]:
            excerpt = " ".join(item.excerpt.strip().split())
            if not excerpt:
                continue
            label = citation_by_evidence.get(item.evidence_id, "")
            location = f"（{item.location}）" if item.location else ""
            lines.append(f"- {excerpt}{location} {label}".rstrip())
        if len(lines) == 1:
            return NO_KNOWLEDGE_EVIDENCE_MESSAGE
        return "\n".join(lines)

    def send_verified(
        self,
        *,
        evidence: list[AgentEvidenceItem],
        citations: list[AgentCitationRef],
        **kwargs: Any,
    ) -> VerifiedGroundedSynthesisResult:
        if not evidence:
            if self._allow_general_without_evidence:
                return VerifiedGroundedSynthesisResult(
                    answer=self._chat_service.send(**kwargs)
                )
            return VerifiedGroundedSynthesisResult(
                answer=self._policy_answer(
                    kwargs,
                    output_text=NO_KNOWLEDGE_EVIDENCE_MESSAGE,
                    model="no-evidence",
                )
            )

        context = self._context_builder.build(evidence, citations)
        if not context.included_evidence_ids:
            return VerifiedGroundedSynthesisResult(
                answer=self._policy_answer(
                    kwargs,
                    output_text=NO_KNOWLEDGE_EVIDENCE_MESSAGE,
                    model="context-budget",
                )
            )

        included_evidence, included_citations = self._included_grounding(
            context, evidence, citations
        )
        payload = dict(kwargs)
        payload["tool_name"] = "search_knowledge_base"
        payload["tool_context"] = context.text
        answer = self._chat_service.send(**payload)
        verification = self._verifier.verify(
            output_text=answer.output_text,
            evidence=included_evidence,
            citations=included_citations,
        )
        if verification.passed:
            return VerifiedGroundedSynthesisResult(
                answer=answer,
                verification=verification,
            )

        fallback = CompanionChatResult(
            session_id=answer.session_id,
            user_message=answer.user_message,
            output_text=self._evidence_only_fallback(
                evidence=included_evidence,
                citations=included_citations,
            ),
            provider="policy",
            model="grounding-verification-fallback",
            request_id=answer.request_id,
        )
        return VerifiedGroundedSynthesisResult(
            answer=fallback,
            verification=verification,
            fallback_applied=True,
        )

    def send(
        self,
        *,
        evidence: list[AgentEvidenceItem],
        citations: list[AgentCitationRef],
        **kwargs: Any,
    ) -> CompanionChatResult:
        """Backward-compatible grounded synthesis entry point."""

        return self.send_verified(
            evidence=evidence,
            citations=citations,
            **kwargs,
        ).answer

    def close(self) -> None:
        close = getattr(self._chat_service, "close", None)
        if callable(close):
            close()


__all__ = [
    "GROUNDING_VERIFICATION_FALLBACK_PREFIX",
    "NO_KNOWLEDGE_EVIDENCE_MESSAGE",
    "GroundedSynthesisService",
    "VerifiedGroundedSynthesisResult",
]
