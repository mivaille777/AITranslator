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
CHAT_PANEL_MIN_HEIGHT = 220
CHAT_PANEL_MAX_HEIGHT = 680
CHAT_MESSAGES_MIN_HEIGHT = 92
CHAT_MESSAGES_MAX_HEIGHT = 500
CHAT_BOTTOM_THRESHOLD = 28


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
    """A bounded reading-assistant chat surface with adaptive transcript height."""

    message_submitted = Signal(str)
    clear_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("OverlayChatPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(CHAT_PANEL_MIN_HEIGHT)
        self.setMaximumHeight(CHAT_PANEL_MAX_HEIGHT)
        self._message_rows: list[QWidget] = []
        self._context_expanded = False
        self._palette: dict[str, str] = {}
        self._follow_tail = True
        self._programmatic_scroll = False

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
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
        self.messages_scroll.setMinimumHeight(CHAT_MESSAGES_MIN_HEIGHT)
        self.messages_scroll.setMaximumHeight(CHAT_MESSAGES_MAX_HEIGHT)
        self.messages_scroll.verticalScrollBar().setSingleStep(CHAT_WHEEL_SCROLL_STEP)

        self.messages_content = QWidget()
        self.messages_content.setObjectName("OverlayChatMessagesContent")
        self.messages_layout = QVBoxLayout(self.messages_content)
        self.messages_layout.setContentsMargins(4, 4, 4, 4)
        self.messages_layout.setSpacing(10)
        self.messages_layout.addStretch(1)
        self.messages_scroll.setWidget(self.messages_content)
        root.addWidget(self.messages_scroll, 1)

        self.jump_to_bottom_button = QToolButton(self.messages_scroll.viewport())
        self.jump_to_bottom_button.setObjectName("OverlayChatJumpToBottomButton")
        self.jump_to_bottom_button.setText("↓")
        self.jump_to_bottom_button.setToolTip("跳转到最新内容")
        self.jump_to_bottom_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.jump_to_bottom_button.setFixedSize(34, 34)
        self.jump_to_bottom_button.hide()
        self.jump_to_bottom_button.clicked.connect(self._jump_to_bottom)

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

        scroll_bar = self.messages_scroll.verticalScrollBar()
        scroll_bar.valueChanged.connect(self._handle_scroll_value_changed)
        scroll_bar.rangeChanged.connect(self._handle_scroll_range_changed)
        self.messages_scroll.viewport().installEventFilter(self)

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

    @property
    def follow_tail(self) -> bool:
        """Whether new AI output should remain pinned to the latest content."""

        return self._follow_tail

    def _install_message_wheel_proxy(self, widget: QWidget) -> None:
        widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override
        if watched is self.messages_scroll.viewport() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            QTimer.singleShot(0, self._position_jump_to_bottom_button)

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
        self._follow_tail = True
        self.jump_to_bottom_button.hide()
        QTimer.singleShot(0, self.refresh_adaptive_height)

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
        QTimer.singleShot(0, self.refresh_adaptive_height)
        QTimer.singleShot(0, self._scroll_after_content_change)

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

    def _is_near_bottom(self) -> bool:
        bar = self.messages_scroll.verticalScrollBar()
        return bar.maximum() - bar.value() <= CHAT_BOTTOM_THRESHOLD

    def _handle_scroll_value_changed(self, _value: int) -> None:
        if self._programmatic_scroll:
            return
        self._follow_tail = self._is_near_bottom()
        self._update_jump_to_bottom_visibility()

    def _handle_scroll_range_changed(self, _minimum: int, _maximum: int) -> None:
        QTimer.singleShot(0, self._sync_scroll_after_range_change)

    def _sync_scroll_after_range_change(self) -> None:
        if self._follow_tail:
            self._scroll_to_bottom()
        else:
            self._update_jump_to_bottom_visibility()

    def _scroll_after_content_change(self) -> None:
        if self._follow_tail:
            self._scroll_to_bottom()
        else:
            self._update_jump_to_bottom_visibility()

    def _scroll_to_bottom(self) -> None:
        bar = self.messages_scroll.verticalScrollBar()
        self._programmatic_scroll = True
        try:
            bar.setValue(bar.maximum())
        finally:
            self._programmatic_scroll = False
        self._follow_tail = True
        self._update_jump_to_bottom_visibility()

    def _jump_to_bottom(self) -> None:
        self._scroll_to_bottom()

    def _update_jump_to_bottom_visibility(self) -> None:
        bar = self.messages_scroll.verticalScrollBar()
        should_show = bool(
            bar.maximum() > bar.minimum()
            and not self._follow_tail
            and not self._is_near_bottom()
        )
        self.jump_to_bottom_button.setVisible(should_show)
        if should_show:
            self._position_jump_to_bottom_button()
            self.jump_to_bottom_button.raise_()

    def _position_jump_to_bottom_button(self) -> None:
        viewport = self.messages_scroll.viewport()
        margin = 10
        x = max(margin, viewport.width() - self.jump_to_bottom_button.width() - margin)
        y = max(margin, viewport.height() - self.jump_to_bottom_button.height() - margin)
        self.jump_to_bottom_button.move(x, y)

    def refresh_adaptive_height(self, maximum_height: int | None = None) -> int:
        """Fit short chats and cap long chats so overflow becomes internal scroll."""

        try:
            cap = int(maximum_height) if maximum_height is not None else CHAT_PANEL_MAX_HEIGHT
        except (TypeError, ValueError):
            cap = CHAT_PANEL_MAX_HEIGHT
        cap = max(CHAT_PANEL_MIN_HEIGHT, min(CHAT_PANEL_MAX_HEIGHT, cap))

        self.messages_layout.invalidate()
        self.messages_layout.activate()
        self.messages_content.updateGeometry()
        content_height = max(0, self.messages_content.sizeHint().height())

        reserved = 132
        context_card = getattr(self, "reading_context_card", None)
        if context_card is not None and context_card.isVisible():
            reserved += max(0, context_card.sizeHint().height()) + 6
        elif self.context_preview.isVisible():
            reserved += max(0, self.context_preview.sizeHint().height()) + 6
        if self.status_label.isVisible():
            reserved += max(0, self.status_label.sizeHint().height()) + 4

        available_messages = max(CHAT_MESSAGES_MIN_HEIGHT, cap - reserved)
        target_messages = max(CHAT_MESSAGES_MIN_HEIGHT, content_height + 8)
        target_messages = min(
            target_messages,
            CHAT_MESSAGES_MAX_HEIGHT,
            available_messages,
        )
        self.messages_scroll.setMinimumHeight(target_messages)
        self.messages_scroll.setMaximumHeight(target_messages)
        self.setMinimumHeight(CHAT_PANEL_MIN_HEIGHT)
        self.setMaximumHeight(cap)
        self.updateGeometry()
        self._position_jump_to_bottom_button()
        return min(cap, max(CHAT_PANEL_MIN_HEIGHT, self.sizeHint().height()))

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
        QTimer.singleShot(0, self.refresh_adaptive_height)
        if not active:
            self.input_edit.setFocus()

    def set_error(self, message: str) -> None:
        self.set_busy(False)
        self.status_label.setText(str(message).strip() or "AI 请求失败。")
        self.status_label.show()
        QTimer.singleShot(0, self.refresh_adaptive_height)

    def focus_input(self) -> None:
        self.input_edit.setFocus()

    def apply_palette(self, palette: dict[str, str]) -> None:
        self._palette = dict(palette)
        chrome_background = palette.get("chrome_background", palette["menu_background"])
        chrome_border = palette.get("chrome_border", palette["border"])
        chrome_hover = palette.get("chrome_hover", palette["hover"])
        chrome_text = palette.get("chrome_text", palette["text"])
        chrome_muted = palette.get("chrome_muted_text", palette["muted_text"])
        self.setStyleSheet(
            f"""
            QWidget#OverlayChatPanel {{
                background-color: {chrome_background};
                color: {chrome_text};
                border: 1px solid {chrome_border};
                border-radius: 11px;
            }}
            QLabel#OverlayChatTitle {{
                color: {chrome_text};
                font-weight: 600;
            }}
            QLabel#OverlayChatIdentity,
            QLabel#OverlayChatUserRole {{
                color: {chrome_muted};
            }}
            QLabel#OverlayChatAssistantRole {{
                color: {palette['accent']};
                font-weight: 600;
            }}
            QLabel#OverlayChatMessageBody {{
                color: {chrome_text};
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
                background-color: {chrome_hover};
                border-color: {chrome_border};
            }}
            QToolButton#OverlayChatContextButton,
            QToolButton#OverlayChatClearButton,
            QToolButton#OverlayChatCloseButton {{
                color: {chrome_text};
                background-color: {chrome_background};
                border: 1px solid {chrome_border};
                border-radius: 6px;
                padding: 5px 8px;
            }}
            QToolButton#OverlayChatContextButton:hover,
            QToolButton#OverlayChatClearButton:hover,
            QToolButton#OverlayChatCloseButton:hover {{
                border-color: {palette['accent']};
                background-color: {chrome_hover};
            }}
            QToolButton#OverlayChatJumpToBottomButton {{
                color: {chrome_text};
                background-color: {chrome_background};
                border: 1px solid {palette['accent']};
                border-radius: 17px;
                font-size: 18px;
                font-weight: 600;
            }}
            QToolButton#OverlayChatJumpToBottomButton:hover {{
                background-color: {chrome_hover};
                border-color: {chrome_text};
            }}
            QLabel#OverlayChatContextPreview {{
                color: {chrome_muted};
                background-color: {chrome_background};
                border: 1px solid {chrome_border};
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
                color: {chrome_muted};
            }}
            QPlainTextEdit#OverlayChatInput {{
                color: {chrome_text};
                background-color: {chrome_background};
                border: 1px solid {chrome_border};
                border-radius: 7px;
                padding: 7px;
            }}
            QPlainTextEdit#OverlayChatInput:focus {{
                border-color: {palette['accent']};
            }}
            QPushButton#OverlayChatSendButton {{
                color: {chrome_text};
                background-color: {chrome_hover};
                border: 1px solid {chrome_border};
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
                background: {chrome_border};
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
    "CHAT_BOTTOM_THRESHOLD",
    "CHAT_MESSAGES_MAX_HEIGHT",
    "CHAT_MESSAGES_MIN_HEIGHT",
    "CHAT_PANEL_MAX_HEIGHT",
    "CHAT_PANEL_MIN_HEIGHT",
    "CHAT_WHEEL_SCROLL_STEP",
    "ChatInput",
    "MESSAGE_COPY_FEEDBACK_MILLISECONDS",
    "MESSAGE_COPY_ICON_SIZE",
    "OverlayChatPanel",
]
