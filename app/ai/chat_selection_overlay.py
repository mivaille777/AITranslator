"""Conversation Overlay with selection capture, history and model switching."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer

from app.ai.chat.models import ChatMessage, ChatRole
from app.ai.chat_managed_ui import ManagedChatPanel
from app.ai.chat_overlay import (
    ConversationalAIOverlayManager,
    ConversationalAIOverlayWindow,
)
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


class SelectionCaptureConversationalAIOverlayWindow(ConversationalAIOverlayWindow):
    """Chat Overlay with robust dragging and compact ChatGPT-style controls."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        old_panel = self._chat_panel
        old_panel.hide()
        self._layout.removeWidget(old_panel)
        old_panel.setParent(None)
        old_panel.deleteLater()

        self._chat_panel = ManagedChatPanel(self)
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
        self._chat_panel.model_selected.connect(
            lambda payload: self.context_action.emit("ai_chat_model", payload)
        )

        # The outer Overlay header remains draggable, and the visible AI Chat
        # title becomes a second explicit drag handle. This fixes the first
        # Chat-open transition where keyboard activation could otherwise make
        # the card feel immovable until another window-state transition.
        self._chat_panel.title_label.installEventFilter(self)

        self._apply_theme(self._theme_name)
        self._resize_to_content()

    @property
    def chat_panel(self) -> ManagedChatPanel:
        return self._chat_panel

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override
        panel = getattr(self, "_chat_panel", None)
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

        # Chat needs keyboard focus, but window activation is kept separate
        # from drag state. Resize synchronously before activation so the first
        # mouse press on the header/title always starts a fresh drag gesture.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self._resize_to_content(animate=False)
        self.show_overlay()
        self.activateWindow()
        self.raise_()
        self._dragging = False
        self._drag_offset = QPoint()
        QTimer.singleShot(0, self._chat_panel.focus_input)

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
