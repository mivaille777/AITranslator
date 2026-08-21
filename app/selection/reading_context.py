"""Adapters between selection providers and source-neutral reading context.

Stage 6C keeps document capture richer than the LLM prompt contract.  Local
file paths and application identifiers stay in :class:`DocumentIdentity`; only
prompt-safe fields are mapped into the existing :class:`ReadingContext` model.
"""

from __future__ import annotations

from typing import Any

from app.ai.chat.models import ReadingContext
from app.models.selection import (
    DocumentIdentity,
    ReadingSelection,
    SelectedText,
    SelectionContext,
)


def normalize_application_name(value: object) -> str:
    """Return a bounded executable/application label from a captured process."""

    return str(value or "").replace("\\", "/").rsplit("/", 1)[-1].strip()


def source_kind_for_provider(provider: object) -> str:
    """Map selection-provider labels to the shared research source families."""

    value = str(provider or "").strip().casefold()
    if value == "word" or value.startswith("word_"):
        return "word"
    if value in {"browser_bridge", "browser_pdf_uia"} or value.startswith("browser_"):
        return "browser"
    if "pdf" in value:
        return "pdf"
    if value:
        return "desktop"
    return "other"


def reading_selection_from_selected_text(
    selected: SelectedText,
    *,
    context: SelectionContext | None = None,
    source_kind: str | None = None,
) -> ReadingSelection:
    """Upgrade a legacy selection with only metadata that is actually known."""

    application = normalize_application_name(
        context.process_name if context is not None else ""
    )
    return ReadingSelection(
        text=selected.text,
        provider=selected.provider,
        document=DocumentIdentity(
            source_kind=source_kind or source_kind_for_provider(selected.provider),
            application=application,
        ),
    )


def browser_snapshot_to_reading_selection(
    snapshot: Any,
    *,
    process_name: object = "",
) -> ReadingSelection:
    """Convert a validated browser bridge snapshot without inventing metadata."""

    text = str(getattr(snapshot, "text", "") or "")
    return ReadingSelection(
        text=text,
        provider="browser_bridge",
        document=DocumentIdentity(
            source_kind="browser",
            resource_url=str(getattr(snapshot, "url", "") or "").strip(),
            resource_title=str(getattr(snapshot, "title", "") or "").strip(),
            application=normalize_application_name(process_name),
        ),
        section_heading=str(getattr(snapshot, "heading", "") or "").strip(),
        context_before=str(getattr(snapshot, "context_before", "") or "").strip(),
        context_after=str(getattr(snapshot, "context_after", "") or "").strip(),
    )


def reading_selection_to_context(selection: ReadingSelection) -> ReadingContext:
    """Map rich local capture into the existing prompt-safe ReadingContext.

    ``resource_path``, ``application`` and ``page_number`` intentionally remain
    local at this stage.  Stage 6D can decide which of those fields should be
    surfaced in API/UI contracts.  A browser URL is already part of the
    existing ReadingContext contract and is therefore preserved.
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


__all__ = [
    "browser_snapshot_to_reading_selection",
    "normalize_application_name",
    "reading_selection_from_selected_text",
    "reading_selection_to_context",
    "source_kind_for_provider",
]
