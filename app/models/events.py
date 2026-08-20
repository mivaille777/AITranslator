"""Application event models shared between input and application layers."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.selection import SelectionContext


@dataclass(frozen=True, slots=True)
class TranslationTriggerEvent:
    """Signal that the user requested a translation action.

    Mouse-selection triggers may carry the immutable context captured at the
    physical mouse-up boundary. Hotkey callers can omit it and keep the legacy
    behavior.
    """

    hotkey: str = "alt+q"
    source: str = "global_hotkey"
    selection_context: SelectionContext | None = None
