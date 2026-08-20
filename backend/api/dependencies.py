from __future__ import annotations

from threading import Lock

from backend.services.translation_service import TranslationService

_translation_service: TranslationService | None = None
_translation_service_lock = Lock()


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
