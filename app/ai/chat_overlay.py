"""Conversation-capable Overlay built on the existing AI translation Overlay."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolButton

from app.ai.chat.models import ChatMessage, ChatRole
from app.ai.chat.ui import OverlayChatPanel
from app.ai.overlay import AIOverlayManager, AIOverlayWindow
from app.overlay.context_menu import OVERLAY_THEMES, symbol_icon
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


class ConversationalAIOverlayWindow(AIOverlayWindow):
    """Add an explicit chat mode that reuses the existing Overlay card."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._chat_open = False

        self._chat_action = QAction("与 AI 对话", self.context_menu.ai_menu)
        self._chat_action.setObjectName("OverlayContextAIChatAction")
        self._chat_action.triggered.connect(
            lambda _checked=False: self._context_menu.action_requested.emit(
                "ai_chat",
                None,
            )
        )
        self.context_menu.ai_menu.addSeparator()
        self.context_menu.ai_menu.addAction(self._chat_action)

        self._chat_button = QToolButton(self._header)
        self._chat_button.setObjectName("OverlayChatButton")
        self._chat_button.setText("")
        self._chat_button.setToolTip("与 AI 对话")
        self._chat_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chat_button.setAutoRaise(True)
        self._chat_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._chat_button.setIconSize(QSize(22, 22))
        self._chat_button.setFixedSize(38, 34)
        self._chat_button.clicked.connect(
            lambda: self.context_action.emit("ai_chat", None)
        )
        copy_index = self._header_layout.indexOf(self._copy_button)
        self._header_layout.insertWidget(max(0, copy_index), self._chat_button)

        self._chat_panel = OverlayChatPanel(self)
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
    def chat_button(self) -> QToolButton:
        return self._chat_button

    @property
    def chat_action(self) -> QAction:
        return self._chat_action

    @property
    def chat_panel(self) -> OverlayChatPanel:
        return self._chat_panel

    @property
    def chat_open(self) -> bool:
        return self._chat_open

    def open_chat(
        self,
        *,
        source_text: str = "",
        translated_text: str = "",
        provider: str = "",
        model: str = "",
        messages: tuple[ChatMessage, ...] = (),
    ) -> None:
        """Switch the card from translation presentation to interactive chat."""

        previous_size = QSize(self.size())
        self._chat_open = True
        self._content_scroll.hide()
        self._chat_panel.set_context(source_text, translated_text)
        self._chat_panel.set_identity(provider, model)
        self._chat_panel.set_messages(messages)
        self._chat_panel.show()

        # Chat is explicitly requested by a click, so temporarily allow the
        # Overlay to activate and receive keyboard focus. Normal translation
        # presentation still retains WA_ShowWithoutActivating.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self._resize_to_content(animate=True, start_size=previous_size)
        self.show_overlay()
        self.activateWindow()
        self.raise_()
        QTimer.singleShot(0, self._chat_panel.focus_input)

    def close_chat(self) -> None:
        if not self._chat_open:
            return
        previous_size = QSize(self.size())
        self._chat_open = False
        self._chat_panel.hide()
        self._content_scroll.show()
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._resize_to_content(animate=True, start_size=previous_size)

    def clear_chat(self) -> None:
        self._chat_panel.clear_messages()

    def append_chat_message(self, role: ChatRole | str, text: str) -> None:
        self._chat_panel.append_message(role, text)
        if self._chat_open:
            self._resize_to_content()

    def set_chat_busy(self, busy: bool) -> None:
        self._chat_panel.set_busy(busy)

    def set_chat_error(self, message: str) -> None:
        self._chat_panel.set_error(message)

    def set_chat_identity(self, provider: str, model: str) -> None:
        self._chat_panel.set_identity(provider, model)

    def _apply_header_style(self, palette: dict[str, str]) -> None:
        super()._apply_header_style(palette)
        button = getattr(self, "_chat_button", None)
        if button is None:
            return
        button_background = self._rgba_with_opacity(
            palette["hover"],
            self._background_opacity * 0.34 * self._header_emphasis,
        )
        button_border = self._rgba_with_opacity(
            palette["border"],
            self._background_opacity * 0.78 * self._header_emphasis,
        )
        button_hover_background = self._rgba_with_opacity(
            palette["hover"],
            min(1.0, self._background_opacity * 0.92),
        )
        button.setStyleSheet(
            f"""
            QToolButton#OverlayChatButton {{
                background-color: {button_background};
                border: 1px solid {button_border};
                border-radius: 6px;
                padding: 2px 6px;
            }}
            QToolButton#OverlayChatButton:hover {{
                background-color: {button_hover_background};
                border: 1px solid {palette['accent']};
            }}
            """
        )

    def _apply_theme(self, theme: str) -> None:
        super()._apply_theme(theme)
        palette = OVERLAY_THEMES[self._theme_name]
        button = getattr(self, "_chat_button", None)
        if button is not None:
            button.setIcon(symbol_icon("↔", palette["accent"], size=22))
        action = getattr(self, "_chat_action", None)
        if action is not None:
            action.setIcon(symbol_icon("↔", palette["accent"], size=18))
        panel = getattr(self, "_chat_panel", None)
        if panel is not None:
            panel.apply_palette(palette)


class ConversationalAIOverlayManager(AIOverlayManager):
    """AI Overlay manager exposing chat operations without leaking QWidget details."""

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
            window = ConversationalAIOverlayWindow(
                position_manager=resolved_position_manager,
                config_manager=config_manager,
            )
        super().__init__(window=window)

    def open_chat(
        self,
        *,
        source_text: str = "",
        translated_text: str = "",
        provider: str = "",
        model: str = "",
        messages: tuple[ChatMessage, ...] = (),
    ) -> None:
        opener = getattr(self.window, "open_chat", None)
        if callable(opener):
            opener(
                source_text=source_text,
                translated_text=translated_text,
                provider=provider,
                model=model,
                messages=messages,
            )

    def close_chat(self) -> None:
        closer = getattr(self.window, "close_chat", None)
        if callable(closer):
            closer()

    def clear_chat(self) -> None:
        clear = getattr(self.window, "clear_chat", None)
        if callable(clear):
            clear()

    def append_chat_message(self, role: ChatRole | str, text: str) -> None:
        append = getattr(self.window, "append_chat_message", None)
        if callable(append):
            append(role, text)

    def set_chat_busy(self, busy: bool) -> None:
        setter = getattr(self.window, "set_chat_busy", None)
        if callable(setter):
            setter(busy)

    def set_chat_error(self, message: str) -> None:
        setter = getattr(self.window, "set_chat_error", None)
        if callable(setter):
            setter(message)

    def set_chat_identity(self, provider: str, model: str) -> None:
        setter = getattr(self.window, "set_chat_identity", None)
        if callable(setter):
            setter(provider, model)


__all__ = [
    "ConversationalAIOverlayManager",
    "ConversationalAIOverlayWindow",
]
