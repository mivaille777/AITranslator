from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from backend.models.agent_runtime import AgentCitationRef, AgentEvidenceItem

_CITATION_RE = re.compile(r"\[(\d+)\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？；;])\s+|\n+")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")

_STOPWORDS = {
    "the",
    "and",
    "for",
    "from",
    "with",
    "that",
    "this",
    "are",
    "was",
    "were",
    "into",
    "than",
    "then",
    "have",
    "has",
    "had",
    "can",
    "could",
    "would",
    "should",
    "about",
    "based",
    "using",
    "use",
    "根据",
    "可以",
    "以及",
    "一个",
    "这种",
    "这些",
    "其中",
}


@dataclass(frozen=True, slots=True)
class ClaimEvidenceVerification:
    passed: bool
    claim_count: int
    cited_claim_count: int
    supported_claim_count: int
    unsupported_claim_count: int
    invalid_citation_count: int
    citation_coverage: float
    support_rate: float
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClaimEvidenceVerifierPolicy:
    minimum_claim_chars: int = 12
    minimum_support_score: float = 0.22
    minimum_citation_coverage: float = 1.0
    minimum_support_rate: float = 1.0

    def __post_init__(self) -> None:
        if self.minimum_claim_chars < 1:
            raise ValueError("minimum_claim_chars must be positive")
        for name, value in (
            ("minimum_support_score", self.minimum_support_score),
            ("minimum_citation_coverage", self.minimum_citation_coverage),
            ("minimum_support_rate", self.minimum_support_rate),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")


class AgentClaimEvidenceVerifier:
    """Deterministically verify citation coverage and lexical evidence support.

    This is deliberately a conservative grounding gate rather than a semantic
    entailment model. It validates only observable invariants: factual-looking
    claims must cite allow-listed citations, cited evidence must exist, and the
    claim must share enough informative lexical material with at least one cited
    evidence item. No private model reasoning is generated or persisted.
    """

    def __init__(self, policy: ClaimEvidenceVerifierPolicy | None = None) -> None:
        self.policy = policy or ClaimEvidenceVerifierPolicy()

    @staticmethod
    def _strip_citations(text: str) -> str:
        return _CITATION_RE.sub("", text).strip(" \t-*•#:")

    @staticmethod
    def _tokens(text: str) -> set[str]:
        tokens: set[str] = set()
        cjk: list[str] = []
        for raw in _WORD_RE.findall(str(text or "")):
            if len(raw) == 1 and "\u4e00" <= raw <= "\u9fff":
                cjk.append(raw)
                continue
            token = raw.lower()
            if len(token) >= 2 and token not in _STOPWORDS:
                tokens.add(token)
        compact_cjk = "".join(cjk)
        if len(compact_cjk) >= 2:
            tokens.update(
                compact_cjk[index : index + 2]
                for index in range(len(compact_cjk) - 1)
            )
        return tokens

    def _claims(self, output_text: str) -> tuple[str, ...]:
        claims: list[str] = []
        for raw in _SENTENCE_SPLIT_RE.split(str(output_text or "")):
            candidate = raw.strip()
            body = self._strip_citations(candidate)
            compact = re.sub(r"\s+", "", body)
            if len(compact) < self.policy.minimum_claim_chars:
                continue
            if not self._tokens(body):
                continue
            claims.append(candidate)
        return tuple(claims)

    @staticmethod
    def _citation_map(
        citations: Sequence[AgentCitationRef],
    ) -> dict[str, tuple[str, ...]]:
        return {
            citation.label.strip(): tuple(citation.evidence_ids)
            for citation in citations
            if citation.label.strip()
        }

    @staticmethod
    def _evidence_map(
        evidence: Sequence[AgentEvidenceItem],
    ) -> dict[str, AgentEvidenceItem]:
        return {
            item.evidence_id: item
            for item in evidence
            if item.evidence_id
        }

    def _support_score(self, claim: str, item: AgentEvidenceItem) -> float:
        claim_tokens = self._tokens(self._strip_citations(claim))
        evidence_tokens = self._tokens(
            " ".join((item.title, item.location, item.excerpt))
        )
        if not claim_tokens or not evidence_tokens:
            return 0.0
        overlap = len(claim_tokens & evidence_tokens)
        return overlap / max(1, len(claim_tokens))

    def verify(
        self,
        *,
        output_text: str,
        evidence: Sequence[AgentEvidenceItem],
        citations: Sequence[AgentCitationRef],
    ) -> ClaimEvidenceVerification:
        claims = self._claims(output_text)
        citation_map = self._citation_map(citations)
        evidence_map = self._evidence_map(evidence)

        cited_claims = 0
        supported_claims = 0
        invalid_citations = 0
        reasons: set[str] = set()

        for claim in claims:
            labels = tuple(
                dict.fromkeys(f"[{match}]" for match in _CITATION_RE.findall(claim))
            )
            if not labels:
                reasons.add("missing_claim_citation")
                continue
            cited_claims += 1

            referenced: list[AgentEvidenceItem] = []
            invalid_for_claim = False
            for label in labels:
                evidence_ids = citation_map.get(label)
                if not evidence_ids:
                    invalid_citations += 1
                    invalid_for_claim = True
                    reasons.add("unknown_citation")
                    continue
                for evidence_id in evidence_ids:
                    item = evidence_map.get(evidence_id)
                    if item is None:
                        invalid_citations += 1
                        invalid_for_claim = True
                        reasons.add("citation_missing_evidence")
                    else:
                        referenced.append(item)

            if invalid_for_claim or not referenced:
                continue
            if max(self._support_score(claim, item) for item in referenced) >= self.policy.minimum_support_score:
                supported_claims += 1
            else:
                reasons.add("weak_claim_evidence_overlap")

        claim_count = len(claims)
        if claim_count == 0:
            reasons.add("no_verifiable_claims")
        citation_coverage = (
            cited_claims / claim_count if claim_count else 0.0
        )
        support_rate = (
            supported_claims / claim_count if claim_count else 0.0
        )
        if citation_coverage < self.policy.minimum_citation_coverage:
            reasons.add("citation_coverage_below_policy")
        if support_rate < self.policy.minimum_support_rate:
            reasons.add("claim_support_below_policy")

        passed = (
            claim_count > 0
            and invalid_citations == 0
            and citation_coverage >= self.policy.minimum_citation_coverage
            and support_rate >= self.policy.minimum_support_rate
        )
        return ClaimEvidenceVerification(
            passed=passed,
            claim_count=claim_count,
            cited_claim_count=cited_claims,
            supported_claim_count=supported_claims,
            unsupported_claim_count=max(0, claim_count - supported_claims),
            invalid_citation_count=invalid_citations,
            citation_coverage=round(citation_coverage, 4),
            support_rate=round(support_rate, 4),
            reason_codes=tuple(sorted(reasons)),
        )


__all__ = [
    "AgentClaimEvidenceVerifier",
    "ClaimEvidenceVerification",
    "ClaimEvidenceVerifierPolicy",
]
