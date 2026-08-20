"""Controller for selection capture, persistent chat history and model switching."""

from __future__ import annotations

from typing import Any

from app.ai.chat import (
    AIChatTask,
    ChatContext,
    ChatRequest,
    ChatResult,
    ChatRole,
)
from app.ai.chat.conversation_manager import Conversation, ConversationManager
from app.ai.chat_controller import ConversationalAIAppController
from app.ai.chat_selection_overlay import (
    SelectionCaptureConversationalAIOverlayManager,
)
from app.ai.client import DEEPSEEK_BASE_URL, SUPPORTED_DEEPSEEK_MODELS
from app.ai.errors import AIConfigurationError, AIError
from app.ai.factory import (
    AI_PROVIDER_LABELS,
    DEFAULT_AI_PROVIDER,
    OPENAI_COMPATIBLE_PROVIDER,
    normalize_ai_provider,
)
from app.infrastructure.settings import SettingsManager
from app.input.mouse_selection_manager import MOUSE_SELECTION_SOURCE
from app.models.events import TranslationTriggerEvent
from app.selection.errors import SelectionError
from app.translation.errors import TextNormalizationError


CHAT_SELECTION_ERROR_TEXT = "无法读取选中的文本。"
CHAT_SELECTION_INPUT_ERROR_TEXT = "选中的文本为空或超过输入限制。"
CHAT_MODEL_ERROR_TEXT = "无法切换到所选模型，请检查 Provider、API Key 和模型配置。"


