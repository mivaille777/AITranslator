from __future__ import annotations

from dataclasses import asdict
from typing import Any

from backend.agent_core.state import AgentState
from backend.services.reading_context_adapter import to_reading_context
from backend.services.reading_selection_resolver import ReadingSelectionResolver


class ReadingContextProvider:
    """Enrich :class:`AgentState` from the existing reading selection pipeline.

    The provider deliberately delegates source capture and normalization to the
    current services.  Agent Core only owns the state mapping so browser, PDF,
    Word and UIA capture behavior cannot drift from the rest of the product.
    """

    def __init__(self, resolver: ReadingSelectionResolver | Any | None = None) -> None:
        self._resolver = resolver or ReadingSelectionResolver()

    def __call__(self, state: AgentState) -> dict[str, Any]:
        context = dict(state.browser_context)
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
