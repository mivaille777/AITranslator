from __future__ import annotations

from dataclasses import dataclass, replace
from threading import RLock


@dataclass(frozen=True, slots=True)
class OverlayState:
    revision: int = 0
    visible: bool = False
    mode: str = "assistant"
    phase: str = "hidden"
    context_id: str = ""
    source_text: str = ""
    translated_text: str = ""
    source_language: str = "auto"
    target_language: str = "zh-CN"
    provider: str = ""
    message: str = ""
    translation_notice: str = ""
    resource_url: str = ""
    resource_title: str = ""
    section_heading: str = ""
    context_before: str = ""
    context_after: str = ""
    source_kind: str = "browser_selection"
    companion_conversation_id: str = ""


class OverlayStateService:
    """Thread-safe presentation state shared by the main and overlay webviews."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state = OverlayState()

    def snapshot(self) -> OverlayState:
        with self._lock:
            return self._state

    def switch_mode(self, *, context_id: str, mode: str) -> OverlayState:
        """Switch presentation without resetting the reading interaction."""
        normalized_context_id = str(context_id or "").strip()
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode not in {"assistant", "translation"}:
            raise ValueError("Unsupported overlay mode.")

        with self._lock:
            current = self._state
            if not normalized_context_id or normalized_context_id != current.context_id:
                raise ValueError("Overlay context changed before mode switch.")

            if normalized_mode == "assistant":
                phase = "ready"
            elif current.translated_text:
                phase = "ready"
            elif current.phase in {"loading", "error"}:
                phase = current.phase
            else:
                phase = "ready"

            if current.mode == normalized_mode and current.phase == phase and current.visible:
                return current

            self._state = replace(
                current,
                revision=current.revision + 1,
                visible=True,
                mode=normalized_mode,
                phase=phase,
            )
            return self._state

    def show_assistant(
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
        """Open a fresh external selection in AI Assistant mode.

        A new selection is a new interaction boundary: stale translation output,
        provider notices and previous conversation bindings are deliberately
        cleared. The selected text remains the frozen reading source for tools.
        """
        with self._lock:
            current = self._state
            same_context = current.context_id == context_id
            self._state = OverlayState(
                revision=current.revision + 1,
                visible=True,
                mode="assistant",
                phase="ready",
                context_id=context_id,
                source_text=source_text,
                source_language=source_language,
                target_language=target_language,
                resource_url=resource_url,
                resource_title=resource_title,
                section_heading=section_heading,
                context_before=context_before,
                context_after=context_after,
                source_kind=source_kind,
                companion_conversation_id=(
                    current.companion_conversation_id if same_context else ""
                ),
            )
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
            current = self._state
            companion_conversation_id = (
                current.companion_conversation_id
                if current.context_id == context_id
                else ""
            )
            self._state = OverlayState(
                revision=current.revision + 1,
                visible=True,
                mode="translation",
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
                companion_conversation_id=companion_conversation_id,
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
        translation_notice: str = "",
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
                mode="translation",
                phase="ready",
                context_id=context_id,
                source_text=source_text,
                translated_text=translated_text,
                source_language=source_language,
                target_language=target_language,
                provider=provider,
                translation_notice=translation_notice,
                resource_url=resource_url or current.resource_url,
                resource_title=resource_title or current.resource_title,
                section_heading=section_heading or current.section_heading,
                context_before=context_before or current.context_before,
                context_after=context_after or current.context_after,
                source_kind=source_kind or current.source_kind,
                companion_conversation_id=current.companion_conversation_id,
            )
            return self._state

    def show_translation_failure(
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
        """Report translation failure without unmounting the AI conversation."""
        with self._lock:
            if self._state.context_id and context_id != self._state.context_id:
                return self._state
            current = self._state
            normalized_message = message or "Translation failed"
            self._state = replace(
                current,
                revision=current.revision + 1,
                visible=True,
                mode="translation",
                phase="ready",
                context_id=context_id,
                source_text=source_text or current.source_text,
                source_language=source_language or current.source_language,
                target_language=target_language or current.target_language,
                message=normalized_message,
                translation_notice=f"翻译暂时不可用：{normalized_message}",
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
                mode="translation",
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
                companion_conversation_id=current.companion_conversation_id,
            )
            return self._state

    def bind_companion_conversation(
        self,
        *,
        context_id: str,
        conversation_id: str,
    ) -> OverlayState:
        normalized_context_id = str(context_id or "").strip()
        normalized_conversation_id = str(conversation_id or "").strip()
        if not normalized_context_id:
            raise ValueError("Overlay companion binding requires a context ID.")

        with self._lock:
            if normalized_context_id != self._state.context_id:
                raise ValueError("Overlay context changed before companion conversation binding.")
            if self._state.companion_conversation_id == normalized_conversation_id:
                return self._state
            self._state = replace(
                self._state,
                revision=self._state.revision + 1,
                companion_conversation_id=normalized_conversation_id,
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
