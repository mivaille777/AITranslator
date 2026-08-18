"""Application event models shared between input and application layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranslationTriggerEvent:
    """Signal that the user requested a translation action."""

    hotkey: str = "alt+q"
    source: str = "global_hotkey"
