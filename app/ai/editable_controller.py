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
from app.translation.task import TranslationTask, TranslationTaskFailure


MANUAL_TRANSLATION_FAILURE_FEEDBACK_MILLISECONDS = 2200


class EditableStreamingResizableAIAppController(StreamingResizableAIAppController):
    """Add direct source editing and stable latest-only live translation.

    Manual editing is deliberately single-flight.  While one provider request
    is running, newer editor contents replace one pending value instead of
    starting more network requests.  The old request is made stale immediately
    so it can never repaint the Overlay; when it finishes only the latest
    pending text is submitted.  This keeps rapid editing from flooding the
    Google web backend while preserving responsive local typing.
    """

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
        self._manual_translation_inflight_request_id: int | None = None
        self._manual_translation_inflight_text = ""
        self._manual_translation_pending_text: str | None = None
        self._manual_last_success_text = ""
        self._manual_last_success_language_pair: tuple[str, str] | None = None
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

    def _abandon_manual_translation_queue(self) -> None:
        """Invalidate manual results without attempting to kill a running HTTP call."""

        self._manual_translation_request_id = None
        self._manual_translation_pending_text = None
        self._manual_translation_inflight_request_id = None
        self._manual_translation_inflight_text = ""

    def _open_ai_chat(self) -> None:
        # A live translation submitted just before the user opens Chat must not
        # finish later and force the Overlay back to translation mode.
        self._request_versions.next_request_id()
        self._abandon_manual_translation_queue()
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
        """Translate editor text after debounce or Ctrl+Enter.

        Only one manual translation is allowed to access the provider at once.
        New input received during that request replaces a single pending value.
        """

        if self._shutdown or self._is_ai_chat_open():
            return

        source_text = "" if value is None else str(value)
        self._last_source_text = source_text

        if not source_text.strip():
            # Invalidate an in-flight result so clearing the editor cannot be
            # followed by an older translation suddenly reappearing.
            self._request_versions.next_request_id()
            self._abandon_manual_translation_queue()
            self._last_translation_text = ""
            self._manual_last_success_text = ""
            self._manual_last_success_language_pair = None
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

        language_pair = self._configured_language_pair()
        if (
            translatable_text == self._manual_last_success_text
            and language_pair == self._manual_last_success_language_pair
        ):
            self._set_translation_status(
                "已是最新",
                auto_hide_ms=TRANSLATION_STATUS_FEEDBACK_MILLISECONDS,
            )
            return

        if self._manual_translation_inflight_request_id is not None:
            # Request-version invalidation makes the running result stale now,
            # not several seconds later when it finally returns.  Do not start
            # another worker yet: keep only the newest editor state.
            self._manual_translation_pending_text = translatable_text
            if self._request_versions.is_latest(
                self._manual_translation_inflight_request_id
            ):
                self._request_versions.next_request_id()
            self._manual_translation_request_id = None
            self._set_translation_status("等待最新输入…")
            self.logger.debug(
                "manual_translation_coalesced text_length=%s",
                len(translatable_text),
            )
            return

        self._start_manual_translation(translatable_text)

    def _start_manual_translation(self, source_text: str) -> None:
        if self._shutdown or self._is_ai_chat_open() or not source_text.strip():
            return
        self.logger.info(
            "manual_translation_submitted text_length=%s",
            len(source_text),
        )
        self._set_translation_status("翻译中…")
        self._submit_translation(source_text)
        request_id = self.latest_request_id
        self._manual_translation_request_id = request_id
        self._manual_translation_inflight_request_id = request_id
        self._manual_translation_inflight_text = source_text

    def _on_translation_task_succeeded(self, result: object) -> None:
        is_manual = bool(
            isinstance(result, TranslationResult)
            and self._manual_translation_inflight_request_id == result.request_id
        )
        was_latest = bool(
            isinstance(result, TranslationResult)
            and self._request_versions.is_latest(result.request_id)
        )
        super()._on_translation_task_succeeded(result)
        if not isinstance(result, TranslationResult) or not was_latest:
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
            self._manual_last_success_text = result.source_text
            self._manual_last_success_language_pair = self._configured_language_pair()
            self._set_translation_status(
                "已更新",
                auto_hide_ms=TRANSLATION_STATUS_FEEDBACK_MILLISECONDS,
            )

    def _on_translation_task_failed(self, failure: object) -> None:
        is_manual = bool(
            isinstance(failure, TranslationTaskFailure)
            and self._manual_translation_inflight_request_id == failure.request_id
        )
        if not is_manual:
            super()._on_translation_task_failed(failure)
            return

        # If newer editor text already exists, this request is intentionally
        # stale and its failure is irrelevant.  The pending latest value will
        # be submitted from _on_translation_task_finished().
        if not self._request_versions.is_latest(failure.request_id):
            self.logger.debug(
                "manual_translation_failure_discarded request_id=%s latest_request_id=%s",
                failure.request_id,
                self.latest_request_id,
            )
            return

        self.logger.info(
            "manual_translation_failed error_type=%s",
            type(failure.error).__name__,
        )
        # Keep the editor and last successful translation visible.  A transient
        # provider failure must not replace the whole workspace with an error
        # card or auto-hide the Overlay.
        self._set_translation_status(
            "暂时失败 · 继续输入可重试",
            auto_hide_ms=MANUAL_TRANSLATION_FAILURE_FEEDBACK_MILLISECONDS,
        )

    def _on_translation_task_finished(self, task: object) -> None:
        was_manual = bool(
            isinstance(task, TranslationTask)
            and self._manual_translation_inflight_request_id == task.request_id
        )
        super()._on_translation_task_finished(task)
        if not was_manual:
            return

        self._manual_translation_inflight_request_id = None
        self._manual_translation_inflight_text = ""
        self._manual_translation_request_id = None
        pending = self._manual_translation_pending_text
        self._manual_translation_pending_text = None

        if (
            pending
            and not self._shutdown
            and not self._is_ai_chat_open()
            and self._translation_enabled
        ):
            self._start_manual_translation(pending)


__all__ = [
    "EditableStreamingResizableAIAppController",
    "MANUAL_TRANSLATION_FAILURE_FEEDBACK_MILLISECONDS",
]
