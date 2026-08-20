"""Stage 11 controller for conversational AI inside the Overlay."""

from __future__ import annotations

from typing import Any

from app.ai.chat import (
    AIChatService,
    AIChatTask,
    AIChatTaskFailure,
    ChatContext,
    ChatResult,
    ChatRole,
    ChatSession,
)
from app.ai.chat_overlay import ConversationalAIOverlayManager
from app.ai.compact_controller import CompactAIAppController
from app.ai.errors import AIConfigurationError, AIError
from app.ai.factory import AI_PROVIDER_LABELS, DEFAULT_AI_PROVIDER, normalize_ai_provider
from app.infrastructure.settings import SettingsManager
from app.translation.request_version import RequestVersionController


CHAT_ERROR_TEXT = "AI 对话请求失败。"
CHAT_CONFIG_ERROR_TEXT = "请先在“设置 → AI 大模型与 API Key”中完成模型配置。"


class ConversationalAIAppController(CompactAIAppController):
    """Add a provider-reusing, multi-turn chat session to the compact controller."""

    def __init__(
        self,
        *args: Any,
        chat_service: AIChatService | Any | None = None,
        **kwargs: Any,
    ) -> None:
        if kwargs.get("overlay_manager") is None:
            resolved_config = kwargs.get("config_manager")
            if resolved_config is None:
                resolved_config = SettingsManager()
                kwargs["config_manager"] = resolved_config
            kwargs["overlay_manager"] = ConversationalAIOverlayManager(
                config_manager=resolved_config,
            )

        super().__init__(*args, **kwargs)
        self.chat_service: AIChatService | Any | None = chat_service
        self._chat_service_injected = chat_service is not None
        self._chat_session = ChatSession()
        self._chat_request_versions = RequestVersionController()
        self._chat_tasks: set[AIChatTask] = set()

    @property
    def chat_session(self) -> ChatSession:
        return self._chat_session

    @property
    def latest_chat_request_id(self) -> int:
        return self._chat_request_versions.latest_request_id

    def _ensure_chat_service(self) -> AIChatService | Any:
        if self.chat_service is None:
            self.chat_service = AIChatService(self._ensure_ai_service())
        return self.chat_service

    def _configured_chat_identity(self) -> tuple[str, str]:
        get = getattr(self.config_manager, "get", None)
        if callable(get):
            provider_key = normalize_ai_provider(
                get("ai", "provider", DEFAULT_AI_PROVIDER)
            )
            model = str(get("ai", "model", "") or "").strip()
        else:
            provider_key = DEFAULT_AI_PROVIDER
            model = ""
        return AI_PROVIDER_LABELS.get(provider_key, provider_key), model

    def _chat_overlay_call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        callback = getattr(self.overlay_manager, name, None)
        if not callable(callback):
            return None
        return self._safe_call(f"{name}_failed", callback, *args, **kwargs)

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        if key == "ai_chat":
            self._open_ai_chat()
            return
        if key == "ai_chat_send":
            self._submit_chat_message(str(value or ""))
            return
        if key == "ai_chat_clear":
            self._clear_ai_chat()
            return
        if key == "ai_chat_close":
            self._chat_overlay_call("close_chat")
            return
        super()._on_overlay_context_action(key, value)

    def _open_ai_chat(self) -> None:
        context = ChatContext(
            source_text=str(self._last_source_text or "").strip(),
            translated_text=str(self._last_translation_text or "").strip(),
        )
        self._chat_session.set_context(context)
        provider, model = self._configured_chat_identity()
        self._chat_overlay_call(
            "open_chat",
            source_text=context.source_text,
            translated_text=context.translated_text,
            provider=provider,
            model=model,
            messages=self._chat_session.messages,
        )
        self._overlay_visible = True
        self._safe_call(
            "tray_overlay_visibility_update_failed",
            self.tray_manager.set_overlay_visible,
            True,
        )

    def _clear_ai_chat(self) -> None:
        self._chat_session.clear()
        self._chat_overlay_call("clear_chat")

    def _submit_chat_message(self, message: str) -> None:
        if self._shutdown:
            return
        user_message = str(message).strip()
        if not user_message:
            return

        request_id = self._chat_request_versions.next_request_id()
        try:
            request = self._chat_session.request(
                user_message,
                request_id=request_id,
            )
        except ValueError:
            return

        self._chat_overlay_call("append_chat_message", ChatRole.USER, user_message)
        self._chat_overlay_call("set_chat_busy", True)

        try:
            service = self._ensure_chat_service()
        except AIConfigurationError:
            self._chat_overlay_call("set_chat_error", CHAT_CONFIG_ERROR_TEXT)
            return
        except AIError as exc:
            self._log_exception("chat_service_start_failed", exc)
            self._chat_overlay_call("set_chat_error", CHAT_ERROR_TEXT)
            return
        except Exception as exc:
            self._log_exception("chat_service_start_failed", exc)
            self._chat_overlay_call("set_chat_error", CHAT_ERROR_TEXT)
            return

        task = AIChatTask(service, request, logger=self.logger)
        task.signals.succeeded.connect(self._on_chat_task_succeeded)
        task.signals.failed.connect(self._on_chat_task_failed)
        task.signals.finished.connect(self._on_chat_task_finished)
        self._chat_tasks.add(task)
        self.logger.info(
            "ai_chat_submitted request_id=%s message_length=%s history_messages=%s",
            request_id,
            len(user_message),
            len(request.history),
        )
        try:
            self.translation_pool.start(task)
        except Exception as exc:
            self._chat_tasks.discard(task)
            self._log_exception("ai_chat_task_start_failed", exc)
            self._chat_overlay_call("set_chat_error", CHAT_ERROR_TEXT)

    def _on_chat_task_succeeded(self, result: object) -> None:
        if self._shutdown or not isinstance(result, ChatResult):
            return
        if not self._chat_request_versions.is_latest(result.request_id):
            self.logger.debug(
                "ai_chat_result_discarded request_id=%s latest_request_id=%s",
                result.request_id,
                self.latest_chat_request_id,
            )
            return
        if result.session_id != self._chat_session.session_id:
            return

        self._chat_session.commit_exchange(
            result.user_message,
            result.output_text,
        )
        self._chat_overlay_call(
            "set_chat_identity",
            result.provider,
            result.model,
        )
        self._chat_overlay_call(
            "append_chat_message",
            ChatRole.ASSISTANT,
            result.output_text,
        )
        self._chat_overlay_call("set_chat_busy", False)
        self.logger.info(
            "ai_chat_displayed request_id=%s output_length=%s",
            result.request_id,
            len(result.output_text),
        )

    def _on_chat_task_failed(self, failure: object) -> None:
        if self._shutdown or not isinstance(failure, AIChatTaskFailure):
            return
        if not self._chat_request_versions.is_latest(failure.request_id):
            return

        message = (
            CHAT_CONFIG_ERROR_TEXT
            if isinstance(failure.error, AIConfigurationError)
            else CHAT_ERROR_TEXT
        )
        self.logger.info(
            "ai_chat_failed request_id=%s error_type=%s",
            failure.request_id,
            type(failure.error).__name__,
        )
        self._chat_overlay_call("set_chat_error", message)

    def _on_chat_task_finished(self, task: object) -> None:
        if isinstance(task, AIChatTask):
            self._chat_tasks.discard(task)

    def _apply_runtime_settings(self) -> None:
        super()._apply_runtime_settings()
        if not self._chat_service_injected:
            self.chat_service = None
        provider, model = self._configured_chat_identity()
        self._chat_overlay_call("set_chat_identity", provider, model)

    def shutdown(self) -> None:
        if self._shutdown:
            return
        try:
            super().shutdown()
        finally:
            self._chat_tasks.clear()
            self.chat_service = None


__all__ = [
    "CHAT_CONFIG_ERROR_TEXT",
    "CHAT_ERROR_TEXT",
    "ConversationalAIAppController",
]
