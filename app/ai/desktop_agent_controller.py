"""Production Desktop Context Agent controller."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFileDialog

from app.agent.desktop_tool_runtime import DesktopAgentToolCoordinator
from app.agent.tool_runtime import AgentToolPlan
from app.ai.agent_workspace_controller import AgentWorkspaceAppController
from app.ai.desktop_agent_overlay import DesktopAgentOverlayManager
from app.ai.chat import ChatContext, ChatRole, ReadingContext
from app.ai.tool_task import AgentToolTask
from app.controller import INPUT_TEXT_ERROR_TEXT, SELECTION_ERROR_TEXT
from app.infrastructure.settings import SettingsManager
from app.input.mouse_selection_manager import MOUSE_SELECTION_SOURCE
from app.models.events import TranslationTriggerEvent
from app.models.selection import SelectedText, SelectionContext
from app.selection.browser_bridge import BrowserSelectionBridge
from app.selection.errors import SelectionError
from app.selection.foreground import ForegroundApplicationDetector
from app.translation.errors import TextNormalizationError


class DesktopAgentAppController(AgentWorkspaceAppController):
    """Extend the existing Agent with browser context and local workspace access."""

    def __init__(
        self,
        *args: Any,
        tool_runtime: DesktopAgentToolCoordinator | None = None,
        foreground_detector: ForegroundApplicationDetector | Any | None = None,
        browser_selection_bridge: BrowserSelectionBridge | Any | None = None,
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
        bridge = browser_selection_bridge or BrowserSelectionBridge(
            logger=kwargs.get("logger"),
        )
        super().__init__(
            *args,
            tool_runtime=tool_runtime or DesktopAgentToolCoordinator(),
            **kwargs,
        )
        self.browser_selection_bridge = bridge
        self._selection_foreground_detector = (
            foreground_detector or ForegroundApplicationDetector()
        )
        self._active_reading_context = ReadingContext()
        self._reading_context_source_text = ""
        self._reading_context_translation_text = ""
        # The base controller still exposes a legacy test-text tray route.
        # Production double-click/show intents should restore the real Overlay
        # exactly as it was instead of replacing its content with test text.
        self.tray_manager.show_overlay_requested.connect(
            self._show_overlay_from_tray,
        )

    @property
    def desktop_tool_runtime(self) -> DesktopAgentToolCoordinator:
        return self.tool_runtime  # type: ignore[return-value]

    @property
    def workspace_root(self) -> str:
        return self.desktop_tool_runtime.workspace_root

    def start(self, *, start_hotkey: bool = True) -> None:
        """Start the local browser bridge before enabling selection listeners."""

        if start_hotkey and not self._shutdown:
            try:
                self.browser_selection_bridge.start()
            except Exception as exc:
                # Browser extension capture is an optimization. Stage-2 UIA
                # remains fully usable when the local bridge cannot bind.
                self._log_exception("browser_selection_bridge_start_failed", exc)
        super().start(start_hotkey=start_hotkey)

    def shutdown(self) -> None:
        """Stop the browser receiver and then release the normal app services."""

        bridge = getattr(self, "browser_selection_bridge", None)
        stop = getattr(bridge, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception as exc:
                self._log_exception("browser_selection_bridge_stop_failed", exc)
        super().shutdown()

    def _capture_native_selection_context(self) -> SelectionContext:
        """Compatibility fallback when a caller did not freeze mouse-up context."""

        cursor = QCursor.pos()
        detector = self._selection_foreground_detector

        hwnd = None
        process_name = None
        snapshot = getattr(detector, "snapshot", None)
        if callable(snapshot):
            try:
                hwnd, process_name = snapshot()
            except Exception:
                hwnd = None
                process_name = None
        else:
            window_handle = getattr(detector, "window_handle", None)
            if callable(window_handle):
                try:
                    hwnd = window_handle()
                except Exception:
                    hwnd = None
            executable_name = getattr(detector, "executable_name", None)
            if callable(executable_name):
                try:
                    process_name = executable_name()
                except Exception:
                    process_name = None

        return SelectionContext(
            release_x=cursor.x(),
            release_y=cursor.y(),
            foreground_hwnd=hwnd,
            process_name=str(process_name) if process_name else None,
        )

    def _set_reading_context(
        self,
        selected_text: str,
        reading: ReadingContext,
    ) -> None:
        """Bind one bounded reading context to the selection that produced it."""

        self._active_reading_context = reading
        self._reading_context_source_text = str(selected_text or "").strip()
        self._reading_context_translation_text = ""

    def _remember_browser_bridge_context(
        self,
        context: SelectionContext,
    ) -> object | None:
        """Cache browser metadata and return the matched structured snapshot."""

        latest_snapshot = getattr(
            self.browser_selection_bridge,
            "latest_snapshot",
            None,
        )
        if not callable(latest_snapshot):
            return None
        try:
            snapshot = latest_snapshot(context=context)
        except Exception:
            return None

        remember_context = getattr(
            self.desktop_tool_runtime.browser_tools,
            "remember_context",
            None,
        )
        if callable(remember_context) and getattr(snapshot, "url", ""):
            try:
                remember_context(
                    snapshot.url,
                    getattr(snapshot, "title", ""),
                    source="selection_bridge",
                )
            except Exception as exc:
                self._log_exception("browser_bridge_context_cache_failed", exc)

        self._set_reading_context(
            getattr(snapshot, "text", ""),
            ReadingContext(
                resource_url=str(getattr(snapshot, "url", "") or "").strip(),
                resource_title=str(getattr(snapshot, "title", "") or "").strip(),
                section_heading=str(getattr(snapshot, "heading", "") or "").strip(),
                context_before=str(
                    getattr(snapshot, "context_before", "") or ""
                ).strip(),
                context_after=str(
                    getattr(snapshot, "context_after", "") or ""
                ).strip(),
                source_kind="browser_selection",
            ),
        )
        return snapshot

    def _capture_automatic_selection(
        self,
        context: SelectionContext,
    ) -> SelectedText:
        """Prefer the DOM bridge, then fall back to zero-keyboard native APIs."""

        bridge_capture = getattr(
            self.browser_selection_bridge,
            "get_selected_text_with_context",
            None,
        )
        if callable(bridge_capture):
            try:
                selected = bridge_capture(context)
            except SelectionError as exc:
                self.logger.debug(
                    "browser_selection_bridge_miss error_type=%s",
                    type(exc).__name__,
                )
            except Exception as exc:
                self._log_exception("browser_selection_bridge_capture_failed", exc)
            else:
                self._remember_browser_bridge_context(context)
                return selected

        capture_native = getattr(
            self.selection_manager,
            "get_selected_text_native",
            None,
        )
        if not callable(capture_native):
            raise SelectionError("native selection capture is unavailable")
        selected = capture_native(context=context)
        # A Word/UIA selection must not inherit URL/heading/context from the
        # previous browser selection.
        self._set_reading_context(
            selected.text,
            ReadingContext(source_kind=selected.provider),
        )
        return selected

    def _current_reading_context(self) -> ChatContext:
        """Return current selected text plus metadata tied to that exact selection."""

        base = super()._current_reading_context()
        source_text = str(base.source_text or "").strip()
        if source_text and source_text == self._reading_context_source_text:
            return ChatContext(
                source_text=source_text,
                translated_text=self._reading_context_translation_text,
                reading=self._active_reading_context,
            )
        return base

    def _sync_active_reading_context(self) -> None:
        """Update the active conversation without deleting its message history."""

        manager = getattr(self, "conversation_manager", None)
        active = getattr(manager, "active", None)
        if manager is None or active is None:
            return
        update = getattr(manager, "update_active_context", None)
        if not callable(update):
            return
        try:
            update(self._current_reading_context())
        except Exception as exc:
            self._log_exception("reading_context_sync_failed", exc)

    def _on_translation_triggered(self, event: TranslationTriggerEvent) -> None:
        """Use zero-keyboard browser/native capture for automatic mouse selection."""

        if event.source != MOUSE_SELECTION_SOURCE:
            super()._on_translation_triggered(event)
            return

        self.logger.info("AUTO_SELECTION_TRIGGERED source=%s", event.source)
        if not self._translation_enabled:
            self.logger.info("auto_selection_ignored translation_paused")
            return
        if self._is_cursor_over_overlay():
            self.logger.info("auto_selection_ignored overlay_hover")
            return

        context = (
            event.selection_context
            if isinstance(event.selection_context, SelectionContext)
            else self._capture_native_selection_context()
        )
        self._hide_overlay_for_selection()

        try:
            selected = self._capture_automatic_selection(context)
        except SelectionError as exc:
            self.logger.info(
                "selection_failed mode=zero_keyboard error_type=%s",
                type(exc).__name__,
            )
            self._show_translation_error(SELECTION_ERROR_TEXT, "SelectionError")
            return
        except Exception as exc:
            self._log_exception("automatic_selection_unexpected_error", exc)
            self._show_translation_error(SELECTION_ERROR_TEXT, "SelectionError")
            return

        self.logger.info(
            "selection_captured text_length=%s provider=%s mode=zero_keyboard",
            len(selected.text),
            selected.provider,
        )
        self._last_source_text = selected.text
        self._sync_active_reading_context()

        try:
            translatable_text = self._prepare_selected_text(selected.text)
        except TextNormalizationError as exc:
            self.logger.info(
                "input_text_rejected error_type=%s",
                type(exc).__name__,
            )
            self._show_translation_error(INPUT_TEXT_ERROR_TEXT, "InputError")
            return

        self._submit_translation(translatable_text)

    def _show_translation(
        self,
        translated_text: str,
        *,
        source_text: str = "",
        source_language: str = "auto",
        target_language: str = "zh-CN",
    ) -> None:
        """Keep the persisted reading context synchronized with final translation."""

        super()._show_translation(
            translated_text,
            source_text=source_text,
            source_language=source_language,
            target_language=target_language,
        )
        if (
            str(source_text or "").strip()
            and str(source_text or "").strip() == self._reading_context_source_text
        ):
            self._reading_context_translation_text = str(translated_text or "").strip()
            self._sync_active_reading_context()

    def _show_overlay_from_tray(self) -> None:
        """Restore the existing Overlay and synchronize tray visibility state."""

        if self._shutdown:
            return
        try:
            self.overlay_manager.show_overlay()
        except Exception as exc:
            self._log_exception("overlay_tray_restore_failed", exc)
            return

        self._overlay_visible = True
        try:
            self.tray_manager.set_overlay_visible(True)
        except Exception as exc:
            self._log_exception("tray_overlay_visibility_update_failed", exc)
        self.logger.info("overlay_shown_from_tray")

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
