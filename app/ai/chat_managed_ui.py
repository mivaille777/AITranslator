"""Compact ChatGPT-inspired history and model controls for Overlay chat."""

from __future__ import annotations

import math
import re

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ai.chat.models import ChatRole
from app.ai.chat_selection_ui import SelectionCaptureChatPanel
from app.ui.design_tokens import CONTROL, LAYOUT, RADIUS, SPACING, TYPOGRAPHY


CHAT_DISPLAY_FONT_MIN = 10
CHAT_DISPLAY_FONT_MAX = 30
CHAT_DISPLAY_FONT_PRESETS = (10, 11, 12, 13, 14, 16, 18, 20, 24, 28, 30)
CHAT_INPUT_MIN_HEIGHT = CONTROL.input_min_height
CHAT_INPUT_SOFT_MAX_HEIGHT = 180
_CHAT_INPUT_PANEL_RATIO = 0.28
_CHAT_INPUT_DYNAMIC_MIN = CONTROL.large_height + CONTROL.touch_target_min + SPACING.xxs
_BARE_URL_RE = re.compile(r"(?<![<(])https?://[^\s<>\]]+", re.IGNORECASE)
_TRAILING_URL_PUNCTUATION = ".,;:!?，。；：！？"


def _linkify_markdown_urls(text: object) -> str:
    """Make bare http(s) URLs clickable without changing copied raw content."""

    markdown = str(text or "")

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        stripped = token.rstrip(_TRAILING_URL_PUNCTUATION)
        trailing = token[len(stripped) :]
        if not stripped:
            return token
        return f"<{stripped}>{trailing}"

    return _BARE_URL_RE.sub(replace, markdown)


