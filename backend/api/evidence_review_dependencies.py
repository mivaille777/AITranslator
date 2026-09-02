from __future__ import annotations

from threading import Lock

from backend.api.evidence_ledger_dependencies import get_evidence_ledger_service
from backend.services.evidence_review_service import EvidenceReviewService

_service: EvidenceReviewService | None = None
_lock = Lock()


def get_evidence_review_service() -> EvidenceReviewService:
    global _service
    if _service is not None:
        return _service
    with _lock:
        if _service is None:
            _service = EvidenceReviewService(ledger_service=get_evidence_ledger_service())
        return _service


def close_evidence_review_service() -> None:
    global _service
    with _lock:
        _service = None


__all__ = ["close_evidence_review_service", "get_evidence_review_service"]
