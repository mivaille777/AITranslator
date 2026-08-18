"""Selection provider abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.selection import SelectedText
from app.selection.errors import SelectionError


class SelectionProvider(ABC):
    """Return selected text without knowing about translation or the UI."""

    @abstractmethod
    def get_selected_text(self) -> SelectedText:
        """Read the current foreground selection."""


__all__ = ["SelectedText", "SelectionError", "SelectionProvider"]
