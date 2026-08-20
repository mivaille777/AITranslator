from __future__ import annotations

from threading import Lock

from backend.services.browser_context_service import BrowserContextService
from backend.services.overlay_state_service import OverlayStateService
from backend.services.quick_action_service import QuickActionService
from backend.services.research_note_service import ResearchNoteService
from backend.services.translation_service import TranslationService

_translation_service: TranslationService | None = None
_translation_service_lock = Lock()
_browser_context_service: BrowserContextService | None = None
_browser_context_service_lock = Lock()
_overlay_state_service: OverlayStateService | None = None
_overlay_state_service_lock = Lock()
_quick_action_service: QuickActionService | None = None
_quick_action_service_lock = Lock()
_research_note_service: ResearchNoteService | None = None
_research_note_service_lock = Lock()


def get_translation_service() -> TranslationService:
    global _translation_service
    if _translation_service is not None:
        return _translation_service

    with _translation_service_lock:
        if _translation_service is None:
            _translation_service = TranslationService()
        return _translation_service


def close_translation_service() -> None:
    global _translation_service
    with _translation_service_lock:
        service = _translation_service
        _translation_service = None
    if service is not None:
        service.close()


def get_browser_context_service() -> BrowserContextService:
    global _browser_context_service
    if _browser_context_service is not None:
        return _browser_context_service

    with _browser_context_service_lock:
        if _browser_context_service is None:
            _browser_context_service = BrowserContextService()
        return _browser_context_service


def close_browser_context_service() -> None:
    global _browser_context_service
    with _browser_context_service_lock:
        service = _browser_context_service
        _browser_context_service = None
    if service is not None:
        service.close()


def get_overlay_state_service() -> OverlayStateService:
    global _overlay_state_service
    if _overlay_state_service is not None:
        return _overlay_state_service

    with _overlay_state_service_lock:
        if _overlay_state_service is None:
            _overlay_state_service = OverlayStateService()
        return _overlay_state_service


def get_quick_action_service() -> QuickActionService:
    global _quick_action_service
    if _quick_action_service is not None:
        return _quick_action_service

    with _quick_action_service_lock:
        if _quick_action_service is None:
            _quick_action_service = QuickActionService()
        return _quick_action_service


def close_quick_action_service() -> None:
    global _quick_action_service
    with _quick_action_service_lock:
        service = _quick_action_service
        _quick_action_service = None
    if service is not None:
        service.close()


def get_research_note_service() -> ResearchNoteService:
    global _research_note_service
    if _research_note_service is not None:
        return _research_note_service

    with _research_note_service_lock:
        if _research_note_service is None:
            _research_note_service = ResearchNoteService()
        return _research_note_service
