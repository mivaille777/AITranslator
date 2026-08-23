from __future__ import annotations

from threading import Lock

from backend.rag.model_manager import ModelManager

_model_manager: ModelManager | None = None
_model_manager_lock = Lock()


def get_rag_model_manager() -> ModelManager:
    global _model_manager
    if _model_manager is not None:
        return _model_manager
    with _model_manager_lock:
        if _model_manager is None:
            _model_manager = ModelManager()
        return _model_manager


def close_rag_model_manager() -> None:
    global _model_manager
    with _model_manager_lock:
        _model_manager = None


__all__ = ["close_rag_model_manager", "get_rag_model_manager"]
