"""Production Desktop Context Agent controller."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFileDialog

from app.agent.desktop_tool_runtime import DesktopAgentToolCoordinator
from app.agent.tool_runtime import AgentToolPlan
from app.ai.agent_workspace_controller import AgentWorkspaceAppController
from app.ai.desktop_agent_overlay import DesktopAgentOverlayManager
from app.ai.chat import ChatRole
from app.ai.tool_task import AgentToolTask
from app.infrastructure.settings import SettingsManager


class DesktopAgentAppController(AgentWorkspaceAppController):
    """Extend the existing Agent with browser context and local workspace access."""

    def __init__(
        self,
        *args: Any,
        tool_runtime: DesktopAgentToolCoordinator | None = None,
        **kwargs: Any,
    ) -> None:
        if kwargs.get("overlay_manager") is None:
            resolved_config = kwargs.get("config_manager")
            if resolved_config is None:
                resolved_config = SettingsManager()
                kwargs["config_manager"] = resolved_config
            kwargs["overlay_manager"] = DesktopAgentOverlayManager(
                config_manager=resolved_config,
            )
        super().__init__(
            *args,
            tool_runtime=tool_runtime or DesktopAgentToolCoordinator(),
            **kwargs,
        )

    @property
    def desktop_tool_runtime(self) -> DesktopAgentToolCoordinator:
        return self.tool_runtime  # type: ignore[return-value]

    @property
    def workspace_root(self) -> str:
        return self.desktop_tool_runtime.workspace_root

    def _capture_browser_context(self) -> None:
        try:
            result = self.desktop_tool_runtime.browser_tools.capture_foreground()
        except Exception as exc:
            self._log_exception("agent_browser_context_capture_failed", exc)
            return
        if result.ok:
            self.logger.info(
                "agent_browser_context_captured host_available=true"
            )

    def _open_ai_chat(self) -> None:
        # Capture the external browser before open_chat() activates the Agent
        # window. Later messages such as “总结这个网页” can use this snapshot.
        self._capture_browser_context()
        super()._open_ai_chat()

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        if key == "agent_capture_browser_context":
            self._capture_browser_context()
            return
        super()._on_overlay_context_action(key, value)

    def _start_agent_tool(
        self,
        user_message: str,
        plan: AgentToolPlan,
        *,
        request_id: int,
    ) -> None:
        if plan.tool_name != "select_workspace" or not plan.requires_file_picker:
            super()._start_agent_tool(user_message, plan, request_id=request_id)
            return

        parent = getattr(self.overlay_manager, "window", None)
        try:
            selected_directory = QFileDialog.getExistingDirectory(
                parent,
                "选择允许 AI Agent 读取的工作区目录",
                "",
                QFileDialog.Option.ShowDirsOnly,
            )
        except Exception as exc:
            self._log_exception("agent_workspace_picker_failed", exc)
            selected_directory = ""
        if not selected_directory:
            self._present_tool_direct_reply(
                user_message,
                "已取消选择本地工作区。",
                user_already_rendered=False,
            )
            return

        self._cancel_active_stream()
        render_in_chat = self._is_ai_chat_open()
        if render_in_chat:
            self._chat_overlay_call("append_chat_message", ChatRole.USER, user_message)
            self._chat_overlay_call("set_chat_busy", True)
        if self._agent_translation_active:
            self._chat_overlay_call("set_agent_workspace_reply", "正在授权工作区…", streaming=False)
            self._chat_overlay_call("set_agent_workspace_busy", True)

        task = AgentToolTask(
            self.tool_runtime,
            user_message,
            selected_file=selected_directory,
            request_id=request_id,
            logger=self.logger,
        )
        self._active_tool_request_id = request_id
        self._agent_tool_tasks.add(task)
        task.signals.succeeded.connect(self._on_agent_tool_succeeded)
        task.signals.failed.connect(self._on_agent_tool_failed)
        task.signals.finished.connect(self._on_agent_tool_finished)
        self.logger.info(
            "agent_workspace_selection_submitted request_id=%s",
            request_id,
        )
        try:
            self.translation_pool.start(task)
        except Exception as exc:
            self._agent_tool_tasks.discard(task)
            self._active_tool_request_id = None
            self._log_exception("agent_workspace_task_start_failed", exc)
            self._present_tool_direct_reply(
                user_message,
                "本地工作区任务启动失败。",
                user_already_rendered=render_in_chat,
            )


__all__ = ["DesktopAgentAppController"]