class SelectionCaptureConversationalAIAppController(ConversationalAIAppController):
    """Full Overlay chat controller with ChatGPT-style local session history."""

    def __init__(
        self,
        *args: Any,
        conversation_manager: ConversationManager | Any | None = None,
        **kwargs: Any,
    ) -> None:
        if kwargs.get("overlay_manager") is None:
            resolved_config = kwargs.get("config_manager")
            if resolved_config is None:
                resolved_config = SettingsManager()
                kwargs["config_manager"] = resolved_config
            kwargs["overlay_manager"] = SelectionCaptureConversationalAIOverlayManager(
                config_manager=resolved_config,
            )
        super().__init__(*args, **kwargs)
        self.conversation_manager = conversation_manager or ConversationManager()

    def _current_ai_config(self) -> tuple[str, str, str]:
        get = getattr(self.config_manager, "get", None)
        if not callable(get):
            return DEFAULT_AI_PROVIDER, "", DEEPSEEK_BASE_URL
        provider = normalize_ai_provider(get("ai", "provider", DEFAULT_AI_PROVIDER))
        model = str(get("ai", "model", "") or "").strip()
        base_url = str(get("ai", "base_url", "") or "").strip()
        if provider == DEFAULT_AI_PROVIDER:
            base_url = DEEPSEEK_BASE_URL
        return provider, model, base_url

    def _current_reading_context(self) -> ChatContext:
        return ChatContext(
            source_text=str(self._last_source_text or "").strip(),
            translated_text=str(self._last_translation_text or "").strip(),
        )

    def _available_chat_models(self) -> tuple[dict[str, str], ...]:
        options: list[dict[str, str]] = []
        for model in sorted(SUPPORTED_DEEPSEEK_MODELS):
            options.append(
                {
                    "provider": DEFAULT_AI_PROVIDER,
                    "provider_label": AI_PROVIDER_LABELS[DEFAULT_AI_PROVIDER],
                    "model": model,
                    "label": model,
                    "base_url": DEEPSEEK_BASE_URL,
                }
            )

        configured_provider, configured_model, configured_base_url = self._current_ai_config()
        if (
            configured_provider == OPENAI_COMPATIBLE_PROVIDER
            and configured_model
            and configured_base_url
        ):
            options.append(
                {
                    "provider": OPENAI_COMPATIBLE_PROVIDER,
                    "provider_label": AI_PROVIDER_LABELS[OPENAI_COMPATIBLE_PROVIDER],
                    "model": configured_model,
                    "label": configured_model,
                    "base_url": configured_base_url,
                }
            )
        return tuple(options)

    @staticmethod
    def _conversation_provider_label(conversation: Conversation) -> str:
        provider = normalize_ai_provider(conversation.provider or DEFAULT_AI_PROVIDER)
        return AI_PROVIDER_LABELS.get(provider, provider)

    def _conversation_summaries(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "conversation_id": item.conversation_id,
                "title": item.title,
                "updated_at": item.updated_at,
            }
            for item in self.conversation_manager.conversations
        )

    def _sync_chat_controls(self, active: Conversation | None = None) -> None:
        current = active or self.conversation_manager.active
        active_id = current.conversation_id if current is not None else ""
        self._chat_overlay_call(
            "set_chat_conversations",
            self._conversation_summaries(),
            active_id,
        )

        if current is None:
            provider, model, _base_url = self._current_ai_config()
        else:
            provider = normalize_ai_provider(current.provider or DEFAULT_AI_PROVIDER)
            model = current.model
        self._chat_overlay_call(
            "set_chat_model_options",
            self._available_chat_models(),
            current_provider=provider,
            current_model=model,
        )
        self._chat_overlay_call(
            "set_chat_identity",
            AI_PROVIDER_LABELS.get(provider, provider),
            model,
        )

    def _show_managed_conversation(self, conversation: Conversation) -> None:
        self._chat_overlay_call(
            "open_chat",
            source_text=conversation.context.source_text,
            translated_text=conversation.context.translated_text,
            provider=self._conversation_provider_label(conversation),
            model=conversation.model,
            messages=tuple(conversation.messages),
        )
        self._sync_chat_controls(conversation)
        self._overlay_visible = True
        self._safe_call(
            "tray_overlay_visibility_update_failed",
            self.tray_manager.set_overlay_visible,
            True,
        )

    def _open_ai_chat(self) -> None:
        active = self.conversation_manager.active
        if active is None:
            provider, model, base_url = self._current_ai_config()
            active = self.conversation_manager.new_conversation(
                context=self._current_reading_context(),
                provider=provider,
                model=model,
                base_url=base_url,
            )
        elif not active.messages:
            active = self.conversation_manager.set_context(self._current_reading_context())
        self._show_managed_conversation(active)

    def _new_ai_chat(self) -> None:
        # Invalidate a late response from the conversation being left.
        self._chat_request_versions.next_request_id()
        provider, model, base_url = self._current_ai_config()
        conversation = self.conversation_manager.new_conversation(
            context=self._current_reading_context(),
            provider=provider,
            model=model,
            base_url=base_url,
        )
        self._show_managed_conversation(conversation)

    def _switch_ai_chat(self, conversation_id: str) -> None:
        conversation_id = str(conversation_id).strip()
        if not conversation_id:
            return
        self._chat_request_versions.next_request_id()
        conversation = self.conversation_manager.switch(conversation_id)
        if conversation is None:
            return
        self._apply_conversation_model_to_runtime(conversation)
        self._show_managed_conversation(conversation)

    def _delete_ai_chat(self, conversation_id: str) -> None:
        conversation_id = str(conversation_id).strip()
        if not conversation_id:
            return
        self._chat_request_versions.next_request_id()
        self.conversation_manager.remove(conversation_id)
        active = self.conversation_manager.active
        if active is None:
            self._new_ai_chat()
            return
        self._apply_conversation_model_to_runtime(active)
        self._show_managed_conversation(active)

    def _clear_ai_chat(self) -> None:
        conversation = self.conversation_manager.clear_active()
        self._chat_overlay_call("clear_chat")
        self._sync_chat_controls(conversation)

    def _apply_conversation_model_to_runtime(self, conversation: Conversation) -> None:
        provider = normalize_ai_provider(conversation.provider or DEFAULT_AI_PROVIDER)
        model = str(conversation.model).strip()
        base_url = str(conversation.base_url).strip()
        if provider == DEFAULT_AI_PROVIDER:
            base_url = DEEPSEEK_BASE_URL
        if not model:
            return
        save = getattr(self.config_manager, "save", None)
        if callable(save):
            save(
                {
                    "ai": {
                        "provider": provider,
                        "model": model,
                        "base_url": base_url,
                    }
                }
            )
        self._reset_configured_ai_service()
        if not self._chat_service_injected:
            self.chat_service = None

    def _select_chat_model(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        provider = normalize_ai_provider(payload.get("provider", DEFAULT_AI_PROVIDER))
        model = str(payload.get("model", "")).strip()
        base_url = str(payload.get("base_url", "")).strip()
        if provider == DEFAULT_AI_PROVIDER:
            if model not in SUPPORTED_DEEPSEEK_MODELS:
                self._chat_overlay_call("set_chat_error", CHAT_MODEL_ERROR_TEXT)
                return
            base_url = DEEPSEEK_BASE_URL
        elif not model or not base_url:
            self._chat_overlay_call("set_chat_error", CHAT_MODEL_ERROR_TEXT)
            return

        save = getattr(self.config_manager, "save", None)
        try:
            if callable(save):
                save(
                    {
                        "ai": {
                            "provider": provider,
                            "model": model,
                            "base_url": base_url,
                        }
                    }
                )
            self._reset_configured_ai_service()
            if not self._chat_service_injected:
                self.chat_service = None
            conversation = self.conversation_manager.set_model(
                provider,
                model,
                base_url,
            )
        except Exception as exc:
            self._log_exception("chat_model_switch_failed", exc)
            self._chat_overlay_call("set_chat_error", CHAT_MODEL_ERROR_TEXT)
            return

        self._chat_overlay_call(
            "set_chat_identity",
            AI_PROVIDER_LABELS.get(provider, provider),
            model,
        )
        self._sync_chat_controls(conversation)
        self.logger.info(
            "ai_chat_model_switched provider=%s model=%s",
            provider,
            model,
        )

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        if key == "ai_chat_new":
            self._new_ai_chat()
            return
        if key == "ai_chat_switch":
            self._switch_ai_chat(str(value or ""))
            return
        if key == "ai_chat_delete":
            self._delete_ai_chat(str(value or ""))
            return
        if key == "ai_chat_model":
            self._select_chat_model(value)
            return
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

        try:
            service = self._ensure_chat_service()
        except AIConfigurationError:
            self._chat_overlay_call(
                "set_chat_error",
                "请先在“设置 → AI 大模型与 API Key”中完成模型配置。",
            )
            return
        except AIError as exc:
            self._log_exception("chat_service_start_failed", exc)
            self._chat_overlay_call("set_chat_error", "AI 对话请求失败。")
            return
        except Exception as exc:
            self._log_exception("chat_service_start_failed", exc)
            self._chat_overlay_call("set_chat_error", "AI 对话请求失败。")
            return

        task = AIChatTask(service, request, logger=self.logger)
        task.signals.succeeded.connect(self._on_chat_task_succeeded)
        task.signals.failed.connect(self._on_chat_task_failed)
        task.signals.finished.connect(self._on_chat_task_finished)
        self._chat_tasks.add(task)
        try:
            self.translation_pool.start(task)
        except Exception as exc:
            self._chat_tasks.discard(task)
            self._log_exception("ai_chat_task_start_failed", exc)
            self._chat_overlay_call("set_chat_error", "AI 对话请求失败。")

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
            "set_chat_identity",
            AI_PROVIDER_LABELS.get(conversation.provider, conversation.provider),
            result.model,
        )
        self._chat_overlay_call(
            "append_chat_message",
            ChatRole.ASSISTANT,
            result.output_text,
        )
        self._chat_overlay_call("set_chat_busy", False)
        self._sync_chat_controls(conversation)

    def _is_chat_selection_capture_armed(self) -> bool:
        checker = getattr(
            self.overlay_manager,
            "is_chat_selection_capture_armed",
            None,
        )
        if not callable(checker):
            return False
        try:
            return bool(checker())
        except Exception as exc:
            self._log_exception("chat_selection_capture_state_failed", exc)
            return False

    def _capture_mouse_selection_into_chat(self) -> bool:
        if self._is_cursor_over_overlay():
            self.logger.info("chat_selection_capture_ignored overlay_hover")
            return True

        try:
            selected = self.selection_manager.get_selected_text()
        except SelectionError as exc:
            self.logger.info(
                "chat_selection_capture_failed error_type=%s",
                type(exc).__name__,
            )
            self._chat_overlay_call("set_chat_error", CHAT_SELECTION_ERROR_TEXT)
            return True
        except Exception as exc:
            self._log_exception("chat_selection_capture_failed", exc)
            self._chat_overlay_call("set_chat_error", CHAT_SELECTION_ERROR_TEXT)
            return True

        self.logger.info(
            "chat_selection_captured text_length=%s provider=%s",
            len(selected.text),
            selected.provider,
        )
        try:
            prepared = self._prepare_selected_text(selected.text)
        except TextNormalizationError as exc:
            self.logger.info(
                "chat_selection_input_rejected error_type=%s",
                type(exc).__name__,
            )
            self._chat_overlay_call(
                "set_chat_error",
                CHAT_SELECTION_INPUT_ERROR_TEXT,
            )
            return True

        if not str(prepared).strip():
            self._chat_overlay_call(
                "set_chat_error",
                CHAT_SELECTION_INPUT_ERROR_TEXT,
            )
            return True

        inserted = bool(
            self._chat_overlay_call(
                "insert_chat_selection",
                prepared,
            )
        )
        if inserted:
            self.logger.info(
                "chat_selection_inserted text_length=%s",
                len(prepared),
            )
        else:
            self._chat_overlay_call("set_chat_error", CHAT_SELECTION_ERROR_TEXT)
        return True

    def _on_translation_triggered(self, event: TranslationTriggerEvent) -> None:
        if (
            event.source == MOUSE_SELECTION_SOURCE
            and self._is_chat_selection_capture_armed()
        ):
            self.logger.info("CHAT_SELECTION_CAPTURE_TRIGGERED source=%s", event.source)
            self._capture_mouse_selection_into_chat()
            return
        super()._on_translation_triggered(event)


__all__ = [
    "CHAT_MODEL_ERROR_TEXT",
    "CHAT_SELECTION_ERROR_TEXT",
    "CHAT_SELECTION_INPUT_ERROR_TEXT",
    "SelectionCaptureConversationalAIAppController",
]
