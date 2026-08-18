"""Production controller for LangGraph-driven translation workspace orchestration."""

from __future__ import annotations

from typing import Any

from app.agent.workspace import (
    OPEN_TRANSLATION_COMMAND,
    RETURN_TO_CHAT_COMMAND,
    WorkspaceAgentCoordinator,
    WorkspaceAgentOutcome,
)
from app.ai.agent_workspace_overlay import AgentWorkspaceOverlayManager
from app.ai.chat import ChatResult, ChatRole
from app.ai.chat.conversation_manager import Conversation
from app.ai.chat.streaming import AIChatStreamChunk
from app.ai.chat.task import AIChatTaskFailure
from app.ai.editable_controller import EditableStreamingResizableAIAppController
from app.ai.streaming_controller import STREAM_CHAT_ERROR_TEXT
from app.infrastructure.settings import SettingsManager


class AgentWorkspaceAppController(EditableStreamingResizableAIAppController):
    """Make translation a conversational Agent-controlled workspace capability.

    Workspace decisions are handled by an interruptible LangGraph. Qt remains a
    deterministic executor of graph-produced UI commands; the graph never
    mutates widgets directly.
    """

    def __init__(
        self,
        *args: Any,
        workspace_agent: WorkspaceAgentCoordinator | None = None,
        **kwargs: Any,
    ) -> None:
        if kwargs.get("overlay_manager") is None:
            resolved_config = kwargs.get("config_manager")
            if resolved_config is None:
                resolved_config = SettingsManager()
                kwargs["config_manager"] = resolved_config
            kwargs["overlay_manager"] = AgentWorkspaceOverlayManager(
                config_manager=resolved_config,
            )
        self.workspace_agent = workspace_agent or WorkspaceAgentCoordinator()
        self._agent_translation_active = False
        super().__init__(*args, **kwargs)

    @property
    def agent_translation_active(self) -> bool:
        return self._agent_translation_active

    def _ensure_agent_conversation(self) -> Conversation:
        active = self.conversation_manager.active
        if active is not None:
            return active
        provider, model, base_url = self._current_ai_config()
        return self.conversation_manager.new_conversation(
            context=self._current_reading_context(),
            provider=provider,
            model=model,
            base_url=base_url,
        )

    def _record_workspace_exchange(
        self,
        user_message: str,
        assistant_message: str,
        *,
        render_in_chat: bool,
    ) -> Conversation:
        conversation = self.conversation_manager.append_exchange(
            user_message,
            assistant_message,
        )
        if render_in_chat:
            self._chat_overlay_call("append_chat_message", ChatRole.USER, user_message)
            self._chat_overlay_call(
                "append_chat_message",
                ChatRole.ASSISTANT,
                assistant_message,
            )
            self._sync_chat_controls(conversation)
        return conversation

    def _handle_workspace_agent_turn(
        self,
        message: str,
        *,
        workspace: str,
        render_in_chat: bool,
    ) -> bool:
        user_message = str(message).strip()
        if not user_message:
            return True
        active = self._ensure_agent_conversation()
        outcome = self.workspace_agent.handle_message(
            active.session_id,
            user_message,
            workspace="translation" if workspace == "translation" else "chat",
        )
        if not outcome.handled:
            return False

        assistant_message = outcome.assistant_message.strip()
        if not assistant_message:
            return True
        conversation = self._record_workspace_exchange(
            user_message,
            assistant_message,
            render_in_chat=render_in_chat,
        )
        self._execute_workspace_outcome(outcome, conversation)
        return True

    def _execute_workspace_outcome(
        self,
        outcome: WorkspaceAgentOutcome,
        conversation: Conversation,
    ) -> None:
        if outcome.ui_command == OPEN_TRANSLATION_COMMAND:
            self._enter_agent_translation_workspace(outcome.assistant_message)
            return
        if outcome.ui_command == RETURN_TO_CHAT_COMMAND:
            self._return_from_agent_translation_workspace(conversation)

    def _enter_agent_translation_workspace(self, assistant_message: str) -> None:
        """Execute the graph-approved translation workspace tool call."""

        self._chat_request_versions.next_request_id()
        self._cancel_active_stream()
        self._agent_translation_active = True
        source_language, target_language = self._configured_language_pair()
        try:
            self.overlay_manager.show_translation(
                self._last_source_text or "",
                self._last_translation_text or "",
                source_language,
                target_language,
            )
            self.overlay_manager.enter_agent_translation_mode(assistant_message)
        except Exception as exc:
            self._agent_translation_active = False
            self._log_exception("agent_translation_workspace_open_failed", exc)
            return
        self._overlay_visible = True
        self._safe_call(
            "tray_overlay_visibility_update_failed",
            self.tray_manager.set_overlay_visible,
            True,
        )
        self.logger.info("agent_workspace_entered workspace=translation")

    def _return_from_agent_translation_workspace(
        self,
        conversation: Conversation | None = None,
    ) -> None:
        """End the translation task and restore the full conversation surface."""

        self._chat_request_versions.next_request_id()
        self._cancel_active_stream()
        self._agent_translation_active = False
        self._chat_overlay_call("leave_agent_translation_mode")
        active = conversation or self.conversation_manager.active
        if active is None:
            self._open_ai_chat()
        else:
            self._show_managed_conversation(active)
        self.logger.info("agent_workspace_returned workspace=chat")

    def _refresh_agent_translation_context(self) -> None:
        """Make the latest editable translation state available to AI chat."""

        if not self._agent_translation_active:
            return
        active = self.conversation_manager.active
        if active is None:
            return
        active.context = self._current_reading_context()
        active.touch()
        self.conversation_manager.save()

    def _submit_chat_message(self, message: str) -> None:
        """Route control intents through the Workspace Agent before normal LLM chat."""

        user_message = str(message).strip()
        if not user_message:
            return
        workspace = "translation" if self._agent_translation_active else "chat"
        if self._handle_workspace_agent_turn(
            user_message,
            workspace=workspace,
            render_in_chat=self._is_ai_chat_open(),
        ):
            return

        if self._agent_translation_active:
            self._refresh_agent_translation_context()
            self._chat_overlay_call("set_agent_workspace_reply", "", streaming=False)
        super()._submit_chat_message(user_message)
        if self._agent_translation_active:
            if self._active_stream_request_id is not None:
                self._chat_overlay_call("set_agent_workspace_busy", True)
            else:
                self._chat_overlay_call(
                    "set_agent_workspace_error",
                    STREAM_CHAT_ERROR_TEXT,
                )

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        if key == "agent_workspace_send":
            self._submit_chat_message(str(value or ""))
            return
        if key == "agent_workspace_stop":
            self._stop_chat_generation()
            return
        super()._on_overlay_context_action(key, value)

    def _on_chat_stream_chunk(self, chunk: object) -> None:
        should_mirror = False
        if isinstance(chunk, AIChatStreamChunk):
            active = self.conversation_manager.active
            should_mirror = bool(
                self._agent_translation_active
                and self._chat_request_versions.is_latest(chunk.request_id)
                and active is not None
                and chunk.session_id == active.session_id
            )
        super()._on_chat_stream_chunk(chunk)
        if should_mirror and isinstance(chunk, AIChatStreamChunk):
            self._chat_overlay_call(
                "set_agent_workspace_reply",
                chunk.accumulated_text,
                streaming=True,
            )
            self._chat_overlay_call("set_agent_workspace_busy", True)

    def _on_chat_task_succeeded(self, result: object) -> None:
        should_mirror = False
        if isinstance(result, ChatResult):
            active = self.conversation_manager.active
            should_mirror = bool(
                self._agent_translation_active
                and self._chat_request_versions.is_latest(result.request_id)
                and active is not None
                and result.session_id == active.session_id
            )
        super()._on_chat_task_succeeded(result)
        if should_mirror and isinstance(result, ChatResult):
            self._chat_overlay_call(
                "set_agent_workspace_reply",
                result.output_text,
                streaming=False,
            )
            self._chat_overlay_call("set_agent_workspace_busy", False)

    def _on_chat_task_failed(self, failure: object) -> None:
        should_mirror = bool(
            self._agent_translation_active
            and isinstance(failure, AIChatTaskFailure)
            and self._chat_request_versions.is_latest(failure.request_id)
        )
        super()._on_chat_task_failed(failure)
        if should_mirror:
            self._chat_overlay_call(
                "set_agent_workspace_error",
                STREAM_CHAT_ERROR_TEXT,
            )

    def _stop_chat_generation(self) -> None:
        partial = self._active_stream_partial.strip()
        super()._stop_chat_generation()
        if self._agent_translation_active:
            if partial:
                self._chat_overlay_call(
                    "set_agent_workspace_reply",
                    partial,
                    streaming=False,
                )
            self._chat_overlay_call("set_agent_workspace_busy", False)

    def _cancel_active_stream(self, *, reset_busy: bool = True) -> None:
        super()._cancel_active_stream(reset_busy=reset_busy)
        if self._agent_translation_active and reset_busy:
            self._chat_overlay_call("set_agent_workspace_busy", False)

    def _new_ai_chat(self) -> None:
        if self._agent_translation_active:
            self._agent_translation_active = False
            self._chat_overlay_call("leave_agent_translation_mode")
        super()._new_ai_chat()

    def _switch_ai_chat(self, conversation_id: str) -> None:
        if self._agent_translation_active:
            self._agent_translation_active = False
            self._chat_overlay_call("leave_agent_translation_mode")
        super()._switch_ai_chat(conversation_id)


__all__ = ["AgentWorkspaceAppController"]
