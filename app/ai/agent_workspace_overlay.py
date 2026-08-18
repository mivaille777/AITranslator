"""Translation workspace that keeps a compact AI Agent conversation dock visible."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ai.editable_overlay import (
    EditableResizableConversationalAIOverlayManager,
    EditableResizableConversationalAIOverlayWindow,
)
from app.overlay.context_menu import OVERLAY_THEMES
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


AGENT_DOCK_COMPACT_WIDTH = 560
AGENT_DOCK_MAX_HEIGHT = 186
AGENT_REPLY_MAX_HEIGHT = 72


class AgentWorkspaceInput(QPlainTextEdit):
    """Compact Agent input: Enter sends, Shift+Enter inserts a newline."""

    submit_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            event.accept()
            self.submit_requested.emit()
            return
        super().keyPressEvent(event)


class TranslationAgentDock(QFrame):
    """Small conversational surface that remains visible during translation."""

    message_submitted = Signal(str)
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._compact = False
        self.setObjectName("OverlayTranslationAgentDock")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setMaximumHeight(AGENT_DOCK_MAX_HEIGHT)

        root = QVBoxLayout(self)
        root.setContentsMargins(7, 5, 7, 7)
        root.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(5)
        self.title_label = QLabel("AI · 翻译协作", self)
        self.title_label.setObjectName("OverlayTranslationAgentTitle")
        self.state_label = QLabel("就绪", self)
        self.state_label.setObjectName("OverlayTranslationAgentState")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.return_button = QPushButton("↩ 对话", self)
        self.return_button.setObjectName("OverlayTranslationAgentReturn")
        self.return_button.setToolTip("结束翻译任务并返回完整 AI 对话")
        self.return_button.setFixedSize(64, 26)
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        title_row.addWidget(self.state_label)
        title_row.addWidget(self.return_button)
        root.addLayout(title_row)

        self.reply_label = QLabel("", self)
        self.reply_label.setObjectName("OverlayTranslationAgentReply")
        self.reply_label.setTextFormat(Qt.TextFormat.MarkdownText)
        self.reply_label.setWordWrap(True)
        self.reply_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.reply_label.setMaximumHeight(AGENT_REPLY_MAX_HEIGHT)
        self.reply_label.hide()
        root.addWidget(self.reply_label)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(5)
        self.input_edit = AgentWorkspaceInput(self)
        self.input_edit.setObjectName("OverlayTranslationAgentInput")
        self.input_edit.setPlaceholderText("继续问 AI；说“翻译完了”返回对话…")
        self.input_edit.setMinimumHeight(38)
        self.input_edit.setMaximumHeight(58)
        self.input_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.input_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.send_button = QPushButton("发送", self)
        self.send_button.setObjectName("OverlayTranslationAgentSend")
        self.send_button.setFixedSize(58, 38)
        self.stop_button = QPushButton("■ 停止", self)
        self.stop_button.setObjectName("OverlayTranslationAgentStop")
        self.stop_button.setFixedSize(68, 38)
        self.stop_button.hide()
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.stop_button)
        input_row.addWidget(self.send_button)
        root.addLayout(input_row)

        self.input_edit.submit_requested.connect(self._submit)
        self.send_button.clicked.connect(self._submit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        # This convenience affordance intentionally goes through the same
        # natural-language Workspace Agent path as typing “翻译完了”.
        self.return_button.clicked.connect(
            lambda: self.message_submitted.emit("翻译完了")
        )

    def _submit(self) -> None:
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        self.input_edit.clear()
        self.message_submitted.emit(text)

    def set_compact(self, compact: bool) -> None:
        """Prioritize translation content when the floating card is narrow."""

        resolved = bool(compact)
        if resolved == self._compact:
            return
        self._compact = resolved
        self.state_label.setVisible(not resolved)
        self.title_label.setText("AI · 翻译" if resolved else "AI · 翻译协作")
        self.return_button.setText("↩" if resolved else "↩ 对话")
        self.return_button.setFixedWidth(32 if resolved else 64)
        self.return_button.setToolTip("返回完整 AI 对话")

    def set_reply(self, text: object, *, streaming: bool = False) -> None:
        content = str(text or "").strip()
        self.reply_label.setText(content)
        self.reply_label.setVisible(bool(content))
        self.state_label.setText("回答中…" if streaming else "就绪")

    def set_busy(self, busy: bool) -> None:
        active = bool(busy)
        self.input_edit.setEnabled(not active)
        self.send_button.setVisible(not active)
        self.send_button.setEnabled(not active)
        self.stop_button.setVisible(active)
        self.stop_button.setEnabled(active)
        self.return_button.setEnabled(not active)
        self.state_label.setText("回答中…" if active else "就绪")
        if not active:
            self.input_edit.setFocus()

    def set_error(self, message: object) -> None:
        self.set_busy(False)
        self.state_label.setText("请求失败")
        self.set_reply(str(message or "AI 请求失败。"), streaming=False)

    def apply_palette(self, palette: dict[str, str]) -> None:
        self.setStyleSheet(
            f"""
            QFrame#OverlayTranslationAgentDock {{
                background-color: {palette['menu_background']};
                border: 1px solid {palette['border']};
                border-radius: 9px;
            }}
            QLabel#OverlayTranslationAgentTitle {{
                color: {palette['accent']};
                font-weight: 600;
            }}
            QLabel#OverlayTranslationAgentState {{
                color: {palette['muted_text']};
                font-size: 10px;
            }}
            QLabel#OverlayTranslationAgentReply {{
                color: {palette['text']};
                background: transparent;
                padding: 1px 1px 3px 1px;
            }}
            QPlainTextEdit#OverlayTranslationAgentInput {{
                color: {palette['text']};
                background-color: {palette['label_background']};
                border: 1px solid {palette['border']};
                border-radius: 7px;
                padding: 5px 7px;
                selection-background-color: {palette['accent']};
            }}
            QPlainTextEdit#OverlayTranslationAgentInput:focus {{
                border-color: {palette['accent']};
            }}
            QPushButton#OverlayTranslationAgentSend,
            QPushButton#OverlayTranslationAgentStop,
            QPushButton#OverlayTranslationAgentReturn {{
                color: {palette['text']};
                background-color: transparent;
                border: 1px solid {palette['border']};
                border-radius: 7px;
            }}
            QPushButton#OverlayTranslationAgentSend:hover,
            QPushButton#OverlayTranslationAgentStop:hover,
            QPushButton#OverlayTranslationAgentReturn:hover {{
                background-color: {palette['hover']};
                border-color: {palette['accent']};
            }}
            QPushButton#OverlayTranslationAgentReturn {{
                color: {palette['muted_text']};
                font-size: 11px;
            }}
            """
        )

    def set_display_font_size(self, size: int) -> None:
        resolved = max(9, min(24, int(size)))
        body_font = QFont(self.font())
        body_font.setPointSize(resolved)
        input_font = QFont(self.font())
        input_font.setPointSize(max(9, round(resolved * 0.9)))
        self.reply_label.setFont(body_font)
        self.input_edit.setFont(input_font)


class AgentWorkspaceOverlayWindow(EditableResizableConversationalAIOverlayWindow):
    """Editable translation view with a persistent compact Agent dock."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._agent_translation_mode = False
        super().__init__(*args, **kwargs)

        self._agent_dock = TranslationAgentDock(self)
        self._agent_dock.hide()
        chat_index = self._layout.indexOf(self._chat_panel)
        self._layout.insertWidget(max(0, chat_index), self._agent_dock)
        self._agent_dock.message_submitted.connect(
            lambda text: self.context_action.emit("agent_workspace_send", text)
        )
        self._agent_dock.stop_requested.connect(
            lambda: self.context_action.emit("agent_workspace_stop", None)
        )
        self._agent_dock.apply_palette(OVERLAY_THEMES[self._theme_name])
        self._agent_dock.set_display_font_size(max(10, round(self._font_size * 0.54)))
        self._sync_agent_dock_responsiveness()

    @property
    def agent_translation_mode(self) -> bool:
        return self._agent_translation_mode

    @property
    def agent_dock(self) -> TranslationAgentDock:
        return self._agent_dock

    def _sync_agent_dock_responsiveness(self) -> None:
        dock = getattr(self, "_agent_dock", None)
        if dock is not None:
            dock.set_compact(self.width() < AGENT_DOCK_COMPACT_WIDTH)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._sync_agent_dock_responsiveness()

    def enter_agent_translation_mode(self, assistant_message: object = "") -> None:
        """Expose translation controls while keeping an Agent input available."""

        self._agent_translation_mode = True
        if self._chat_open:
            super().close_chat()
        self._content_scroll.show()
        self.set_original_visible(True)
        self._agent_dock.set_reply(assistant_message, streaming=False)
        self._agent_dock.set_busy(False)
        self._agent_dock.show()
        self._sync_agent_dock_responsiveness()
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self._resize_to_content(animate=False)
        self.show_overlay()
        self.activateWindow()
        self.raise_()
        self._source_editor.setFocus()

    def leave_agent_translation_mode(self) -> None:
        self._agent_translation_mode = False
        self._agent_dock.hide()
        self._agent_dock.set_busy(False)
        self._agent_dock.set_reply("")
        if not self._chat_open:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._resize_to_content(animate=False)

    def open_chat(self, **kwargs: Any) -> None:
        self._agent_dock.hide()
        super().open_chat(**kwargs)

    def close_chat(self) -> None:
        super().close_chat()
        if self._agent_translation_mode:
            self._agent_dock.show()
            self._sync_agent_dock_responsiveness()
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
            self._resize_to_content(animate=False)

    def set_agent_workspace_reply(self, text: object, *, streaming: bool = False) -> None:
        self._agent_dock.set_reply(text, streaming=streaming)
        if self._agent_translation_mode and not self._chat_open:
            self._agent_dock.show()
            self._resize_to_content(animate=False)

    def set_agent_workspace_busy(self, busy: bool) -> None:
        self._agent_dock.set_busy(busy)

    def set_agent_workspace_error(self, message: object) -> None:
        self._agent_dock.set_error(message)

    def _apply_theme(self, theme: str) -> None:
        super()._apply_theme(theme)
        dock = getattr(self, "_agent_dock", None)
        if dock is not None:
            dock.apply_palette(OVERLAY_THEMES[self._theme_name])

    def _scale_fonts_for_manual_size(self, new_size: QSize) -> None:
        super()._scale_fonts_for_manual_size(new_size)
        dock = getattr(self, "_agent_dock", None)
        if dock is not None:
            dock.set_display_font_size(max(10, round(self._font_size * 0.54)))


