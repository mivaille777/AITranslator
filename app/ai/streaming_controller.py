"""Production controller with startup Overlay, streaming chat and resize support."""

from __future__ import annotations

from typing import Any

from app.ai.chat import ChatRequest, ChatResult, ChatRole
from app.ai.chat.streaming import (
    AIChatStreamChunk,
    StreamingAIChatService,
    StreamingAIChatTask,
)
from app.ai.chat.task import AIChatTaskFailure
from app.ai.chat_selection_controller import (
    SelectionCaptureConversationalAIAppController,
)
from app.ai.errors import AIConfigurationError, AIError
from app.ai.factory import AI_PROVIDER_LABELS, normalize_ai_provider
from app.ai.resizable_overlay import ResizableConversationalAIOverlayManager
from app.infrastructure.settings import SettingsManager
from app.input.mouse_selection_manager import MOUSE_SELECTION_SOURCE
from app.models.events import TranslationTriggerEvent
from app.overlay.context_menu import normalize_language_code
from app.overlay.language_bar import normalize_target_language_code


STREAM_CHAT_ERROR_TEXT = "AI 对话请求失败。"
STREAM_CHAT_CONFIG_ERROR_TEXT = "请先在“设置 → AI 大模型与 API Key”中完成模型配置。"
STARTUP_OVERLAY_TEXT = "等待划词翻译…"


