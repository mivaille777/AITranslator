"""Source-neutral adapters for richer selection capture.

This module deliberately stays below the AI/chat layer.  It can enrich legacy
``SelectedText`` values and browser snapshots, but it does not decide what
metadata is safe or useful to send to an LLM.
"""

from __future__ import annotations

from typing import Any

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


__all__ = [
    "browser_snapshot_to_reading_selection",
    "normalize_application_name",
    "reading_selection_from_selected_text",
    "source_kind_for_provider",
]
