"""Selection-layer components."""

from app.models.selection import DocumentIdentity, ReadingSelection, SelectedText
from app.selection.base import SelectionProvider
from app.selection.clipboard_provider import ClipboardSelectionProvider
from app.selection.errors import SelectionError
from app.selection.foreground import ForegroundApplicationDetector
from app.selection.manager import SelectionManager
from app.selection.reading_context import (
    browser_snapshot_to_reading_selection,
    reading_selection_from_selected_text,
)
from app.selection.uia_provider import UIASelectionProvider
from app.selection.word_provider import WordSelectionProvider

__all__ = [
    "ClipboardSelectionProvider",
    "DocumentIdentity",
    "ForegroundApplicationDetector",
    "ReadingSelection",
    "SelectedText",
    "SelectionError",
    "SelectionManager",
    "SelectionProvider",
    "UIASelectionProvider",
    "WordSelectionProvider",
    "browser_snapshot_to_reading_selection",
    "reading_selection_from_selected_text",
]