class ManagedChatPanel(SelectionCaptureChatPanel):
    """Selection-aware chat panel with recent conversations and model picker."""

    new_conversation_requested = Signal()
    conversation_selected = Signal(str)
    conversation_delete_requested = Signal(str)
    model_selected = Signal(object)
    stream_layout_changed = Signal()
    display_font_size_changed = Signal(int)
    link_open_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._active_conversation_id = ""
        self._current_model_key = ("", "")
        self._streaming_request_id: int | None = None
        self._streaming_row: QWidget | None = None
        self._streaming_body: QLabel | None = None
        self._display_font_size = TYPOGRAPHY.body
        self._font_action_group: QActionGroup | None = None

        root = self.layout()
        top_item = root.itemAt(0) if root is not None else None
        top = top_item.layout() if top_item is not None else None
        if not isinstance(top, QHBoxLayout):
            raise RuntimeError("Overlay chat header layout is unavailable")

        self.history_button = QToolButton(self)
        self.history_button.setObjectName("OverlayChatHistoryButton")
        self.history_button.setText("☰")
        self.history_button.setToolTip("历史会话")
        self.history_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.history_menu = QMenu(self.history_button)
        self.history_menu.setObjectName("OverlayChatHistoryMenu")
        self.history_button.setMenu(self.history_menu)
        top.insertWidget(0, self.history_button)

        self.new_chat_button = QToolButton(self)
        self.new_chat_button.setObjectName("OverlayChatNewConversationButton")
        self.new_chat_button.setText("＋")
        self.new_chat_button.setToolTip("新建对话")
        self.new_chat_button.clicked.connect(self.new_conversation_requested.emit)
        top.insertWidget(1, self.new_chat_button)

        self.identity_label.hide()
        self.model_button = QToolButton(self)
        self.model_button.setObjectName("OverlayChatModelButton")
        self.model_button.setText("选择模型 ▾")
        self.model_button.setToolTip("切换当前对话使用的模型")
        self.model_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.model_menu = QMenu(self.model_button)
        self.model_menu.setObjectName("OverlayChatModelMenu")
        self.model_button.setMenu(self.model_menu)
        identity_index = top.indexOf(self.identity_label)
        top.insertWidget(max(0, identity_index), self.model_button, 1)

        self.font_button = QToolButton(self)
        self.font_button.setObjectName("OverlayChatFontButton")
        self.font_button.setToolTip("调整 AI 对话文字大小")
        self.font_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.font_menu = QMenu(self.font_button)
        self.font_menu.setObjectName("OverlayChatFontMenu")
        self.font_button.setMenu(self.font_menu)
        close_index = top.indexOf(self.close_button)
        top.insertWidget(max(0, close_index), self.font_button)

        self.delete_chat_button = QToolButton(self)
        self.delete_chat_button.setObjectName("OverlayChatDeleteConversationButton")
        self.delete_chat_button.setText("⌫")
        self.delete_chat_button.setToolTip("删除当前对话")
        self.delete_chat_button.clicked.connect(self._request_delete_current)
        close_index = top.indexOf(self.close_button)
        top.insertWidget(max(0, close_index), self.delete_chat_button)

        self.title_label.setToolTip("拖动以移动悬浮窗")
        self.title_label.setMinimumWidth(CONTROL.large_height + TYPOGRAPHY.title_large)
        self.model_button.setMinimumWidth(LAYOUT.chat_model_min_width)
        self._build_font_menu()
        self.input_edit.textChanged.connect(self._schedule_input_height_refresh)
        self.set_display_font_size(self._display_font_size)
        self._schedule_input_height_refresh()

    @property
    def active_conversation_id(self) -> str:
        return self._active_conversation_id

    @property
    def display_font_size(self) -> int:
        return int(self._display_font_size)

    def _request_delete_current(self) -> None:
        if self._active_conversation_id:
            self.conversation_delete_requested.emit(self._active_conversation_id)

    def _build_font_menu(self) -> None:
        self.font_menu.clear()
        group = QActionGroup(self.font_menu)
        group.setExclusive(True)
        for size in CHAT_DISPLAY_FONT_PRESETS:
            action = QAction(f"{size} pt", self.font_menu)
            action.setCheckable(True)
            action.setData(size)
            action.setChecked(size == self._display_font_size)
            action.triggered.connect(
                lambda _checked=False, selected=size: self._request_display_font_size(selected)
            )
            group.addAction(action)
            self.font_menu.addAction(action)
        self._font_action_group = group
        self._sync_font_button()

    def _sync_font_button(self) -> None:
        self.font_button.setText(f"A {self._display_font_size} ▾")
        group = self._font_action_group
        if group is None:
            return
        for action in group.actions():
            try:
                size = int(action.data())
            except (TypeError, ValueError):
                continue
            blocked = action.blockSignals(True)
            action.setChecked(size == self._display_font_size)
            action.blockSignals(blocked)

    def _request_display_font_size(self, size: int) -> None:
        previous = self._display_font_size
        self.set_display_font_size(size)
        if self._display_font_size != previous:
            self.display_font_size_changed.emit(self._display_font_size)

    def set_conversations(
        self,
        items: tuple[dict[str, object], ...] | list[dict[str, object]],
        active_id: str = "",
    ) -> None:
        self._active_conversation_id = str(active_id or "")
        self.history_menu.clear()

        new_action = QAction("＋  新建对话", self.history_menu)
        new_action.triggered.connect(self.new_conversation_requested.emit)
        self.history_menu.addAction(new_action)
        self.history_menu.addSeparator()

        if not items:
            empty = QAction("暂无历史会话", self.history_menu)
            empty.setEnabled(False)
            self.history_menu.addAction(empty)
        else:
            heading = QAction("最近会话", self.history_menu)
            heading.setEnabled(False)
            self.history_menu.addAction(heading)
            for item in items:
                conversation_id = str(item.get("conversation_id", "")).strip()
                if not conversation_id:
                    continue
                title = str(item.get("title", "新对话")).strip() or "新对话"
                action = QAction(title, self.history_menu)
                action.setCheckable(True)
                action.setChecked(conversation_id == self._active_conversation_id)
                action.triggered.connect(
                    lambda _checked=False, cid=conversation_id: self.conversation_selected.emit(cid)
                )
                self.history_menu.addAction(action)

        self.delete_chat_button.setEnabled(bool(self._active_conversation_id))

    def set_model_options(
        self,
        options: tuple[dict[str, str], ...] | list[dict[str, str]],
        *,
        current_provider: str = "",
        current_model: str = "",
    ) -> None:
        self.model_menu.clear()
        self._current_model_key = (
            str(current_provider).strip(),
            str(current_model).strip(),
        )
        group = QActionGroup(self.model_menu)
        group.setExclusive(True)

        for option in options:
            provider = str(option.get("provider", "")).strip()
            model = str(option.get("model", "")).strip()
            if not provider or not model:
                continue
            provider_label = str(option.get("provider_label", provider)).strip() or provider
            label = str(option.get("label", model)).strip() or model
            base_url = str(option.get("base_url", "")).strip()
            action = QAction(f"{provider_label} · {label}", self.model_menu)
            action.setCheckable(True)
            action.setChecked((provider, model) == self._current_model_key)
            payload = {
                "provider": provider,
                "model": model,
                "base_url": base_url,
            }
            action.triggered.connect(
                lambda _checked=False, selected=payload: self.model_selected.emit(dict(selected))
            )
            group.addAction(action)
            self.model_menu.addAction(action)

        if self.model_menu.isEmpty():
            empty = QAction("请先在设置中配置模型", self.model_menu)
            empty.setEnabled(False)
            self.model_menu.addAction(empty)

        self.set_identity(current_provider, current_model)

    def set_identity(self, provider: str, model: str) -> None:
        provider_text = str(provider).strip()
        model_text = str(model).strip()
        if provider_text and model_text:
            self.model_button.setText(f"{provider_text} · {model_text} ▾")
        elif model_text:
            self.model_button.setText(f"{model_text} ▾")
        elif provider_text:
            self.model_button.setText(f"{provider_text} ▾")
        else:
            self.model_button.setText("选择模型 ▾")

    def _assistant_link_flags(self) -> Qt.TextInteractionFlag:
        return (
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )

    def _configure_assistant_links(self, body: QLabel, raw_text: object) -> None:
        body.setOpenExternalLinks(False)
        body.setTextInteractionFlags(self._assistant_link_flags())
        body.setText(_linkify_markdown_urls(raw_text))
        body.setToolTip("选择文字；Ctrl + 点击链接可选择浏览器打开")
        if not bool(body.property("aiTransLinkConnected")):
            body.linkActivated.connect(self._on_link_activated)
            body.setProperty("aiTransLinkConnected", True)

    def _on_link_activated(self, url: str) -> None:
        if not (
            QApplication.keyboardModifiers()
            & Qt.KeyboardModifier.ControlModifier
        ):
            return
        target = str(url or "").strip()
        if target:
            self.link_open_requested.emit(target)

    def append_message(self, role: ChatRole | str, text: str) -> None:
        before = len(self._message_rows)
        super().append_message(role, text)
        if len(self._message_rows) <= before:
            return
        role_value = role.value if isinstance(role, ChatRole) else str(role).lower()
        if role_value == ChatRole.USER.value:
            return
        row = self._message_rows[-1]
        body = row.findChild(QLabel, "OverlayChatMessageBody")
        if body is not None:
            self._configure_assistant_links(body, text)
            body.setProperty("rawMessage", str(text).strip())

    def begin_streaming_reply(self, request_id: int) -> None:
        """Create one temporary assistant row that can be updated in place."""

        self.cancel_streaming_reply()
        row = QWidget(self.messages_content)
        row.setObjectName("OverlayChatStreamingMessageRow")
        row.setProperty("chatRole", ChatRole.ASSISTANT.value)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.xs)

        role_label = QLabel("AI")
        role_label.setObjectName("OverlayChatAssistantRole")
        body = QLabel("▍")
        body.setObjectName("OverlayChatMessageBody")
        body.setTextFormat(Qt.TextFormat.MarkdownText)
        body.setWordWrap(True)
        self._configure_assistant_links(body, "▍")
        layout.addWidget(role_label)
        layout.addWidget(body)
        self._install_message_wheel_proxy(row)
        self._install_message_wheel_proxy(role_label)
        self._install_message_wheel_proxy(body)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        self._streaming_request_id = int(request_id)
        self._streaming_row = row
        self._streaming_body = body
        self.set_display_font_size(self._display_font_size)
        self.stream_layout_changed.emit()
        QTimer.singleShot(0, self.refresh_adaptive_height)
        QTimer.singleShot(0, self._scroll_after_content_change)

    def update_streaming_reply(self, request_id: int, text: str) -> bool:
        if self._streaming_request_id != int(request_id) or self._streaming_body is None:
            return False
        content = str(text)
        rendered = content if content else "▍"
        self._streaming_body.setText(_linkify_markdown_urls(rendered))
        self._streaming_body.setProperty("rawMessage", content)
        self._streaming_body.updateGeometry()
        self.messages_content.updateGeometry()
        self.stream_layout_changed.emit()
        QTimer.singleShot(0, self.refresh_adaptive_height)
        QTimer.singleShot(0, self._scroll_after_content_change)
        return True

    def finish_streaming_reply(self, request_id: int, text: str) -> bool:
        if self._streaming_request_id != int(request_id):
            return False
        self.cancel_streaming_reply()
        self.append_message(ChatRole.ASSISTANT, text)
        self.set_display_font_size(self._display_font_size)
        self.stream_layout_changed.emit()
        return True

    def cancel_streaming_reply(self, request_id: int | None = None) -> None:
        if request_id is not None and self._streaming_request_id != int(request_id):
            return
        row = self._streaming_row
        if row is not None:
            self.messages_layout.removeWidget(row)
            row.deleteLater()
        self._streaming_request_id = None
        self._streaming_row = None
        self._streaming_body = None
        self.stream_layout_changed.emit()
        QTimer.singleShot(0, self.refresh_adaptive_height)

    def clear_messages(self) -> None:
        self.cancel_streaming_reply()
        super().clear_messages()

    def _schedule_input_height_refresh(self) -> None:
        QTimer.singleShot(0, self._refresh_input_height)

    def _refresh_input_height(self) -> None:
        edit = self.input_edit
        try:
            document_height = float(edit.document().documentLayout().documentSize().height())
        except (AttributeError, TypeError, ValueError):
            document_height = float(CHAT_INPUT_MIN_HEIGHT)
        frame = max(0, edit.frameWidth() * 2)
        margins = edit.contentsMargins()
        desired = math.ceil(
            document_height
            + frame
            + margins.top()
            + margins.bottom()
            + SPACING.md
        )
        if not edit.toPlainText():
            desired = CHAT_INPUT_MIN_HEIGHT
        panel_height = max(self.height(), self.minimumHeight(), 1)
        dynamic_cap = max(
            _CHAT_INPUT_DYNAMIC_MIN,
            min(
                CHAT_INPUT_SOFT_MAX_HEIGHT,
                round(panel_height * _CHAT_INPUT_PANEL_RATIO),
            ),
        )
        target = max(CHAT_INPUT_MIN_HEIGHT, min(dynamic_cap, desired))
        if edit.minimumHeight() != target or edit.maximumHeight() != target:
            edit.setMinimumHeight(target)
            edit.setMaximumHeight(target)
            edit.updateGeometry()
            self.updateGeometry()
            QTimer.singleShot(0, self.refresh_adaptive_height)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._schedule_input_height_refresh()

    def set_display_font_size(self, size: int) -> None:
        """Scale chat content independently of the translation surface font."""

        try:
            resolved = max(CHAT_DISPLAY_FONT_MIN, min(CHAT_DISPLAY_FONT_MAX, int(size)))
        except (TypeError, ValueError):
            resolved = TYPOGRAPHY.body
        self._display_font_size = resolved
        body_font = QFont(self.font())
        body_font.setPointSize(resolved)
        role_font = QFont(self.font())
        role_font.setPointSize(max(8, round(resolved * 0.78)))
        role_font.setBold(True)
        input_font = QFont(self.font())
        input_font.setPointSize(max(9, round(resolved * 0.92)))

        self.input_edit.setFont(input_font)
        self.context_preview.setFont(input_font)
        for body in self.findChildren(QLabel, "OverlayChatMessageBody"):
            body.setFont(body_font)
        for role in self.findChildren(QLabel, "OverlayChatAssistantRole") + self.findChildren(
            QLabel,
            "OverlayChatUserRole",
        ):
            role.setFont(role_font)
        if self._streaming_body is not None:
            self._streaming_body.setFont(body_font)
        self._sync_font_button()
        self._schedule_input_height_refresh()
        QTimer.singleShot(0, self.refresh_adaptive_height)

    def apply_palette(self, palette: dict[str, str]) -> None:
        super().apply_palette(palette)
        chrome_background = palette.get("chrome_background", palette["menu_background"])
        chrome_border = palette.get("chrome_border", palette["border"])
        chrome_hover = palette.get("chrome_hover", palette["hover"])
        chrome_text = palette.get("chrome_text", palette["text"])
        chrome_muted = palette.get("chrome_muted_text", palette["muted_text"])
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QToolButton#OverlayChatHistoryButton,
            QToolButton#OverlayChatNewConversationButton,
            QToolButton#OverlayChatDeleteConversationButton,
            QToolButton#OverlayChatModelButton,
            QToolButton#OverlayChatFontButton {{
                color: {chrome_text};
                background-color: {chrome_background};
                border: 1px solid {chrome_border};
                border-radius: {RADIUS.sm}px;
                padding: {SPACING.xs}px {RADIUS.sm}px;
            }}
            QToolButton#OverlayChatHistoryButton:hover,
            QToolButton#OverlayChatNewConversationButton:hover,
            QToolButton#OverlayChatDeleteConversationButton:hover:enabled,
            QToolButton#OverlayChatModelButton:hover,
            QToolButton#OverlayChatFontButton:hover {{
                background-color: {chrome_hover};
                border-color: {palette['accent']};
            }}
            QToolButton#OverlayChatDeleteConversationButton:disabled {{
                color: {chrome_muted};
            }}
            QToolButton#OverlayChatModelButton {{
                text-align: right;
                color: {chrome_muted};
            }}
            QToolButton#OverlayChatFontButton {{
                min-width: {CONTROL.large_height + SPACING.md}px;
                color: {chrome_muted};
            }}
            QMenu#OverlayChatHistoryMenu,
            QMenu#OverlayChatHistoryConversationMenu,
            QMenu#OverlayChatModelMenu,
            QMenu#OverlayChatFontMenu {{
                background-color: {chrome_background};
                color: {chrome_text};
                border: 1px solid {chrome_border};
                border-radius: {RADIUS.md}px;
                padding: {RADIUS.sm}px;
            }}
            QMenu#OverlayChatHistoryMenu::item,
            QMenu#OverlayChatHistoryConversationMenu::item,
            QMenu#OverlayChatModelMenu::item,
            QMenu#OverlayChatFontMenu::item {{
                padding: {SPACING.sm}px {SPACING.md}px;
                border-radius: {RADIUS.sm}px;
            }}
            QMenu#OverlayChatHistoryMenu::item:selected,
            QMenu#OverlayChatHistoryConversationMenu::item:selected,
            QMenu#OverlayChatModelMenu::item:selected,
            QMenu#OverlayChatFontMenu::item:selected {{
                background-color: {chrome_hover};
            }}
            """
        )
        self.set_display_font_size(self._display_font_size)


__all__ = [
    "CHAT_DISPLAY_FONT_MAX",
    "CHAT_DISPLAY_FONT_MIN",
    "CHAT_DISPLAY_FONT_PRESETS",
    "CHAT_INPUT_MIN_HEIGHT",
    "CHAT_INPUT_SOFT_MAX_HEIGHT",
    "ManagedChatPanel",
]
