"""Compact ChatGPT-inspired history and model controls for Overlay chat."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QHBoxLayout, QMenu, QToolButton

from app.ai.chat_selection_ui import SelectionCaptureChatPanel


class ManagedChatPanel(SelectionCaptureChatPanel):
    """Selection-aware chat panel with recent conversations and model picker."""

    new_conversation_requested = Signal()
    conversation_selected = Signal(str)
    conversation_delete_requested = Signal(str)
    model_selected = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._active_conversation_id = ""
        self._current_model_key = ("", "")

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

        # The title row doubles as an explicit drag affordance.  The Overlay
        # installs an event filter on this label so entering Chat never removes
        # the user's ability to move the card.
        self.title_label.setToolTip("拖动以移动悬浮窗")
        self.title_label.setMinimumWidth(72)

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
        """Render recent conversations as a compact ChatGPT-style history menu."""

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
        """Populate the clickable provider/model display with available models."""

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

    def apply_palette(self, palette: dict[str, str]) -> None:
        super().apply_palette(palette)
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QToolButton#OverlayChatHistoryButton,
            QToolButton#OverlayChatNewConversationButton,
            QToolButton#OverlayChatDeleteConversationButton,
            QToolButton#OverlayChatModelButton {{
                color: {palette['text']};
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 4px 6px;
            }}
            QToolButton#OverlayChatHistoryButton:hover,
            QToolButton#OverlayChatNewConversationButton:hover,
            QToolButton#OverlayChatDeleteConversationButton:hover:enabled,
            QToolButton#OverlayChatModelButton:hover {{
                background-color: {palette['hover']};
                border-color: {palette['border']};
            }}
            QToolButton#OverlayChatDeleteConversationButton:disabled {{
                color: {palette['muted_text']};
            }}
            QToolButton#OverlayChatModelButton {{
                text-align: right;
                color: {palette['muted_text']};
            }}
            QMenu#OverlayChatHistoryMenu,
            QMenu#OverlayChatModelMenu {{
                background-color: {palette['menu_background']};
                color: {palette['text']};
                border: 1px solid {palette['border']};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu#OverlayChatHistoryMenu::item,
            QMenu#OverlayChatModelMenu::item {{
                padding: 7px 12px;
                border-radius: 5px;
            }}
            QMenu#OverlayChatHistoryMenu::item:selected,
            QMenu#OverlayChatModelMenu::item:selected {{
                background-color: {palette['hover']};
            }}
            """
        )


__all__ = ["ManagedChatPanel"]