class AgentWorkspaceOverlayManager(EditableResizableConversationalAIOverlayManager):
    """Manager boundary exposing Agent translation-workspace operations."""

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
            window = AgentWorkspaceOverlayWindow(
                position_manager=resolved_position_manager,
                config_manager=config_manager,
            )
        super().__init__(window=window)

    def enter_agent_translation_mode(self, assistant_message: object = "") -> None:
        callback = getattr(self.window, "enter_agent_translation_mode", None)
        if callable(callback):
            callback(assistant_message)

    def leave_agent_translation_mode(self) -> None:
        callback = getattr(self.window, "leave_agent_translation_mode", None)
        if callable(callback):
            callback()

    def set_agent_workspace_reply(self, text: object, *, streaming: bool = False) -> None:
        callback = getattr(self.window, "set_agent_workspace_reply", None)
        if callable(callback):
            callback(text, streaming=streaming)

    def set_agent_workspace_busy(self, busy: bool) -> None:
        callback = getattr(self.window, "set_agent_workspace_busy", None)
        if callable(callback):
            callback(busy)

    def set_agent_workspace_error(self, message: object) -> None:
        callback = getattr(self.window, "set_agent_workspace_error", None)
        if callable(callback):
            callback(message)


__all__ = [
    "AGENT_DOCK_COMPACT_WIDTH",
    "AGENT_DOCK_MAX_HEIGHT",
    "AgentWorkspaceInput",
    "AgentWorkspaceOverlayManager",
    "AgentWorkspaceOverlayWindow",
    "TranslationAgentDock",
]
