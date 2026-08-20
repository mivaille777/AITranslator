from __future__ import annotations

from dataclasses import dataclass, replace
from threading import RLock


@dataclass(frozen=True, slots=True)
class OverlayState:
    revision: int = 0
    visible: bool = False
    phase: str = "hidden"
    context_id: str = ""
    source_text: str = ""
    translated_text: str = ""
    source_language: str = "auto"
    target_language: str = "zh-CN"
    provider: str = ""
    message: str = ""


class OverlayStateService:
    """Thread-safe presentation state shared by the main and overlay webviews."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state = OverlayState()

    def snapshot(self) -> OverlayState:
        with self._lock:
            return self._state

    def show_loading(
        self,
        *,
        context_id: str,
        source_text: str,
        source_language: str,
        target_language: str,
    ) -> OverlayState:
        with self._lock:
            self._state = OverlayState(
                revision=self._state.revision + 1,
                visible=True,
                phase="loading",
                context_id=context_id,
                source_text=source_text,
                source_language=source_language,
                target_language=target_language,
                message="Translating…",
            )
            return self._state

    def show_translation(
        self,
        *,
        context_id: str,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        provider: str,
    ) -> OverlayState:
        with self._lock:
            if self._state.context_id and context_id != self._state.context_id:
                return self._state
            self._state = OverlayState(
                revision=self._state.revision + 1,
                visible=True,
                phase="ready",
                context_id=context_id,
                source_text=source_text,
                translated_text=translated_text,
                source_language=source_language,
                target_language=target_language,
                provider=provider,
            )
            return self._state

    def show_error(
        self,
        *,
        context_id: str,
        source_text: str,
        source_language: str,
        target_language: str,
        message: str,
    ) -> OverlayState:
        with self._lock:
            if self._state.context_id and context_id != self._state.context_id:
                return self._state
            self._state = OverlayState(
                revision=self._state.revision + 1,
                visible=True,
                phase="error",
                context_id=context_id,
                source_text=source_text,
                source_language=source_language,
                target_language=target_language,
                message=message or "Translation failed",
            )
            return self._state

    def dismiss(self) -> OverlayState:
        with self._lock:
            self._state = replace(
                self._state,
                revision=self._state.revision + 1,
                visible=False,
                phase="hidden",
            )
            return self._state
