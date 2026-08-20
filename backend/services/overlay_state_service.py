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
    resource_url: str = ""
    resource_title: str = ""
    section_heading: str = ""
    context_before: str = ""
    context_after: str = ""
    source_kind: str = "browser_selection"


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
        resource_url: str = "",
        resource_title: str = "",
        section_heading: str = "",
        context_before: str = "",
        context_after: str = "",
        source_kind: str = "browser_selection",
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
                resource_url=resource_url,
                resource_title=resource_title,
                section_heading=section_heading,
                context_before=context_before,
                context_after=context_after,
                source_kind=source_kind,
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
        resource_url: str = "",
        resource_title: str = "",
        section_heading: str = "",
        context_before: str = "",
        context_after: str = "",
        source_kind: str = "browser_selection",
    ) -> OverlayState:
        with self._lock:
            if self._state.context_id and context_id != self._state.context_id:
                return self._state
            current = self._state
            self._state = OverlayState(
                revision=current.revision + 1,
                visible=True,
                phase="ready",
                context_id=context_id,
                source_text=source_text,
                translated_text=translated_text,
                source_language=source_language,
                target_language=target_language,
                provider=provider,
                resource_url=resource_url or current.resource_url,
                resource_title=resource_title or current.resource_title,
                section_heading=section_heading or current.section_heading,
                context_before=context_before or current.context_before,
                context_after=context_after or current.context_after,
                source_kind=source_kind or current.source_kind,
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
        resource_url: str = "",
        resource_title: str = "",
        section_heading: str = "",
        context_before: str = "",
        context_after: str = "",
        source_kind: str = "browser_selection",
    ) -> OverlayState:
        with self._lock:
            if self._state.context_id and context_id != self._state.context_id:
                return self._state
            current = self._state
            self._state = OverlayState(
                revision=current.revision + 1,
                visible=True,
                phase="error",
                context_id=context_id,
                source_text=source_text,
                source_language=source_language,
                target_language=target_language,
                message=message or "Translation failed",
                resource_url=resource_url or current.resource_url,
                resource_title=resource_title or current.resource_title,
                section_heading=section_heading or current.section_heading,
                context_before=context_before or current.context_before,
                context_after=context_after or current.context_after,
                source_kind=source_kind or current.source_kind,
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
