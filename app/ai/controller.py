"""AI-aware application controller integration.

This module extends the existing :class:`app.controller.AppController` instead
of duplicating the mature selection/translation/tray logic. AI work therefore
shares the controller's request-version sequence and QThreadPool while keeping
DeepSeek-specific details below :class:`AITextService`.
"""

from __future__ import annotations

from typing import Any

from app.ai.errors import AIConfigurationError, AIError
from app.ai.models import AITextAction, AITextRequest, AITextResult
from app.ai.overlay import AIOverlayManager
from app.ai.service import AITextService
from app.ai.task import AITextTask, AITextTaskFailure
from app.controller import AppController, INPUT_TEXT_ERROR_TEXT
from app.infrastructure.settings import SettingsManager
from app.translation.errors import TextNormalizationError


AI_ERROR_TEXT = "AIError: AI request failed."
AI_CONFIG_ERROR_TEXT = "AIConfigError: configure DEEPSEEK_API_KEY to use AI features."
AI_INPUT_ERROR_TEXT = "InputError: no source text is available for AI processing."
AI_TRANSLATING_TEXT = "AI 翻译中…"
AI_POLISHING_TEXT = "AI 润色中…"
AI_POLISH_DISPLAY_TARGET = "润色"


class AIAppController(AppController):
    """Add asynchronous AI translation/polish actions to ``AppController``.

    The DeepSeek-backed service is created lazily. This is important for the
    normal desktop startup and ``--smoke-test`` path: users who only use the
    existing Google translation flow do not need an API key just to launch the
    application.
    """

    def __init__(
        self,
        *args: Any,
        ai_service: AITextService | Any | None = None,
        **kwargs: Any,
    ) -> None:
        # Resolve the normal settings object once so the AI-aware Overlay uses
        # the exact same runtime visual/language configuration as AppController.
        if kwargs.get("overlay_manager") is None:
            resolved_config = kwargs.get("config_manager")
            if resolved_config is None:
                resolved_config = SettingsManager()
                kwargs["config_manager"] = resolved_config
            kwargs["overlay_manager"] = AIOverlayManager(
                config_manager=resolved_config,
            )

        super().__init__(*args, **kwargs)
        self.ai_service: AITextService | Any | None = ai_service
        self._ai_tasks: set[AITextTask] = set()
        self._ai_shutdown_complete = False

    def _ensure_ai_service(self) -> AITextService | Any:
        """Create the default DeepSeek service only when an AI action is used."""

        if self.ai_service is None:
            self.ai_service = AITextService()
        return self.ai_service

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        """Handle AI semantic actions, delegating every legacy action unchanged."""

        if key == "ai_translate":
            self._submit_ai_action(AITextAction.TRANSLATE)
            return
        if key == "ai_polish":
            self._submit_ai_action(AITextAction.POLISH)
            return
        super()._on_overlay_context_action(key, value)

    def _submit_ai_action(self, action: AITextAction) -> None:
        """Submit an AI request without blocking the Qt GUI thread."""

        if self._shutdown:
            return

        if not isinstance(self._last_source_text, str) or not self._last_source_text.strip():
            self._show_translation_error(AI_INPUT_ERROR_TEXT, "AIInputError")
            return

        try:
            source_text = self._prepare_selected_text(self._last_source_text)
        except TextNormalizationError:
            self._show_translation_error(INPUT_TEXT_ERROR_TEXT, "InputError")
            return

        source_language = str(
            getattr(
                self.translation_manager,
                "default_source_language",
                getattr(self.config_manager, "translation_source_language", "auto"),
            )
            or "auto"
        )
        target_language = str(
            getattr(
                self.translation_manager,
                "default_target_language",
                getattr(self.config_manager, "translation_target_language", "zh-CN"),
            )
            or "zh-CN"
        )
        if action is AITextAction.POLISH:
            target_language = source_language

        request_id = self._request_versions.next_request_id()
        request = AITextRequest(
            source_text=source_text,
            action=action,
            source_language=source_language,
            target_language=target_language,
            request_id=request_id,
        )

        try:
            service = self._ensure_ai_service()
        except AIConfigurationError:
            self.logger.info("ai_configuration_missing request_id=%s", request_id)
            self._show_translation_error(AI_CONFIG_ERROR_TEXT, "AIConfigurationError")
            return
        except AIError as exc:
            self._log_exception("ai_service_start_failed", exc)
            self._show_translation_error(AI_ERROR_TEXT, type(exc).__name__)
            return
        except Exception as exc:
            self._log_exception("ai_service_start_failed", exc)
            self._show_translation_error(AI_ERROR_TEXT, "AIError")
            return

        task = AITextTask(service, request, logger=self.logger)
        task.signals.succeeded.connect(self._on_ai_task_succeeded)
        task.signals.failed.connect(self._on_ai_task_failed)
        task.signals.finished.connect(self._on_ai_task_finished)
        self._ai_tasks.add(task)
        self.logger.info(
            "ai_text_submitted request_id=%s action=%s text_length=%s",
            request_id,
            action.value,
            len(source_text),
        )

        try:
            self._show_ai_loading(request)
            # Reuse the existing pool so shutdown semantics and concurrency
            # limits remain centralized in one controller-owned resource.
            self.translation_pool.start(task)
        except Exception as exc:
            self._ai_tasks.discard(task)
            self._log_exception("ai_text_task_start_failed", exc)
            self._show_translation_error(AI_ERROR_TEXT, "AIError")

    def _show_ai_loading(self, request: AITextRequest) -> None:
        """Show a compact operation-specific loading state."""

        message = (
            AI_TRANSLATING_TEXT
            if request.action is AITextAction.TRANSLATE
            else AI_POLISHING_TEXT
        )
        target_display = (
            request.target_language
            if request.action is AITextAction.TRANSLATE
            else AI_POLISH_DISPLAY_TARGET
        )
        show_translation = getattr(self.overlay_manager, "show_translation", None)
        try:
            if callable(show_translation):
                show_translation(
                    request.source_text,
                    message,
                    request.source_language,
                    target_display,
                )
            else:
                self.overlay_manager.show_text(message)
        except Exception as exc:
            self._log_exception("ai_loading_display_failed", exc)
            return

        self._overlay_visible = True
        self._safe_call(
            "tray_overlay_visibility_update_failed",
            self.tray_manager.set_overlay_visible,
            True,
        )

    def _on_ai_task_succeeded(self, result: object) -> None:
        """Display only the newest AI result on the GUI thread."""

        if self._shutdown:
            return
        if not isinstance(result, AITextResult):
            self.logger.error(
                "ai_text_unexpected_result result_type=%s",
                type(result).__name__,
            )
            return
        if not self._request_versions.is_latest(result.request_id):
            self.logger.debug(
                "ai_text_result_discarded request_id=%s latest_request_id=%s",
                result.request_id,
                self.latest_request_id,
            )
            return

        target_display = (
            result.target_language
            if result.action is AITextAction.TRANSLATE
            else AI_POLISH_DISPLAY_TARGET
        )
        self._show_translation(
            result.output_text,
            source_text=result.source_text,
            source_language=result.source_language,
            target_language=target_display,
        )
        self.logger.info(
            "ai_text_displayed request_id=%s action=%s text_length=%s",
            result.request_id,
            result.action.value,
            len(result.output_text),
        )

    def _on_ai_task_failed(self, failure: object) -> None:
        """Convert AI worker failures into safe user-facing messages."""

        if self._shutdown:
            return
        if not isinstance(failure, AITextTaskFailure):
            self.logger.error(
                "ai_text_unexpected_failure failure_type=%s",
                type(failure).__name__,
            )
            return
        if not self._request_versions.is_latest(failure.request_id):
            self.logger.debug(
                "ai_text_failure_discarded request_id=%s latest_request_id=%s",
                failure.request_id,
                self.latest_request_id,
            )
            return

        if isinstance(failure.error, AIConfigurationError):
            self.logger.info(
                "ai_configuration_error request_id=%s action=%s",
                failure.request_id,
                failure.action.value,
            )
            self._show_translation_error(
                AI_CONFIG_ERROR_TEXT,
                "AIConfigurationError",
            )
            return

        self.logger.info(
            "ai_text_failed request_id=%s action=%s error_type=%s",
            failure.request_id,
            failure.action.value,
            type(failure.error).__name__,
        )
        self._show_translation_error(AI_ERROR_TEXT, type(failure.error).__name__)

    def _on_ai_task_finished(self, task: object) -> None:
        """Release the controller keep-alive reference for a completed AI task."""

        if isinstance(task, AITextTask):
            self._ai_tasks.discard(task)

    def shutdown(self) -> None:
        """Close the lazily created AI service after the shared pool is stopped."""

        if self._ai_shutdown_complete:
            return
        try:
            super().shutdown()
        finally:
            service = self.ai_service
            close = getattr(service, "close", None) if service is not None else None
            if callable(close):
                try:
                    close()
                except Exception as exc:
                    self._log_exception("ai_service_shutdown_failed", exc)
            self._ai_tasks.clear()
            self._ai_shutdown_complete = True


__all__ = [
    "AIAppController",
    "AI_CONFIG_ERROR_TEXT",
    "AI_ERROR_TEXT",
    "AI_INPUT_ERROR_TEXT",
    "AI_POLISH_DISPLAY_TARGET",
]
