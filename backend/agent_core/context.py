from __future__ import annotations

from dataclasses import asdict
from typing import Any

from backend.agent_core.state import AgentState
from backend.services.reading_context_adapter import to_reading_context
from backend.services.reading_selection_resolver import ReadingSelectionResolver

_EXPLICIT_READING_CONTEXT_FIELDS = (
    "resource_url",
    "resource_title",
    "section_heading",
    "context_before",
    "context_after",
)


class ReadingContextProvider:
    """Enrich AgentState with the existing source-neutral reading pipeline.

    Explicit API context always wins. Native/browser selection resolution is a
    fallback for requests that only contain selected text, preventing a current
    foreground selection from replacing context the caller already froze.
    """

    def __init__(self, resolver: ReadingSelectionResolver | Any | None = None) -> None:
        self._resolver = resolver or ReadingSelectionResolver()

    @staticmethod
    def _has_explicit_context(context: dict[str, Any]) -> bool:
        return any(
            str(context.get(field, "") or "").strip()
            for field in _EXPLICIT_READING_CONTEXT_FIELDS
        )

    def __call__(self, state: AgentState) -> dict[str, Any]:
        context = dict(state.browser_context)
        context["source_text"] = state.selected_text

        if self._has_explicit_context(context):
            return context

        selection = self._resolver.resolve_for_text(state.selected_text)
        if selection is None:
            return context

        if not state.selected_text.strip():
            state.selected_text = selection.text
        reading = to_reading_context(selection)
        context.update(asdict(reading))
        context["source_text"] = state.selected_text
        return context


__all__ = ["ReadingContextProvider"]
