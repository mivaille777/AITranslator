"""Compact ChatGPT-inspired history and model controls for Overlay chat."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QToolButton, QVBoxLayout, QWidget

from app.ai.chat.models import ChatRole
from app.ai.chat_selection_ui import SelectionCaptureChatPanel


class ManagedChatPanel(SelectionCaptureChatPanel):
    """Selection-aware chat panel with recent conversations and model picker."""

    new_conversation_requested = Signal()
    conversation_selected = Signal(str)
    conversation_delete_requested = Signal(str)
    model_selected = Signal(object)
    stream_layout_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._active_conversation_id = ""
        self._current_model_key = ("", "")
        self._streaming_request_id: int | None = None
        self._streaming_row: QWidget | None = None
        self._streaming_body: QLabel | None = None
        self._display_font_size = 13

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

        self.delete_chat_button = QToolButton(self)
        self.delete_chat_button.setObjectName("OverlayChatDeleteConversationButton")
        self.delete_chat_button.setText("⌫")
        self.delete_chat_button.setToolTip("删除当前对话")
        self.delete_chat_button.clicked.connect(self._request_delete_current)
        close_index = top.indexOf(self.close_button)
        top.insertWidget(max(0, close_index), self.delete_chat_button)

        self.title_label.setToolTip("拖动以移动悬浮窗")
        self.title_label.setMinimumWidth(64)
        self.model_button.setMinimumWidth(120)
        self.set_display_font_size(self._display_font_size)

    @property
    def active_conversation_id(self) -> str:
        return self._active_conversation_id

    def _request_delete_current(self) -> None:
        if self._active_conversation_id:
            self.conversation_delete_requested.emit(self._active_conversation_id)

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

    def begin_streaming_reply(self, request_id: int) -> None:
        """Create one temporary assistant row that can be updated in place."""

        self.cancel_streaming_reply()
        row = QWidget(self.messages_content)
        row.setObjectName("OverlayChatStreamingMessageRow")
        row.setProperty("chatRole", ChatRole.ASSISTANT.value)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        role_label = QLabel("AI")
        role_label.setObjectName("OverlayChatAssistantRole")
        body = QLabel("▍")
        body.setObjectName("OverlayChatMessageBody")
        body.setTextFormat(Qt.TextFormat.MarkdownText)
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
        self._streaming_body.setText(content if content else "▍")
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

    def set_display_font_size(self, size: int) -> None:
        """Scale chat content with a manually resized Overlay."""

        try:
            resolved = max(10, min(30, int(size)))
        except (TypeError, ValueError):
            resolved = 13
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
            QToolButton#OverlayChatModelButton {{
                color: {chrome_text};
                background-color: {chrome_background};
                border: 1px solid {chrome_border};
                border-radius: 6px;
                padding: 4px 6px;
            }}
            QToolButton#OverlayChatHistoryButton:hover,
            QToolButton#OverlayChatNewConversationButton:hover,
            QToolButton#OverlayChatDeleteConversationButton:hover:enabled,
            QToolButton#OverlayChatModelButton:hover {{
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
            QMenu#OverlayChatHistoryMenu,
            QMenu#OverlayChatHistoryConversationMenu,
            QMenu#OverlayChatModelMenu {{
                background-color: {chrome_background};
                color: {chrome_text};
                border: 1px solid {chrome_border};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu#OverlayChatHistoryMenu::item,
            QMenu#OverlayChatHistoryConversationMenu::item,
            QMenu#OverlayChatModelMenu::item {{
                padding: 7px 12px;
                border-radius: 5px;
            }}
            QMenu#OverlayChatHistoryMenu::item:selected,
            QMenu#OverlayChatHistoryConversationMenu::item:selected,
            QMenu#OverlayChatModelMenu::item:selected {{
                background-color: {chrome_hover};
            }}
            """
        )
        self.set_display_font_size(self._display_font_size)


__all__ = ["ManagedChatPanel"]
