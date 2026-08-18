"""Domain models shared by application layers."""

from app.models.events import TranslationTriggerEvent
from app.models.selection import SelectedText
from app.models.translation import TranslationRequest, TranslationResult

__all__ = [
    "SelectedText",
    "TranslationRequest",
    "TranslationResult",
    "TranslationTriggerEvent",
]
