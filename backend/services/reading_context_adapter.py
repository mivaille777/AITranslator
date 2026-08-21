"""Application-layer mapping from native reading capture to AI chat context."""

from __future__ import annotations

from app.ai.chat.models import ReadingContext
from app.models.selection import ReadingSelection


def to_reading_context(selection: ReadingSelection) -> ReadingContext:
    """Map rich local capture into the existing prompt-safe ReadingContext.

    Local filesystem paths, executable names and page numbers intentionally stay
    out of the current LLM prompt contract.  They remain available on
    ``selection.document`` for Research/source identity and future Stage 6D API
    work. Browser URLs are already part of the existing ReadingContext contract
    and are preserved.
    """

    document = selection.document
    return ReadingContext(
        resource_url=document.resource_url,
        resource_title=document.resource_title,
        section_heading=selection.section_heading,
        context_before=selection.context_before,
        context_after=selection.context_after,
        source_kind=document.source_kind,
    )


__all__ = ["to_reading_context"]
