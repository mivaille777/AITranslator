"""Compact conversational panel embedded inside the translation Overlay."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ai.chat.models import ChatMessage, ChatRole
from app.overlay.context_menu import symbol_icon


MESSAGE_COPY_FEEDBACK_MILLISECONDS = 1200
CHAT_WHEEL_SCROLL_STEP = 54
MESSAGE_COPY_ICON_SIZE = 17


class ChatInput(QPlainTextEdit):
    submit_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                event.accept()
                self.submit_requested.emit()
                return
        super().keyPressEvent(event)


class OverlayChatPanel(QWidget):
    """A bounded reading-assistant chat surface with fixed input controls."""

    message_submitted = Signal(str)
    clear_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("OverlayChatPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(300)
        self.setMaximumHeight(430)
        self._message_rows: list[QWidget] = []
        self._context_expanded = False
        self._palette: dict[str, str] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(7)

        top = QHBoxLayout()
        top.setContentsMargins(2, 0, 2, 0)
        self.title_label = QLabel("AI Chat")
        self.title_label.setObjectName("OverlayChatTitle")
        self.identity_label = QLabel("")
        self.identity_label.setObjectName("OverlayChatIdentity")
        self.identity_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.clear_button = QToolButton()
        self.clear_button.setObjectName("OverlayChatClearButton")
        self.clear_button.setText("清空")
        self.clear_button.setToolTip("清空当前对话")
        self.close_button = QToolButton()
        self.close_button.setObjectName("OverlayChatCloseButton")
        self.close_button.setText("×")
        self.close_button.setToolTip("返回翻译视图")
        top.addWidget(self.title_label)
        top.addWidget(self.identity_label, 1)
        top.addWidget(self.clear_button)
        top.addWidget(self.close_button)
        root.addLayout(top)

        self.context_button = QToolButton()
        self.context_button.setObjectName("OverlayChatContextButton")
        self.context_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.context_button.setText("📎 当前上下文 · 0 chars")
        self.context_button.setCheckable(True)
        self.context_button.setCursor(Qt.CursorShape.PointingHandCursor)
        root.addWidget(self.context_button)

        self.context_preview = QLabel("")
        self.context_preview.setObjectName("OverlayChatContextPreview")
        self.context_preview.setWordWrap(True)
        self.context_preview.setTextFormat(Qt.TextFormat.PlainText)
        self.context_preview.setMaximumHeight(96)
        self.context_preview.hide()
        root.addWidget(self.context_preview)

        self.messages_scroll = QScrollArea()
        self.messages_scroll.setObjectName("OverlayChatMessagesScroll")
        self.messages_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.messages_scroll.setWidgetResizable(True)
        self.messages_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.messages_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.messages_scroll.setMinimumHeight(140)
        self.messages_scroll.verticalScrollBar().setSingleStep(CHAT_WHEEL_SCROLL_STEP)

        self.messages_content = QWidget()
        self.messages_content.setObjectName("OverlayChatMessagesContent")
        self.messages_layout = QVBoxLayout(self.messages_content)
        self.messages_layout.setContentsMargins(4, 4, 4, 4)
        self.messages_layout.setSpacing(10)
        self.messages_layout.addStretch(1)
        self.messages_scroll.setWidget(self.messages_content)
        root.addWidget(self.messages_scroll, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("OverlayChatStatus")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        root.addWidget(self.status_label)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(6)
        self.input_edit = ChatInput()
        self.input_edit.setObjectName("OverlayChatInput")
        self.input_edit.setPlaceholderText("输入问题…  Enter 发送，Shift+Enter 换行")
        self.input_edit.setMinimumHeight(44)
        self.input_edit.setMaximumHeight(78)
        self.input_edit.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.input_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.input_edit.verticalScrollBar().setSingleStep(24)
        self.send_button = QPushButton("发送")
        self.send_button.setObjectName("OverlayChatSendButton")
        self.send_button.setFixedWidth(64)
        self.send_button.setMinimumHeight(44)
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.send_button)
        root.addLayout(input_row)

        self.send_button.clicked.connect(self._submit)
        self.input_edit.submit_requested.connect(self._submit)
        self.clear_button.clicked.connect(self.clear_requested)
        self.close_button.clicked.connect(self.close_requested)
        self.context_button.toggled.connect(self._toggle_context)

        # Wheel events over labels/rows normally stop at those widgets. Route
        # them to the conversation scrollbar so the entire AI reading surface
        # scrolls naturally without forcing the pointer onto the scrollbar.
        for widget in (
            self.title_label,
            self.identity_label,
            self.context_preview,
            self.status_label,
            self.messages_content,
        ):
            self._install_message_wheel_proxy(widget)

    @property
    def message_count(self) -> int:
        return len(self._message_rows)

    def _install_message_wheel_proxy(self, widget: QWidget) -> None:
        widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.Wheel and watched is not self.input_edit:
            bar = self.messages_scroll.verticalScrollBar()
            if bar.maximum() > bar.minimum():
                delta = event.angleDelta().y()
                if delta:
                    direction = -1 if delta > 0 else 1
                    bar.setValue(bar.value() + direction * CHAT_WHEEL_SCROLL_STEP)
                    event.accept()
                    return True
        return super().eventFilter(watched, event)

    def _submit(self) -> None:
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        self.input_edit.clear()
        self.message_submitted.emit(text)

    def _toggle_context(self, expanded: bool) -> None:
        self._context_expanded = bool(expanded)
        self.context_preview.setVisible(
            self._context_expanded and bool(self.context_preview.text())
        )

    def set_identity(self, provider: str, model: str) -> None:
        provider_text = str(provider).strip()
        model_text = str(model).strip()
        if provider_text and model_text:
            self.identity_label.setText(f"{provider_text} · {model_text}")
        else:
            self.identity_label.setText(provider_text or model_text)

    def set_context(self, source_text: str, translated_text: str = "") -> None:
        source = str(source_text or "").strip()
        translated = str(translated_text or "").strip()
        context = source or translated
        self.context_button.setText(f"📎 当前上下文 · {len(context)} chars")
        if source and translated:
            preview = f"原文：{source}\n\n当前译文：{translated}"
        else:
            preview = context
        self.context_preview.setText(preview)
        self.context_button.setEnabled(bool(preview))
        if not preview:
            self.context_button.setChecked(False)
            self.context_preview.hide()

    def clear_messages(self) -> None:
        for row in self._message_rows:
            self.messages_layout.removeWidget(row)
            row.deleteLater()
        self._message_rows.clear()
        self.status_label.hide()
        self.status_label.clear()

    def set_messages(self, messages: tuple[ChatMessage, ...]) -> None:
        self.clear_messages()
        for message in messages:
            self.append_message(message.role, message.content)

    def append_message(self, role: ChatRole | str, text: str) -> None:
        """Append one message, rendering assistant Markdown like ChatGPT."""

        content = str(text).strip()
        if not content:
            return
        role_value = role.value if isinstance(role, ChatRole) else str(role).lower()
        is_user = role_value == ChatRole.USER.value

        row = QWidget(self.messages_content)
        row.setObjectName("OverlayChatMessageRow")
        row.setProperty("chatRole", role_value)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        role_label = QLabel("YOU" if is_user else "AI")
        role_label.setObjectName(
            "OverlayChatUserRole" if is_user else "OverlayChatAssistantRole"
        )
        body = QLabel(content)
        body.setObjectName("OverlayChatMessageBody")
        body.setProperty("rawMessage", content)
        body.setTextFormat(
            Qt.TextFormat.PlainText if is_user else Qt.TextFormat.MarkdownText
        )
        body.setWordWrap(True)
        body.setOpenExternalLinks(False)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(role_label)
        layout.addWidget(body)

        self._install_message_wheel_proxy(row)
        self._install_message_wheel_proxy(role_label)
        self._install_message_wheel_proxy(body)

        if not is_user:
            actions = QHBoxLayout()
            actions.setContentsMargins(0, 0, 0, 0)
            actions.setSpacing(4)
            actions.addStretch(1)
            copy_button = QToolButton(row)
            copy_button.setObjectName("OverlayChatMessageCopyButton")
            copy_button.setText("")
            copy_button.setToolTip("复制这条 AI 回复")
            copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
            copy_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            copy_button.setIconSize(QSize(MESSAGE_COPY_ICON_SIZE, MESSAGE_COPY_ICON_SIZE))
            copy_button.setFixedSize(30, 28)
            copy_button.setProperty("rawMessage", content)
            copy_button.setProperty("copyFeedback", False)
            self._update_message_copy_icon(copy_button)
            copy_button.clicked.connect(
                lambda _checked=False, raw=content, button=copy_button: self._copy_assistant_message(
                    raw,
                    button,
                )
            )
            self._install_message_wheel_proxy(copy_button)
            actions.addWidget(copy_button)
            layout.addLayout(actions)

        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        self._message_rows.append(row)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _update_message_copy_icon(self, button: QToolButton) -> None:
        palette = self._palette
        copied = bool(button.property("copyFeedback"))
        color = palette.get("accent", "#60A5FA") if copied else palette.get(
            "muted_text",
            "#CBD5E1",
        )
        button.setIcon(
            symbol_icon(
                "✓" if copied else "▣",
                color,
                size=MESSAGE_COPY_ICON_SIZE,
            )
        )

    def _copy_assistant_message(self, content: str, button: QToolButton) -> None:
        """Copy one assistant reply without touching the whole conversation."""

        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        clipboard.setText(str(content))
        button.setProperty("copyFeedback", True)
        button.setToolTip("已复制这条 AI 回复")
        self._update_message_copy_icon(button)
        QTimer.singleShot(
            MESSAGE_COPY_FEEDBACK_MILLISECONDS,
            lambda current=button: self._restore_message_copy_button(current),
        )

    def _restore_message_copy_button(self, button: QToolButton) -> None:
        try:
            button.setProperty("copyFeedback", False)
            button.setToolTip("复制这条 AI 回复")
            self._update_message_copy_icon(button)
        except RuntimeError:
            # The row may have been removed while the feedback timer was active.
            return

    def _scroll_to_bottom(self) -> None:
        bar = self.messages_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_busy(self, busy: bool) -> None:
        active = bool(busy)
        self.input_edit.setEnabled(not active)
        self.send_button.setEnabled(not active)
        self.clear_button.setEnabled(not active)
        if active:
            self.status_label.setText("AI 正在回答…")
            self.status_label.show()
        elif self.status_label.text() == "AI 正在回答…":
            self.status_label.clear()
            self.status_label.hide()
        if not active:
            self.input_edit.setFocus()

    def set_error(self, message: str) -> None:
        self.set_busy(False)
        self.status_label.setText(str(message).strip() or "AI 请求失败。")
        self.status_label.show()

    def focus_input(self) -> None:
        self.input_edit.setFocus()

    def apply_palette(self, palette: dict[str, str]) -> None:
        self._palette = dict(palette)
        self.setStyleSheet(
            f"""
            QWidget#OverlayChatPanel {{
                background: transparent;
                color: {palette['text']};
            }}
            QLabel#OverlayChatTitle {{
                color: {palette['text']};
                font-weight: 600;
            }}
            QLabel#OverlayChatIdentity,
            QLabel#OverlayChatUserRole {{
                color: {palette['muted_text']};
            }}
            QLabel#OverlayChatAssistantRole {{
                color: {palette['accent']};
                font-weight: 600;
            }}
            QLabel#OverlayChatMessageBody {{
                color: {palette['text']};
                background: transparent;
                padding: 1px 0px 4px 0px;
            }}
            QToolButton#OverlayChatMessageCopyButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 2px;
            }}
            QToolButton#OverlayChatMessageCopyButton:hover {{
                background-color: {palette['hover']};
                border-color: {palette['border']};
            }}
            QToolButton#OverlayChatContextButton,
            QToolButton#OverlayChatClearButton,
            QToolButton#OverlayChatCloseButton {{
                color: {palette['text']};
                background-color: {palette['menu_background']};
                border: 1px solid {palette['border']};
                border-radius: 6px;
                padding: 5px 8px;
            }}
            QToolButton#OverlayChatContextButton:hover,
            QToolButton#OverlayChatClearButton:hover,
            QToolButton#OverlayChatCloseButton:hover {{
                border-color: {palette['accent']};
                background-color: {palette['hover']};
            }}
            QLabel#OverlayChatContextPreview {{
                color: {palette['muted_text']};
                background-color: {palette['menu_background']};
                border: 1px solid {palette['border']};
                border-radius: 6px;
                padding: 7px;
            }}
            QScrollArea#OverlayChatMessagesScroll {{
                background: transparent;
                border: none;
            }}
            QWidget#OverlayChatMessagesContent {{
                background: transparent;
            }}
            QLabel#OverlayChatStatus {{
                color: {palette['muted_text']};
            }}
            QPlainTextEdit#OverlayChatInput {{
                color: {palette['text']};
                background-color: {palette['menu_background']};
                border: 1px solid {palette['border']};
                border-radius: 7px;
                padding: 7px;
            }}
            QPlainTextEdit#OverlayChatInput:focus {{
                border-color: {palette['accent']};
            }}
            QPushButton#OverlayChatSendButton {{
                color: {palette['text']};
                background-color: {palette['hover']};
                border: 1px solid {palette['border']};
                border-radius: 7px;
            }}
            QPushButton#OverlayChatSendButton:hover {{
                border-color: {palette['accent']};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 2px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {palette['border']};
                min-height: 24px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {palette['accent']};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            """
        )
        for button in self.findChildren(QToolButton, "OverlayChatMessageCopyButton"):
            self._update_message_copy_icon(button)


__all__ = [
    "CHAT_WHEEL_SCROLL_STEP",
    "ChatInput",
    "MESSAGE_COPY_FEEDBACK_MILLISECONDS",
    "MESSAGE_COPY_ICON_SIZE",
    "OverlayChatPanel",
]
