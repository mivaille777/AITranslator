"""Production controller for editable source text and live translation."""

from __future__ import annotations

from typing import Any

from app.ai.editable_overlay import EditableResizableConversationalAIOverlayManager
from app.ai.streaming_controller import StreamingResizableAIAppController
from app.infrastructure.settings import SettingsManager
from app.translation.errors import TextNormalizationError


class EditableStreamingResizableAIAppController(StreamingResizableAIAppController):
    """Add direct source editing without changing the translation task model."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("overlay_manager") is None:
            resolved_config = kwargs.get("config_manager")
            if resolved_config is None:
                resolved_config = SettingsManager()
                kwargs["config_manager"] = resolved_config
            kwargs["overlay_manager"] = EditableResizableConversationalAIOverlayManager(
                config_manager=resolved_config,
            )
        super().__init__(*args, **kwargs)

    def _open_ai_chat(self) -> None:
        # A live translation submitted just before the user opens Chat must not
        # finish later and force the Overlay back to translation mode.
        self._request_versions.next_request_id()
        super()._open_ai_chat()

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        if key == "manual_source_text":
            self._translate_manual_source(value)
            return
        super()._on_overlay_context_action(key, value)

    def _translate_manual_source(self, value: object) -> None:
        """Translate editor text after the Overlay's UI-side debounce."""

        if self._shutdown or self._is_ai_chat_open():
            return

        source_text = "" if value is None else str(value)
        self._last_source_text = source_text

        if not source_text.strip():
            # Invalidate an in-flight result so clearing the editor cannot be
            # followed by an older translation suddenly reappearing.
            self._request_versions.next_request_id()
            self._last_translation_text = ""
            source_language, target_language = self._configured_language_pair()
            try:
                self.overlay_manager.show_translation(
                    "",
                    "",
                    source_language,
                    target_language,
                )
            except Exception as exc:
                self._log_exception("manual_translation_clear_failed", exc)
            return

        if not self._translation_enabled:
            self.logger.info("manual_translation_ignored translation_paused")
            return

        try:
            translatable_text = self._prepare_selected_text(source_text)
        except TextNormalizationError as exc:
            self.logger.info(
                "manual_input_text_rejected error_type=%s",
                type(exc).__name__,
            )
            return

        self.logger.info(
            "manual_translation_submitted text_length=%s",
            len(translatable_text),
        )
        self._submit_translation(translatable_text)


__all__ = ["EditableStreamingResizableAIAppController"]
