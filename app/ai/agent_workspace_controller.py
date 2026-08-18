"""Production controller for LangGraph-driven workspace and tool orchestration."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFileDialog

from app.agent.tool_runtime import AgentToolCoordinator, AgentToolPlan
from app.agent.workspace import (
    OPEN_TRANSLATION_COMMAND,
    RETURN_TO_CHAT_COMMAND,
    WorkspaceAgentCoordinator,
    WorkspaceAgentOutcome,
)
from app.ai.agent_workspace_overlay import AgentWorkspaceOverlayManager
from app.ai.chat import ChatRequest, ChatResult, ChatRole
from app.ai.chat.conversation_manager import Conversation
from app.ai.chat.streaming import AIChatStreamChunk, StreamingAIChatTask
from app.ai.chat.task import AIChatTaskFailure
from app.ai.editable_controller import EditableStreamingResizableAIAppController
from app.ai.errors import AIConfigurationError, AIError
from app.ai.streaming_controller import (
    STREAM_CHAT_CONFIG_ERROR_TEXT,
    STREAM_CHAT_ERROR_TEXT,
)
from app.ai.tool_task import AgentToolTask, AgentToolTaskFailure
from app.infrastructure.settings import SettingsManager


DOCUMENT_PICKER_FILTER = (
    "Supported documents (*.pdf *.docx *.txt *.md *.markdown);;"
    "PDF (*.pdf);;Word (*.docx);;Text/Markdown (*.txt *.md *.markdown)"
)


class AgentWorkspaceAppController(EditableStreamingResizableAIAppController):
    """Run workspace HITL and document/web tools around the streaming Chat Agent."""

    def __init__(
        self,
        *args: Any,
        workspace_agent: WorkspaceAgentCoordinator | None = None,
        tool_runtime: AgentToolCoordinator | None = None,
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
        self.tool_runtime = tool_runtime or AgentToolCoordinator()
        self._agent_translation_active = False
        self._tool_request_version = 0
        self._active_tool_request_id: int | None = None
        self._agent_tool_tasks: set[AgentToolTask] = set()
        super().__init__(*args, **kwargs)

    @property
    def agent_translation_active(self) -> bool:
        return self._agent_translation_active

    @property
    def current_document_name(self) -> str:
        session = self.tool_runtime.document_tools.current
        return session.name if session is not None else ""

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
        if self._agent_translation_active and not render_in_chat:
            self._chat_overlay_call(
                "set_agent_workspace_reply",
                assistant_message,
                streaming=False,
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

    def _restore_agent_translation_surface(self, assistant_message: str = "") -> None:
        if not self._agent_translation_active:
            return
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
            self._log_exception("agent_translation_workspace_restore_failed", exc)

    def _return_from_agent_translation_workspace(
        self,
        conversation: Conversation | None = None,
    ) -> None:
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
        if not self._agent_translation_active:
            return
        active = self.conversation_manager.active
        if active is None:
            return
        active.context = self._current_reading_context()
        active.touch()
        self.conversation_manager.save()

    def _next_tool_request_id(self) -> int:
        self._tool_request_version += 1
        return self._tool_request_version

    def _invalidate_active_tool_ui(self) -> int:
        request_id = self._next_tool_request_id()
        if self._active_tool_request_id is not None:
            self._active_tool_request_id = None
            self._chat_overlay_call("set_chat_busy", False)
            if self._agent_translation_active:
                self._chat_overlay_call("set_agent_workspace_busy", False)
            active = self.conversation_manager.active
            if active is not None and self._is_ai_chat_open():
                self._show_managed_conversation(active)
        return request_id

    def _submit_chat_message(self, message: str) -> None:
        """Route workspace controls, Agent tools, then ordinary LLM chat."""

        user_message = str(message).strip()
        if not user_message:
            return
        tool_request_id = self._invalidate_active_tool_ui()
        workspace = "translation" if self._agent_translation_active else "chat"
        if self._handle_workspace_agent_turn(
            user_message,
            workspace=workspace,
            render_in_chat=self._is_ai_chat_open(),
        ):
            return

        plan = self.tool_runtime.plan_message(user_message)
        if plan.handled:
            self._start_agent_tool(
                user_message,
                plan,
                request_id=tool_request_id,
            )
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

    def _start_agent_tool(
        self,
        user_message: str,
        plan: AgentToolPlan,
        *,
        request_id: int,
    ) -> None:
        selected_file = ""
        if plan.requires_file_picker:
            parent = getattr(self.overlay_manager, "window", None)
            try:
                selected_file, _selected_filter = QFileDialog.getOpenFileName(
                    parent,
                    "选择要交给 AI Agent 的文档",
                    "",
                    DOCUMENT_PICKER_FILTER,
                )
            except Exception as exc:
                self._log_exception("agent_document_picker_failed", exc)
                selected_file = ""
            if not selected_file:
                self._present_tool_direct_reply(
                    user_message,
                    "已取消选择文档。",
                    user_already_rendered=False,
                )
                return

        self._cancel_active_stream()
        render_in_chat = self._is_ai_chat_open()
        if render_in_chat:
            self._chat_overlay_call("append_chat_message", ChatRole.USER, user_message)
            self._chat_overlay_call("set_chat_busy", True)
        if self._agent_translation_active:
            self._chat_overlay_call("set_agent_workspace_reply", "工具执行中…", streaming=False)
            self._chat_overlay_call("set_agent_workspace_busy", True)

        task = AgentToolTask(
            self.tool_runtime,
            user_message,
            selected_file=selected_file,
            request_id=request_id,
            logger=self.logger,
        )
        self._active_tool_request_id = request_id
        self._agent_tool_tasks.add(task)
        task.signals.succeeded.connect(self._on_agent_tool_succeeded)
        task.signals.failed.connect(self._on_agent_tool_failed)
        task.signals.finished.connect(self._on_agent_tool_finished)
        self.logger.info(
            "agent_tool_submitted request_id=%s tool=%s message_length=%s",
            request_id,
            plan.tool_name,
            len(user_message),
        )
        try:
            self.translation_pool.start(task)
        except Exception as exc:
            self._agent_tool_tasks.discard(task)
            self._active_tool_request_id = None
            self._log_exception("agent_tool_task_start_failed", exc)
            self._present_tool_direct_reply(
                user_message,
                "工具任务启动失败。",
                user_already_rendered=render_in_chat,
            )

    def _on_agent_tool_succeeded(self, payload: object) -> None:
        if self._shutdown or not isinstance(payload, tuple) or len(payload) != 3:
            return
        request_id, user_message, outcome = payload
        if int(request_id) != self._active_tool_request_id:
            return
        self._active_tool_request_id = None
        self._chat_overlay_call("set_chat_busy", False)
        if self._agent_translation_active:
            self._chat_overlay_call("set_agent_workspace_busy", False)

        assistant_message = str(getattr(outcome, "assistant_message", "")).strip()
        tool_context = str(getattr(outcome, "tool_context", "")).strip()
        tool_name = str(getattr(outcome, "tool_name", "")).strip()
        requires_llm = bool(getattr(outcome, "requires_llm", False))

        if requires_llm and tool_context:
            self._submit_tool_grounded_chat(
                str(user_message),
                tool_name=tool_name,
                tool_context=tool_context,
                user_already_rendered=self._is_ai_chat_open(),
            )
            return
        if not assistant_message:
            assistant_message = "工具执行完成。"
        self._present_tool_direct_reply(
            str(user_message),
            assistant_message,
            user_already_rendered=self._is_ai_chat_open(),
        )

    def _on_agent_tool_failed(self, failure: object) -> None:
        if not isinstance(failure, AgentToolTaskFailure):
            return
        if failure.request_id != self._active_tool_request_id:
            return
        self._active_tool_request_id = None
        self._chat_overlay_call("set_chat_busy", False)
        if self._agent_translation_active:
            self._chat_overlay_call("set_agent_workspace_busy", False)
        self._present_tool_direct_reply(
            failure.user_message,
            "工具执行失败，请稍后重试。",
            user_already_rendered=self._is_ai_chat_open(),
        )

    def _on_agent_tool_finished(self, task: object) -> None:
        if isinstance(task, AgentToolTask):
            self._agent_tool_tasks.discard(task)

    def _present_tool_direct_reply(
        self,
        user_message: str,
        assistant_message: str,
        *,
        user_already_rendered: bool,
    ) -> None:
        conversation = self._ensure_agent_conversation()
        conversation = self.conversation_manager.append_exchange(
            user_message,
            assistant_message,
        )
        if self._is_ai_chat_open():
            if not user_already_rendered:
                self._chat_overlay_call("append_chat_message", ChatRole.USER, user_message)
            self._chat_overlay_call("append_chat_message", ChatRole.ASSISTANT, assistant_message)
            self._chat_overlay_call("set_chat_busy", False)
            self._sync_chat_controls(conversation)
        elif self._agent_translation_active:
            self._chat_overlay_call(
                "set_agent_workspace_reply",
                assistant_message,
                streaming=False,
            )
            self._chat_overlay_call("set_agent_workspace_busy", False)

    def _submit_tool_grounded_chat(
        self,
        user_message: str,
        *,
        tool_name: str,
        tool_context: str,
        user_already_rendered: bool,
    ) -> None:
        """Start the normal LangGraph chat stream with a bounded Tool Observation."""

        active = self._ensure_agent_conversation()
        if self._agent_translation_active:
            self._refresh_agent_translation_context()
            active = self._ensure_agent_conversation()

        self._cancel_active_stream()
        request_id = self._chat_request_versions.next_request_id()
        request = ChatRequest(
            session_id=active.session_id,
            user_message=user_message,
            context=active.context,
            history=tuple(active.messages),
            request_id=request_id,
            tool_name=tool_name,
            tool_context=tool_context,
        )
        if self._is_ai_chat_open() and not user_already_rendered:
            self._chat_overlay_call("append_chat_message", ChatRole.USER, user_message)
        self._chat_overlay_call("set_chat_busy", True)
        self._chat_overlay_call("begin_chat_stream", request_id)
        self._active_stream_request_id = request_id
        self._active_stream_user_message = user_message
        self._active_stream_partial = ""
        if self._agent_translation_active:
            self._chat_overlay_call("set_agent_workspace_busy", True)
            self._chat_overlay_call("set_agent_workspace_reply", "", streaming=False)

        try:
            service = self._ensure_chat_service()
        except AIConfigurationError:
            self._cancel_active_stream()
            self._chat_overlay_call("set_chat_error", STREAM_CHAT_CONFIG_ERROR_TEXT)
            if self._agent_translation_active:
                self._chat_overlay_call("set_agent_workspace_error", STREAM_CHAT_CONFIG_ERROR_TEXT)
            return
        except AIError as exc:
            self._cancel_active_stream()
            self._log_exception("tool_grounded_chat_start_failed", exc)
            self._chat_overlay_call("set_chat_error", STREAM_CHAT_ERROR_TEXT)
            return
        except Exception as exc:
            self._cancel_active_stream()
            self._log_exception("tool_grounded_chat_start_failed", exc)
            self._chat_overlay_call("set_chat_error", STREAM_CHAT_ERROR_TEXT)
            return

        task = StreamingAIChatTask(service, request, logger=self.logger)
        self._active_stream_task = task
        task.signals.chunk.connect(self._on_chat_stream_chunk)
        task.signals.succeeded.connect(self._on_chat_task_succeeded)
        task.signals.failed.connect(self._on_chat_task_failed)
        task.signals.finished.connect(self._on_chat_task_finished)
        self._chat_tasks.add(task)
        self.logger.info(
            "agent_tool_chat_submitted request_id=%s tool=%s observation_length=%s",
            request_id,
            tool_name,
            len(tool_context),
        )
        try:
            self.translation_pool.start(task)
        except Exception as exc:
            self._chat_tasks.discard(task)
            self._cancel_active_stream()
            self._log_exception("agent_tool_chat_task_start_failed", exc)
            self._chat_overlay_call("set_chat_error", STREAM_CHAT_ERROR_TEXT)

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
        was_agent_translation = self._agent_translation_active
        super()._stop_chat_generation()
        if was_agent_translation and self._agent_translation_active:
            if not partial and self._is_ai_chat_open():
                self._restore_agent_translation_surface()
            elif partial:
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
        self._next_tool_request_id()
        self._active_tool_request_id = None
        if self._agent_translation_active:
            self._agent_translation_active = False
            self._chat_overlay_call("leave_agent_translation_mode")
        super()._new_ai_chat()

    def _switch_ai_chat(self, conversation_id: str) -> None:
        self._next_tool_request_id()
        self._active_tool_request_id = None
        if self._agent_translation_active:
            self._agent_translation_active = False
            self._chat_overlay_call("leave_agent_translation_mode")
        super()._switch_ai_chat(conversation_id)


__all__ = ["AgentWorkspaceAppController", "DOCUMENT_PICKER_FILTER"]
