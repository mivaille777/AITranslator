"""Selection-layer components."""

from app.models.selection import SelectedText
from app.selection.base import SelectionProvider
from app.selection.clipboard_provider import ClipboardSelectionProvider
from app.selection.errors import SelectionError
from app.selection.foreground import ForegroundApplicationDetector
from app.selection.manager import SelectionManager
from app.selection.uia_provider import UIASelectionProvider
from app.selection.word_provider import WordSelectionProvider

__all__ = [
    "ClipboardSelectionProvider",
    "SelectedText",
    "SelectionError",
    "ForegroundApplicationDetector",
    "SelectionManager",
    "SelectionProvider",
    "UIASelectionProvider",
    "WordSelectionProvider",
]
