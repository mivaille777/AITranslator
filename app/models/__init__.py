"""Domain models shared by application layers."""

from app.models.events import TranslationTriggerEvent
from app.models.selection import DocumentIdentity, ReadingSelection, SelectedText
from app.models.translation import TranslationRequest, TranslationResult

__all__ = [
    "DocumentIdentity",
    "ReadingSelection",
    "SelectedText",
    "TranslationRequest",
    "TranslationResult",
    "TranslationTriggerEvent",
]
