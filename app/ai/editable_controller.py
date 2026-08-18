"""Production controller for editable source text and live translation."""

from __future__ import annotations

from typing import Any

from app.ai.editable_overlay import (
    TRANSLATION_STATUS_FEEDBACK_MILLISECONDS,
    EditableResizableConversationalAIOverlayManager,
)
from app.ai.streaming_controller import StreamingResizableAIAppController
from app.infrastructure.settings import SettingsManager
from app.models.translation import TranslationResult
from app.translation.errors import TextNormalizationError
from app.translation.task import TranslationTaskFailure


class EditableStreamingResizableAIAppController(StreamingResizableAIAppController):
    """Add direct source editing and responsive translation feedback."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("overlay_manager") is None:
            resolved_config = kwargs.get("config_manager")
            if resolved_config is None:
                resolved_config = SettingsManager()
                kwargs["config_manager"] = resolved_config
            kwargs["overlay_manager"] = EditableResizableConversationalAIOverlayManager(
                config_manager=resolved_config,
            )
        self._manual_translation_request_id: int | None = None
        super().__init__(*args, **kwargs)

    def _set_translation_status(self, status: object, *, auto_hide_ms: int = 0) -> None:
        callback = getattr(self.overlay_manager, "set_translation_status", None)
        if callable(callback):
            self._safe_call(
                "translation_status_update_failed",
                callback,
                status,
                auto_hide_ms=auto_hide_ms,
            )

    def _open_ai_chat(self) -> None:
        # A live translation submitted just before the user opens Chat must not
        # finish later and force the Overlay back to translation mode.
        self._request_versions.next_request_id()
        self._manual_translation_request_id = None
        self._set_translation_status("")
        super()._open_ai_chat()

    def _clear_ai_chat(self) -> None:
        # Clearing a conversation is also a state transition. Invalidate the
        # current chat request before the streaming controller cooperatively
        # cancels it so any already-queued token/result signal becomes stale.
        self._chat_request_versions.next_request_id()
        super()._clear_ai_chat()

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        if key == "manual_source_text":
            self._translate_manual_source(value)
            return
        super()._on_overlay_context_action(key, value)

    def _translate_manual_source(self, value: object) -> None:
        """Translate editor text after debounce or Ctrl+Enter."""

        if self._shutdown or self._is_ai_chat_open():
            return

        source_text = "" if value is None else str(value)
        self._last_source_text = source_text

        if not source_text.strip():
            # Invalidate an in-flight result so clearing the editor cannot be
            # followed by an older translation suddenly reappearing.
            self._request_versions.next_request_id()
            self._manual_translation_request_id = None
            self._last_translation_text = ""
            self._set_translation_status("")
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
            self._set_translation_status(
                "翻译已暂停",
                auto_hide_ms=TRANSLATION_STATUS_FEEDBACK_MILLISECONDS,
            )
            self.logger.info("manual_translation_ignored translation_paused")
            return

        try:
            translatable_text = self._prepare_selected_text(source_text)
        except TextNormalizationError as exc:
            self._set_translation_status(
                "文本不可翻译",
                auto_hide_ms=TRANSLATION_STATUS_FEEDBACK_MILLISECONDS,
            )
            self.logger.info(
                "manual_input_text_rejected error_type=%s",
                type(exc).__name__,
            )
            return

        self.logger.info(
            "manual_translation_submitted text_length=%s",
            len(translatable_text),
        )
        self._set_translation_status("翻译中…")
        self._submit_translation(translatable_text)
        self._manual_translation_request_id = self.latest_request_id

    def _on_translation_task_succeeded(self, result: object) -> None:
        is_manual = bool(
            isinstance(result, TranslationResult)
            and self._manual_translation_request_id == result.request_id
        )
        super()._on_translation_task_succeeded(result)
        if not isinstance(result, TranslationResult):
            return
        if not self._request_versions.is_latest(result.request_id):
            return

        configured_source, _configured_target = self._configured_language_pair()
        detected = str(result.source_language or "").strip()
        if configured_source == "auto" and detected and detected.lower() != "auto":
            setter = getattr(self.overlay_manager, "set_detected_source_language", None)
            if callable(setter):
                self._safe_call(
                    "overlay_detected_language_update_failed",
                    setter,
                    detected,
                )

        if is_manual:
            self._manual_translation_request_id = None
            self._set_translation_status(
                "已更新",
                auto_hide_ms=TRANSLATION_STATUS_FEEDBACK_MILLISECONDS,
            )

    def _on_translation_task_failed(self, failure: object) -> None:
        is_manual = bool(
            isinstance(failure, TranslationTaskFailure)
            and self._manual_translation_request_id == failure.request_id
        )
        super()._on_translation_task_failed(failure)
        if is_manual:
            self._manual_translation_request_id = None
            self._set_translation_status(
                "翻译失败",
                auto_hide_ms=TRANSLATION_STATUS_FEEDBACK_MILLISECONDS,
            )


__all__ = ["EditableStreamingResizableAIAppController"]