class StreamingResizableAIAppController(
    SelectionCaptureConversationalAIAppController
):
    """Final production controller for streaming, resizable Overlay chat."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("overlay_manager") is None:
            resolved_config = kwargs.get("config_manager")
            if resolved_config is None:
                resolved_config = SettingsManager()
                kwargs["config_manager"] = resolved_config
            kwargs["overlay_manager"] = ResizableConversationalAIOverlayManager(
                config_manager=resolved_config,
            )
        self._active_stream_request_id: int | None = None
        super().__init__(*args, **kwargs)
        self._normalize_runtime_language_pair(persist_invalid_target=True)

    def _connect_tray_signals(self) -> None:
        """Wire the renamed tray visibility action to real Overlay visibility."""

        self.tray_manager.enable_translation_requested.connect(
            self._enable_translation,
        )
        self.tray_manager.pause_translation_requested.connect(
            self._pause_translation,
        )
        self.tray_manager.auto_selection_requested.connect(
            self._set_auto_selection,
        )
        self.tray_manager.lock_overlay_requested.connect(self._lock_overlay)
        self.tray_manager.unlock_overlay_requested.connect(self._unlock_overlay)
        self.tray_manager.show_overlay_requested.connect(self._show_overlay_from_tray)
        self.tray_manager.hide_overlay_requested.connect(self._hide_overlay)
        self.tray_manager.settings_requested.connect(self._show_settings)
        self.tray_manager.exit_requested.connect(self._exit_application)

    def start(self, *, start_hotkey: bool = True) -> None:
        was_started = self._started
        super().start(start_hotkey=start_hotkey)
        if not was_started and self._started and not self._shutdown:
            self._show_startup_overlay()

    def _show_startup_overlay(self) -> None:
        """Show a normal ready card instead of the old internal test subtitle."""

        if self._last_translation_text:
            self._show_overlay_from_tray()
            return
        try:
            self.overlay_manager.show_text(STARTUP_OVERLAY_TEXT)
        except Exception as exc:
            self._log_exception("overlay_startup_show_failed", exc)
            return
        self._overlay_visible = True
        self._safe_call(
            "tray_overlay_visibility_update_failed",
            self.tray_manager.set_overlay_visible,
            True,
        )
        self.logger.info("overlay_startup_ready_shown")

    def _show_overlay_from_tray(self) -> None:
        """Reveal the current Overlay content without replacing it."""

        try:
            self.overlay_manager.show_overlay()
        except Exception as exc:
            self._log_exception("overlay_show_failed", exc)
            return
        self._overlay_visible = True
        self._safe_call(
            "tray_overlay_visibility_update_failed",
            self.tray_manager.set_overlay_visible,
            True,
        )
        self.logger.info("overlay_shown")

    def _configured_language_pair(self) -> tuple[str, str]:
        source = normalize_language_code(
            getattr(
                self.translation_manager,
                "default_source_language",
                getattr(self.config_manager, "translation_source_language", "auto"),
            )
        )
        target_raw = getattr(
            self.translation_manager,
            "default_target_language",
            getattr(self.config_manager, "translation_target_language", "zh-CN"),
        )
        target = normalize_target_language_code(target_raw)
        return source, target

    def _apply_language_pair(
        self,
        source_language: object,
        target_language: object,
        *,
        persist: bool = True,
    ) -> tuple[str, str]:
        source = normalize_language_code(source_language)
        target = normalize_target_language_code(target_language)

        configure_languages = getattr(
            self.translation_manager,
            "configure_languages",
            None,
        )
        if callable(configure_languages):
            self._safe_call(
                "translation_language_apply_failed",
                configure_languages,
                source,
                target,
            )
        else:
            if hasattr(self.translation_manager, "default_source_language"):
                self.translation_manager.default_source_language = source
            if hasattr(self.translation_manager, "default_target_language"):
                self.translation_manager.default_target_language = target

        set_languages = getattr(self.overlay_manager, "set_languages", None)
        if callable(set_languages):
            self._safe_call(
                "overlay_language_display_apply_failed",
                set_languages,
                source,
                target,
            )

        if persist:
            save = getattr(self.config_manager, "save", None)
            if callable(save):
                try:
                    save(
                        {
                            "translation": {
                                "source_language": source,
                                "target_language": target,
                            }
                        }
                    )
                except Exception as exc:
                    self._log_exception("translation_language_setting_save_failed", exc)
        return source, target

    def _normalize_runtime_language_pair(self, *, persist_invalid_target: bool) -> None:
        raw_target = getattr(
            self.translation_manager,
            "default_target_language",
            getattr(self.config_manager, "translation_target_language", "zh-CN"),
        )
        source, target = self._configured_language_pair()
        invalid_target = str(raw_target or "").strip().lower() == "auto"
        self._apply_language_pair(
            source,
            target,
            persist=bool(persist_invalid_target and invalid_target),
        )

    def _handle_language_action(self, key: str, value: object) -> bool:
        if key == "source_language":
            _current_source, current_target = self._configured_language_pair()
            source = normalize_language_code(value)
            self._apply_language_pair(source, current_target)
            self.logger.info(
                "translation_source_language_changed language=%s target=%s",
                source,
                current_target,
            )
            return True

        if key == "target_language":
            current_source, _current_target = self._configured_language_pair()
            target = normalize_target_language_code(value)
            self._apply_language_pair(current_source, target)
            self.logger.info(
                "translation_target_language_changed source=%s language=%s",
                current_source,
                target,
            )
            return True

        if key == "swap_languages":
            if isinstance(value, (tuple, list)) and len(value) == 2:
                candidate_source = normalize_language_code(value[0])
                candidate_target = normalize_target_language_code(value[1])
            else:
                current_source, current_target = self._configured_language_pair()
                if current_source == "auto":
                    return True
                candidate_source = current_target
                candidate_target = normalize_target_language_code(current_source)

            # ``auto`` is valid only on the source side. The visible swap
            # button is disabled in that state, but keep the controller guard
            # too so synthetic/context events cannot persist an invalid pair.
            if candidate_source == "auto" or str(candidate_target).lower() == "auto":
                return True
            source, target = self._apply_language_pair(
                candidate_source,
                candidate_target,
            )
            self.logger.info(
                "translation_languages_swapped source=%s target=%s",
                source,
                target,
            )
            return True

        return False

    def _is_ai_chat_open(self) -> bool:
        """Return whether the production Overlay is currently in Chat mode."""

        checker = getattr(self.overlay_manager, "is_chat_open", None)
        if callable(checker):
            try:
                return bool(checker())
            except Exception as exc:
                self._log_exception("chat_open_state_failed", exc)

        window = getattr(self.overlay_manager, "window", None)
        return bool(getattr(window, "chat_open", False))

    def _on_translation_triggered(self, event: TranslationTriggerEvent) -> None:
        """Never let automatic mouse selection kick an open Chat back to translation."""

        if event.source == MOUSE_SELECTION_SOURCE and self._is_ai_chat_open():
            if self._is_chat_selection_capture_armed():
                self.logger.info(
                    "CHAT_SELECTION_CAPTURE_TRIGGERED source=%s",
                    event.source,
                )
                self._capture_mouse_selection_into_chat()
            else:
                # Chat owns mouse-selection gestures while it is open. If the
                # optional capture preference is disabled, or the input is
                # temporarily unavailable during streaming, ignore the gesture
                # instead of falling through to the normal translation path.
                self.logger.info("auto_selection_ignored chat_open")
            return
        super()._on_translation_triggered(event)

    def _ensure_chat_service(self) -> Any:
        if self.chat_service is None:
            self.chat_service = StreamingAIChatService(self._ensure_ai_service())
        return self.chat_service

    def _cancel_active_stream(self) -> None:
        request_id = self._active_stream_request_id
        if request_id is not None:
            self._chat_overlay_call("cancel_chat_stream", request_id)
        self._active_stream_request_id = None

    def _new_ai_chat(self) -> None:
        self._cancel_active_stream()
        super()._new_ai_chat()

    def _switch_ai_chat(self, conversation_id: str) -> None:
        self._cancel_active_stream()
        super()._switch_ai_chat(conversation_id)

    def _delete_ai_chat(self, conversation_id: str) -> None:
        self._cancel_active_stream()
        super()._delete_ai_chat(conversation_id)

    def _clear_ai_chat(self) -> None:
        self._cancel_active_stream()
        super()._clear_ai_chat()

    def _select_chat_model(self, payload: object) -> None:
        self._chat_request_versions.next_request_id()
        self._cancel_active_stream()
        super()._select_chat_model(payload)

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        if self._handle_language_action(key, value):
            return
        if key == "ai_chat_close":
            self._chat_request_versions.next_request_id()
            self._cancel_active_stream()
        super()._on_overlay_context_action(key, value)

    def _submit_chat_message(self, message: str) -> None:
        if self._shutdown:
            return
        user_message = str(message).strip()
        if not user_message:
            return

        active = self.conversation_manager.active
        if active is None:
            provider, model, base_url = self._current_ai_config()
            active = self.conversation_manager.new_conversation(
                context=self._current_reading_context(),
                provider=provider,
                model=model,
                base_url=base_url,
            )

        self._cancel_active_stream()
        request_id = self._chat_request_versions.next_request_id()
        request = ChatRequest(
            session_id=active.session_id,
            user_message=user_message,
            context=active.context,
            history=tuple(active.messages),
            request_id=request_id,
        )
        self._chat_overlay_call("append_chat_message", ChatRole.USER, user_message)
        self._chat_overlay_call("set_chat_busy", True)
        self._chat_overlay_call("begin_chat_stream", request_id)
        self._active_stream_request_id = request_id

        try:
            service = self._ensure_chat_service()
        except AIConfigurationError:
            self._cancel_active_stream()
            self._chat_overlay_call("set_chat_error", STREAM_CHAT_CONFIG_ERROR_TEXT)
            return
        except AIError as exc:
            self._cancel_active_stream()
            self._log_exception("chat_service_start_failed", exc)
            self._chat_overlay_call("set_chat_error", STREAM_CHAT_ERROR_TEXT)
            return
        except Exception as exc:
            self._cancel_active_stream()
            self._log_exception("chat_service_start_failed", exc)
            self._chat_overlay_call("set_chat_error", STREAM_CHAT_ERROR_TEXT)
            return

        task = StreamingAIChatTask(service, request, logger=self.logger)
        task.signals.chunk.connect(self._on_chat_stream_chunk)
        task.signals.succeeded.connect(self._on_chat_task_succeeded)
        task.signals.failed.connect(self._on_chat_task_failed)
        task.signals.finished.connect(self._on_chat_task_finished)
        self._chat_tasks.add(task)
        self.logger.info(
            "ai_chat_stream_submitted request_id=%s message_length=%s history_messages=%s",
            request_id,
            len(user_message),
            len(request.history),
        )
        try:
            self.translation_pool.start(task)
        except Exception as exc:
            self._chat_tasks.discard(task)
            self._cancel_active_stream()
            self._log_exception("ai_chat_task_start_failed", exc)
            self._chat_overlay_call("set_chat_error", STREAM_CHAT_ERROR_TEXT)

    def _on_chat_stream_chunk(self, chunk: object) -> None:
        if self._shutdown or not isinstance(chunk, AIChatStreamChunk):
            return
        if not self._chat_request_versions.is_latest(chunk.request_id):
            return
        active = self.conversation_manager.active
        if active is None or chunk.session_id != active.session_id:
            return
        self._chat_overlay_call(
            "update_chat_stream",
            chunk.request_id,
            chunk.accumulated_text,
        )

    def _on_chat_task_succeeded(self, result: object) -> None:
        if self._shutdown or not isinstance(result, ChatResult):
            return
        if not self._chat_request_versions.is_latest(result.request_id):
            return
        active = self.conversation_manager.active
        if active is None or result.session_id != active.session_id:
            return

        conversation = self.conversation_manager.append_exchange(
            result.user_message,
            result.output_text,
        )
        if result.provider:
            conversation.provider = normalize_ai_provider(result.provider)
        if result.model:
            conversation.model = result.model
        self.conversation_manager.save()

        self._chat_overlay_call(
            "finish_chat_stream",
            result.request_id,
            result.output_text,
        )
        self._active_stream_request_id = None
        self._chat_overlay_call(
            "set_chat_identity",
            AI_PROVIDER_LABELS.get(conversation.provider, conversation.provider),
            result.model,
        )
        self._chat_overlay_call("set_chat_busy", False)
        self._sync_chat_controls(conversation)
        self.logger.info(
            "ai_chat_stream_completed request_id=%s output_length=%s",
            result.request_id,
            len(result.output_text),
        )

    def _on_chat_task_failed(self, failure: object) -> None:
        if isinstance(failure, AIChatTaskFailure):
            self._chat_overlay_call("cancel_chat_stream", failure.request_id)
            if self._active_stream_request_id == failure.request_id:
                self._active_stream_request_id = None
        super()._on_chat_task_failed(failure)

    def _on_chat_task_finished(self, task: object) -> None:
        if isinstance(task, StreamingAIChatTask):
            self._chat_tasks.discard(task)
            return
        super()._on_chat_task_finished(task)

    def _apply_runtime_settings(self) -> None:
        super()._apply_runtime_settings()
        self._normalize_runtime_language_pair(persist_invalid_target=True)
        if not self._chat_service_injected:
            self.chat_service = None


__all__ = [
    "STARTUP_OVERLAY_TEXT",
    "STREAM_CHAT_CONFIG_ERROR_TEXT",
    "STREAM_CHAT_ERROR_TEXT",
    "StreamingResizableAIAppController",
]
