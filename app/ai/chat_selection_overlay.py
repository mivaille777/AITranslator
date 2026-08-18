"""Conversation Overlay variant that accepts captured mouse selections."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from app.ai.chat.models import ChatMessage, ChatRole
from app.ai.chat_selection_ui import SelectionCaptureChatPanel
from app.ai.chat_overlay import (
    ConversationalAIOverlayManager,
    ConversationalAIOverlayWindow,
)
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


class SelectionCaptureConversationalAIOverlayWindow(ConversationalAIOverlayWindow):
    """Replace the Stage 11 chat panel with a selection-aware input panel."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        old_panel = self._chat_panel
        old_panel.hide()
        self._layout.removeWidget(old_panel)
        old_panel.setParent(None)
        old_panel.deleteLater()

        self._chat_panel = SelectionCaptureChatPanel(self)
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
        self._apply_theme(self._theme_name)
        self._resize_to_content()

    @property
    def chat_panel(self) -> SelectionCaptureChatPanel:
        return self._chat_panel

    def is_chat_selection_capture_armed(self) -> bool:
        return bool(
            self._chat_open
            and self._chat_panel.selection_capture_armed
        )

    def insert_chat_selection(self, text: object) -> bool:
        if not self._chat_open:
            return False
        inserted = self._chat_panel.insert_selected_text(text)
        if not inserted:
            return False
        self.activateWindow()
        self.raise_()
        QTimer.singleShot(0, self._chat_panel.focus_input)
        return True

    def close_chat(self) -> None:
        self._chat_panel.disarm_selection_capture()
        super().close_chat()


class SelectionCaptureConversationalAIOverlayManager(ConversationalAIOverlayManager):
    """Expose selection-capture state without leaking Qt widgets to controllers."""

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


__all__ = [
    "SelectionCaptureConversationalAIOverlayManager",
    "SelectionCaptureConversationalAIOverlayWindow",
]
