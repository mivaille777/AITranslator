from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.models.evidence_ledger import EvidenceLedgerItem

EvidenceReviewStatus = Literal["unreviewed", "accepted", "rejected", "needs_review"]
LiteratureSynthesisBucket = Literal["consensus", "disagreement", "excluded"]


class EvidenceReviewContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceReview(EvidenceReviewContract):
    entry_id: str = Field(min_length=1, max_length=128)
    workspace_id: str = Field(min_length=1, max_length=128)
    status: EvidenceReviewStatus
    note: str = Field(default="", max_length=4000)
    reviewed_at: str = Field(default="", max_length=64)
    updated_at: str = Field(default="", max_length=64)


class EvidenceReviewUpdateRequest(EvidenceReviewContract):
    status: EvidenceReviewStatus
    note: str = Field(default="", max_length=4000)


class ReviewedEvidenceLedgerItem(EvidenceReviewContract):
    ledger: EvidenceLedgerItem
    review: EvidenceReview


class EvidenceReviewSnapshot(EvidenceReviewContract):
    workspace_id: str = Field(min_length=1, max_length=128)
    query: str = Field(default="", max_length=4000)
    entry_count: int = Field(default=0, ge=0)
    unreviewed_count: int = Field(default=0, ge=0)
    accepted_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    needs_review_count: int = Field(default=0, ge=0)
    items: list[ReviewedEvidenceLedgerItem] = Field(default_factory=list, max_length=256)


class LiteratureSynthesisRequest(EvidenceReviewContract):
    query: str = Field(default="", max_length=4000)


class LiteratureSynthesisItem(EvidenceReviewContract):
    entry_id: str = Field(min_length=1, max_length=128)
    statement: str = Field(min_length=1, max_length=4000)
    machine_status: str = Field(min_length=1, max_length=32)
    review_status: EvidenceReviewStatus
    bucket: LiteratureSynthesisBucket
    reason: str = Field(default="", max_length=256)
    document_ids: list[str] = Field(default_factory=list, max_length=256)
    evidence_ids: list[str] = Field(default_factory=list, max_length=512)


class LiteratureSynthesisPlan(EvidenceReviewContract):
    workspace_id: str = Field(min_length=1, max_length=128)
    query: str = Field(default="", max_length=4000)
    included_count: int = Field(default=0, ge=0)
    excluded_count: int = Field(default=0, ge=0)
    consensus: list[LiteratureSynthesisItem] = Field(default_factory=list, max_length=256)
    disagreements: list[LiteratureSynthesisItem] = Field(default_factory=list, max_length=256)
    excluded: list[LiteratureSynthesisItem] = Field(default_factory=list, max_length=256)
    draft_markdown: str = Field(default="", max_length=60000)


__all__ = [
    "EvidenceReview",
    "EvidenceReviewSnapshot",
    "EvidenceReviewStatus",
    "EvidenceReviewUpdateRequest",
    "LiteratureSynthesisItem",
    "LiteratureSynthesisPlan",
    "LiteratureSynthesisRequest",
    "ReviewedEvidenceLedgerItem",
]
