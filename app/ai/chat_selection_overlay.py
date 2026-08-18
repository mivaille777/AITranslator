"""Conversation Overlay with selection capture, history and model switching."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtGui import QAction

from app.ai.chat.models import ChatMessage
from app.ai.chat_interaction_ui import InteractiveManagedChatPanel
from app.ai.chat_overlay import (
    ConversationalAIOverlayManager,
    ConversationalAIOverlayWindow,
)
from app.overlay.context_menu import OVERLAY_THEMES, symbol_icon
from app.overlay.drag_handle import OverlayDragHandle
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


class SelectionCaptureConversationalAIOverlayWindow(ConversationalAIOverlayWindow):
    """Chat Overlay with robust dragging and compact ChatGPT-style controls."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._chat_config_manager = kwargs.get("config_manager")
        super().__init__(*args, **kwargs)

        old_panel = self._chat_panel
        old_panel.hide()
        self._layout.removeWidget(old_panel)
        old_panel.setParent(None)
        old_panel.deleteLater()

        self._chat_panel = InteractiveManagedChatPanel(self)
        self._chat_panel.hide()
        self._layout.addWidget(self._chat_panel)
        self._chat_panel.message_submitted.connect(
            lambda text: self.context_action.emit("ai_chat_send", text)
        )
        self._chat_panel.clear_requested.connect(
            lambda: self.context_action.emit("ai_chat_clear", None)
        )
        self._chat_panel.close_requested.connect(
            lambda: self.context_action.emit("ai_chat_close", None)
        )
        self._chat_panel.new_conversation_requested.connect(
            lambda: self.context_action.emit("ai_chat_new", None)
        )
        self._chat_panel.conversation_selected.connect(
            lambda conversation_id: self.context_action.emit(
                "ai_chat_switch",
                conversation_id,
            )
        )
        self._chat_panel.conversation_delete_requested.connect(
            lambda conversation_id: self.context_action.emit(
                "ai_chat_delete",
                conversation_id,
            )
        )
        self._chat_panel.conversation_rename_requested.connect(
            lambda payload: self.context_action.emit("ai_chat_rename", payload)
        )
        self._chat_panel.model_selected.connect(
            lambda payload: self.context_action.emit("ai_chat_model", payload)
        )
        self._chat_panel.stop_generation_requested.connect(
            lambda: self.context_action.emit("ai_chat_stop", None)
        )
        self._chat_panel.regenerate_requested.connect(
            lambda content: self.context_action.emit("ai_chat_regenerate", content)
        )

        self._chat_panel.title_label.installEventFilter(self)
        self._drag_handle = OverlayDragHandle(self._header)
        self._drag_handle.installEventFilter(self)
        self._drag_handle.show()
        self._position_drag_handle()

        # Mirror the Settings-window checkbox with a fast context-menu toggle.
        # Both controls persist the same non-secret ai.chat_selection_capture_enabled
        # value, so users can change the behavior without reopening the dialog.
        self._chat_capture_action = QAction(
            "Chat 划词自动填入",
            self._context_menu.settings_menu,
        )
        self._chat_capture_action.setObjectName(
            "OverlayContextChatSelectionCaptureAction"
        )
        self._chat_capture_action.setCheckable(True)
        self._chat_capture_action.setToolTip(
            "Chat 输入框有光标时，将外部鼠标划词自动填入输入框"
        )
        self._chat_capture_action.triggered.connect(
            self._set_chat_selection_capture_preference
        )
        self._context_menu.settings_menu.add_scrollable_action(
            self._chat_capture_action
        )
        self._context_menu.aboutToShow.connect(
            self._sync_chat_selection_capture_action
        )
        self._sync_chat_selection_capture_action()

        self._apply_theme(self._theme_name)
        self._resize_to_content()

    @property
    def chat_panel(self) -> InteractiveManagedChatPanel:
        return self._chat_panel

    @property
    def drag_handle(self) -> OverlayDragHandle:
        return self._drag_handle

    @property
    def chat_selection_capture_action(self) -> QAction:
        return self._chat_capture_action

    def _position_drag_handle(self) -> None:
        handle = getattr(self, "_drag_handle", None)
        header = getattr(self, "_header", None)
        if handle is None or header is None:
            return
        x = max(0, (header.width() - handle.width()) // 2)
        y = max(0, (header.height() - handle.height()) // 2)
        handle.move(x, y)
        handle.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._position_drag_handle()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override
        panel = getattr(self, "_chat_panel", None)
        handle = getattr(self, "_drag_handle", None)
        if panel is not None and watched is panel.title_label:
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonPress:
                self.mousePressEvent(event)
                return True
            if event_type == QEvent.Type.MouseMove:
                self.mouseMoveEvent(event)
                return True
            if event_type == QEvent.Type.MouseButtonRelease:
                self.mouseReleaseEvent(event)
                return True
        if handle is not None and watched is handle:
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonDblClick:
                if event.button() == Qt.MouseButton.LeftButton and self._chat_open:
                    self.close_chat()
                event.accept()
                return True
            if event_type == QEvent.Type.MouseButtonPress:
                self.mousePressEvent(event)
                return True
            if event_type == QEvent.Type.MouseMove:
                self.mouseMoveEvent(event)
                return True
            if event_type == QEvent.Type.MouseButtonRelease:
                self.mouseReleaseEvent(event)
                return True
        return super().eventFilter(watched, event)

    def open_chat(
        self,
        *,
        source_text: str = "",
        translated_text: str = "",
        provider: str = "",
        model: str = "",
        messages: tuple[ChatMessage, ...] = (),
    ) -> None:
        """Open Chat without leaving a resize/drag transition active."""

        self._stop_resize_animation()
        self._dragging = False
        self._drag_offset = QPoint()
        self._chat_open = True
        self._content_scroll.hide()
        self._chat_panel.set_context(source_text, translated_text)
        self._chat_panel.set_identity(provider, model)
        self._chat_panel.set_messages(messages)
        self._chat_panel.show()

        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self._resize_to_content(animate=False)
        self.show_overlay()
        self.activateWindow()
        self.raise_()
        self._dragging = False
        self._drag_offset = QPoint()
        self._position_drag_handle()
        QTimer.singleShot(0, self._chat_panel.focus_input)

    def _selection_capture_setting_enabled(self) -> bool:
        get = getattr(self._chat_config_manager, "get", None)
        if not callable(get):
            return True
        value = get("ai", "chat_selection_capture_enabled", True)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"0", "false", "no", "off"}:
                return False
            if normalized in {"1", "true", "yes", "on"}:
                return True
        return bool(value)

    def _sync_chat_selection_capture_action(self) -> None:
        action = getattr(self, "_chat_capture_action", None)
        if action is None:
            return
        blocked = action.blockSignals(True)
        action.setChecked(self._selection_capture_setting_enabled())
        action.blockSignals(blocked)

    def _set_chat_selection_capture_preference(self, enabled: bool) -> None:
        save = getattr(self._chat_config_manager, "save", None)
        if callable(save):
            try:
                save(
                    {
                        "ai": {
                            "chat_selection_capture_enabled": bool(enabled),
                        }
                    }
                )
            except (OSError, TypeError, ValueError):
                self._sync_chat_selection_capture_action()
                return
        self._sync_chat_selection_capture_action()

    def is_chat_selection_capture_armed(self) -> bool:
        return bool(
            self._selection_capture_setting_enabled()
            and self._chat_open
            and self._chat_panel.selection_capture_armed
        )

    def insert_chat_selection(self, text: object) -> bool:
        if not self._chat_open or not self._selection_capture_setting_enabled():
            return False
        inserted = self._chat_panel.insert_selected_text(text)
        if not inserted:
            return False
        self.activateWindow()
        self.raise_()
        QTimer.singleShot(0, self._chat_panel.focus_input)
        return True

    def set_chat_conversations(
        self,
        items: tuple[dict[str, object], ...] | list[dict[str, object]],
        active_id: str = "",
    ) -> None:
        self._chat_panel.set_conversations(items, active_id)

    def set_chat_model_options(
        self,
        options: tuple[dict[str, str], ...] | list[dict[str, str]],
        *,
        current_provider: str = "",
        current_model: str = "",
    ) -> None:
        self._chat_panel.set_model_options(
            options,
            current_provider=current_provider,
            current_model=current_model,
        )

    def close_chat(self) -> None:
        self._chat_panel.disarm_selection_capture()
        self._dragging = False
        self._drag_offset = QPoint()
        super().close_chat()
        self._position_drag_handle()

    def _apply_theme(self, theme: str) -> None:
        super()._apply_theme(theme)
        handle = getattr(self, "_drag_handle", None)
        palette = OVERLAY_THEMES[self._theme_name]
        if handle is not None:
            handle.set_theme_colors(palette["muted_text"], palette["accent"])
        action = getattr(self, "_chat_capture_action", None)
        if action is not None:
            action.setIcon(symbol_icon("↪", palette["text"], size=18))


class SelectionCaptureConversationalAIOverlayManager(ConversationalAIOverlayManager):
    """Expose selection capture, history and model UI without leaking Qt widgets."""

    def __init__(
        self,
        window: OverlayWindow | None = None,
        *,
        position_manager: PositionManager | None = None,
        config_manager: Any | None = None,
    ) -> None:
        if window is None:
            resolved_position_manager = position_manager or PositionManager(
                config_manager=config_manager,
            )
            window = SelectionCaptureConversationalAIOverlayWindow(
                position_manager=resolved_position_manager,
                config_manager=config_manager,
            )
        super().__init__(window=window)

    def is_chat_selection_capture_armed(self) -> bool:
        getter = getattr(self.window, "is_chat_selection_capture_armed", None)
        if not callable(getter):
            return False
        return bool(getter())

    def insert_chat_selection(self, text: object) -> bool:
        inserter = getattr(self.window, "insert_chat_selection", None)
        if not callable(inserter):
            return False
        return bool(inserter(text))

    def set_chat_conversations(
        self,
        items: tuple[dict[str, object], ...] | list[dict[str, object]],
        active_id: str = "",
    ) -> None:
        setter = getattr(self.window, "set_chat_conversations", None)
        if callable(setter):
            setter(items, active_id)

    def set_chat_model_options(
        self,
        options: tuple[dict[str, str], ...] | list[dict[str, str]],
        *,
        current_provider: str = "",
        current_model: str = "",
    ) -> None:
        setter = getattr(self.window, "set_chat_model_options", None)
        if callable(setter):
            setter(
                options,
                current_provider=current_provider,
                current_model=current_model,
            )


__all__ = [
    "SelectionCaptureConversationalAIOverlayManager",
    "SelectionCaptureConversationalAIOverlayWindow",
]
