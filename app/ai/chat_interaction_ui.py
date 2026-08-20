"""High-level interaction refinements for the managed Overlay chat panel."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
    QWidgetAction,
)

from app.ai.chat.models import ChatRole
from app.ai.chat_managed_ui import ManagedChatPanel
from app.overlay.context_menu import symbol_icon
from app.ui.design_tokens import CONTROL, ICON, RADIUS, SPACING, TYPOGRAPHY


MESSAGE_ACTION_ICON_SIZE = ICON.md


class InteractiveManagedChatPanel(ManagedChatPanel):
    """ChatGPT-inspired interaction layer for the compact Overlay chat.

    It adds an explicit back affordance, streaming stop action, searchable
    history management, and hover-only per-answer actions while preserving the
    existing managed conversation/model APIs.
    """

    stop_generation_requested = Signal()
    conversation_rename_requested = Signal(object)
    regenerate_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        self._conversation_items: list[dict[str, object]] = []
        self._history_actions: list[tuple[QAction, str]] = []
        self._assistant_action_rows: dict[QWidget, tuple[QToolButton, ...]] = {}
        self._assistant_action_visibility: dict[QWidget, bool] = {}
        super().__init__(parent)

        root = self.layout()
        top_item = root.itemAt(0) if root is not None else None
        top = top_item.layout() if top_item is not None else None
        if not isinstance(top, QHBoxLayout):
            raise RuntimeError("Overlay chat header layout is unavailable")

        self.back_button = QToolButton(self)
        self.back_button.setObjectName("OverlayChatBackButton")
        self.back_button.setText("←")
        self.back_button.setToolTip("返回翻译页面")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.setFixedSize(
            CONTROL.touch_target_min,
            CONTROL.compact_height + SPACING.xxs,
        )
        self.back_button.clicked.connect(self.close_requested.emit)
        top.insertWidget(0, self.back_button)

        # The explicit back button replaces the less discoverable close cross.
        self.close_button.hide()

        input_item = root.itemAt(root.count() - 1) if root is not None else None
        input_row = input_item.layout() if input_item is not None else None
        if not isinstance(input_row, QHBoxLayout):
            raise RuntimeError("Overlay chat input layout is unavailable")

        self.stop_button = QPushButton("■ 停止", self)
        self.stop_button.setObjectName("OverlayChatStopButton")
        self.stop_button.setToolTip("停止当前 AI 回答")
        self.stop_button.setFixedWidth(CONTROL.normal_height * 2)
        self.stop_button.setMinimumHeight(CONTROL.large_height)
        self.stop_button.hide()
        self.stop_button.clicked.connect(self.stop_generation_requested.emit)
        send_index = input_row.indexOf(self.send_button)
        input_row.insertWidget(max(0, send_index), self.stop_button)

        # Word-wrapped Markdown labels report a wide preferred size. Let the
        # scroll viewport own the available width instead so long Chinese text,
        # inline Markdown, and tables cannot silently extend beyond the visible
        # conversation surface while the horizontal scrollbar is disabled.
        self.messages_content.setMinimumWidth(0)
        self.messages_content.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.messages_scroll.viewport().installEventFilter(self)
        self.stream_layout_changed.connect(self._schedule_message_layout_sync)
        self._schedule_message_layout_sync()

    def set_busy(self, busy: bool) -> None:
        super().set_busy(busy)
        active = bool(busy)
        self.send_button.setVisible(not active)
        self.stop_button.setVisible(active)
        self.stop_button.setEnabled(active)

    def set_conversations(
        self,
        items: tuple[dict[str, object], ...] | list[dict[str, object]],
        active_id: str = "",
    ) -> None:
        """Build a searchable history menu with open/rename/delete actions."""

        self._active_conversation_id = str(active_id or "")
        self._conversation_items = [dict(item) for item in items]
        self.history_menu.clear()
        self._history_actions.clear()

        new_action = QAction("＋  新建对话", self.history_menu)
        new_action.triggered.connect(self.new_conversation_requested.emit)
        self.history_menu.addAction(new_action)
        self.history_menu.addSeparator()

        search_edit = QLineEdit(self.history_menu)
        search_edit.setObjectName("OverlayChatHistorySearch")
        search_edit.setPlaceholderText("搜索历史会话…")
        search_edit.setClearButtonEnabled(True)
        search_action = QWidgetAction(self.history_menu)
        search_action.setDefaultWidget(search_edit)
        self.history_menu.addAction(search_action)
        self.history_menu.addSeparator()

        if not self._conversation_items:
            empty = QAction("暂无历史会话", self.history_menu)
            empty.setEnabled(False)
            self.history_menu.addAction(empty)
        else:
            for item in self._conversation_items:
                conversation_id = str(item.get("conversation_id", "")).strip()
                if not conversation_id:
                    continue
                title = str(item.get("title", "新对话")).strip() or "新对话"
                prefix = "✓ " if conversation_id == self._active_conversation_id else ""
                submenu = QMenu(f"{prefix}{title}", self.history_menu)
                submenu.setObjectName("OverlayChatHistoryConversationMenu")

                open_action = QAction("打开", submenu)
                open_action.triggered.connect(
                    lambda _checked=False, cid=conversation_id: self.conversation_selected.emit(cid)
                )
                submenu.addAction(open_action)

                rename_action = QAction("重命名…", submenu)
                rename_action.triggered.connect(
                    lambda _checked=False, cid=conversation_id, old=title: self._prompt_rename_conversation(
                        cid,
                        old,
                    )
                )
                submenu.addAction(rename_action)

                delete_action = QAction("删除", submenu)
                delete_action.triggered.connect(
                    lambda _checked=False, cid=conversation_id: self.conversation_delete_requested.emit(cid)
                )
                submenu.addAction(delete_action)

                action = self.history_menu.addMenu(submenu)
                self._history_actions.append((action, title.casefold()))

        search_edit.textChanged.connect(self._filter_history_actions)
        self.delete_chat_button.setEnabled(bool(self._active_conversation_id))

    def _filter_history_actions(self, query: str) -> None:
        needle = " ".join(str(query).casefold().split())
        for action, title in self._history_actions:
            action.setVisible(not needle or needle in title)

    def _prompt_rename_conversation(self, conversation_id: str, current_title: str) -> None:
        title, accepted = QInputDialog.getText(
            self,
            "重命名对话",
            "会话名称",
            QLineEdit.EchoMode.Normal,
            current_title,
        )
        normalized = " ".join(str(title).strip().split())
        if not accepted or not normalized:
            return
        self.conversation_rename_requested.emit(
            {
                "conversation_id": str(conversation_id),
                "title": normalized,
            }
        )

    def _schedule_message_layout_sync(self) -> None:
        QTimer.singleShot(0, self._fit_message_rows_to_viewport)

    def _fit_message_rows_to_viewport(self) -> None:
        """Keep every message inside the visible scroll viewport width."""

        viewport_width = self.messages_scroll.viewport().width()
        if viewport_width <= 16:
            return
        margins = self.messages_layout.contentsMargins()
        available_width = max(
            1,
            viewport_width - margins.left() - margins.right(),
        )
        rows = list(self._message_rows)
        streaming_row = getattr(self, "_streaming_row", None)
        if streaming_row is not None:
            rows.append(streaming_row)

        for row in rows:
            try:
                row.setMinimumWidth(0)
                row.setMaximumWidth(available_width)
                row.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Preferred,
                )
                body = row.findChild(QLabel, "OverlayChatMessageBody")
                if body is not None:
                    body.setMinimumWidth(0)
                    body.setMaximumWidth(available_width)
                    body.setSizePolicy(
                        QSizePolicy.Policy.Ignored,
                        QSizePolicy.Policy.Preferred,
                    )
                    body.updateGeometry()
            except RuntimeError:
                continue
        self.messages_content.updateGeometry()
        QTimer.singleShot(0, self.refresh_adaptive_height)

    def append_message(self, role: ChatRole | str, text: str) -> None:
        before = len(self._message_rows)
        super().append_message(role, text)
        if len(self._message_rows) <= before:
            return

        row = self._message_rows[-1]
        self._schedule_message_layout_sync()
        role_value = role.value if isinstance(role, ChatRole) else str(role).lower()
        if role_value == ChatRole.USER.value:
            return

        # Do not reposition a completed reply to its beginning. The base panel
        # owns the follow-tail state: users at the bottom remain at the bottom,
        # while users reading history keep their exact scroll position and get
        # an explicit jump-to-latest affordance.
        raw = str(text).strip()
        copy_buttons = row.findChildren(QToolButton, "OverlayChatMessageCopyButton")
        copy_button = copy_buttons[0] if copy_buttons else None
        if copy_button is None:
            return

        layout = row.layout()
        actions_item = layout.itemAt(layout.count() - 1) if layout is not None else None
        actions = actions_item.layout() if actions_item is not None else None
        if not isinstance(actions, QHBoxLayout):
            return

        regenerate_button = QToolButton(row)
        regenerate_button.setObjectName("OverlayChatMessageRegenerateButton")
        regenerate_button.setText("")
        regenerate_button.setToolTip("从这条回答重新生成")
        regenerate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        regenerate_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        regenerate_button.setIconSize(
            QSize(MESSAGE_ACTION_ICON_SIZE, MESSAGE_ACTION_ICON_SIZE)
        )
        regenerate_button.setFixedSize(
            CONTROL.compact_height + SPACING.xxs,
            CONTROL.compact_height,
        )
        regenerate_button.clicked.connect(
            lambda _checked=False, content=raw: self.regenerate_requested.emit(content)
        )
        actions.addWidget(regenerate_button)

        self._assistant_action_rows[row] = (copy_button, regenerate_button)
        self._assistant_action_visibility[row] = False
        row.setProperty("assistantActionsVisible", False)
        self._set_row_actions_visible(row, False)
        row.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        row.installEventFilter(self)
        for child in row.findChildren(QWidget):
            child.installEventFilter(self)
        self._update_regenerate_icon(regenerate_button)

    def _update_regenerate_icon(self, button: QToolButton) -> None:
        color = self._palette.get(
            "chrome_muted_text",
            self._palette.get("muted_text", "#CBD5E1"),
        )
        button.setIcon(symbol_icon("↻", color, size=MESSAGE_ACTION_ICON_SIZE))

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override
        messages_scroll = getattr(self, "messages_scroll", None)
        if (
            messages_scroll is not None
            and watched is messages_scroll.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self._schedule_message_layout_sync()

        row = self._assistant_row_for_widget(watched)
        if row is not None:
            event_type = event.type()
            if event_type in {QEvent.Type.Enter, QEvent.Type.HoverEnter}:
                self._set_row_actions_visible(row, True)
            elif event_type in {QEvent.Type.Leave, QEvent.Type.HoverLeave}:
                QTimer.singleShot(0, lambda current=row: self._hide_row_actions_if_left(current))
        return super().eventFilter(watched, event)

    def _assistant_row_for_widget(self, widget: object) -> QWidget | None:
        action_rows = getattr(self, "_assistant_action_rows", {})
        current = widget if isinstance(widget, QWidget) else None
        while current is not None and current is not self:
            if current in action_rows:
                return current
            current = current.parentWidget()
        return None

    def assistant_actions_visible(self, row: QWidget) -> bool:
        """Return the logical hover state independent of ancestor visibility."""

        return bool(getattr(self, "_assistant_action_visibility", {}).get(row, False))

    def _hide_row_actions_if_left(self, row: QWidget) -> None:
        try:
            if not row.underMouse():
                self._set_row_actions_visible(row, False)
        except RuntimeError:
            getattr(self, "_assistant_action_rows", {}).pop(row, None)
            getattr(self, "_assistant_action_visibility", {}).pop(row, None)

    def _set_row_actions_visible(self, row: QWidget, visible: bool) -> None:
        shown = bool(visible)
        getattr(self, "_assistant_action_visibility", {})[row] = shown
        try:
            row.setProperty("assistantActionsVisible", shown)
        except RuntimeError:
            return
        for button in getattr(self, "_assistant_action_rows", {}).get(row, ()):
            try:
                button.setHidden(not shown)
            except RuntimeError:
                pass

    def clear_messages(self) -> None:
        getattr(self, "_assistant_action_rows", {}).clear()
        getattr(self, "_assistant_action_visibility", {}).clear()
        super().clear_messages()

    def apply_palette(self, palette: dict[str, str]) -> None:
        super().apply_palette(palette)
        for buttons in getattr(self, "_assistant_action_rows", {}).values():
            if len(buttons) > 1:
                self._update_regenerate_icon(buttons[1])
        chrome_background = palette.get("chrome_background", palette["menu_background"])
        chrome_border = palette.get("chrome_border", palette["border"])
        chrome_hover = palette.get("chrome_hover", palette["hover"])
        chrome_text = palette.get("chrome_text", palette["text"])
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QToolButton#OverlayChatBackButton {{
                color: {chrome_text};
                background-color: {chrome_background};
                border: 1px solid {chrome_border};
                border-radius: {RADIUS.sm}px;
                font-size: {TYPOGRAPHY.title}px;
            }}
            QToolButton#OverlayChatBackButton:hover {{
                background-color: {chrome_hover};
                border-color: {palette['accent']};
            }}
            QPushButton#OverlayChatStopButton {{
                color: {chrome_text};
                background-color: {chrome_background};
                border: 1px solid {chrome_border};
                border-radius: {RADIUS.sm}px;
            }}
            QPushButton#OverlayChatStopButton:hover {{
                background-color: {chrome_hover};
                border-color: {palette['accent']};
            }}
            QLineEdit#OverlayChatHistorySearch {{
                color: {chrome_text};
                background-color: {chrome_background};
                border: 1px solid {chrome_border};
                border-radius: {RADIUS.sm}px;
                padding: {SPACING.sm}px {SPACING.sm}px;
                margin: {SPACING.xxs}px {RADIUS.sm}px;
            }}
            QLineEdit#OverlayChatHistorySearch:focus {{
                border-color: {palette['accent']};
            }}
            QScrollArea#OverlayChatMessagesScroll {{
                background-color: {chrome_background};
                border: 1px solid {chrome_border};
                border-radius: {RADIUS.md}px;
            }}
            QWidget#OverlayChatMessagesContent {{
                background-color: {chrome_background};
            }}
            QToolButton#OverlayChatMessageRegenerateButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: {RADIUS.sm}px;
                padding: {SPACING.xxs}px;
            }}
            QToolButton#OverlayChatMessageRegenerateButton:hover {{
                background-color: {chrome_hover};
                border-color: {chrome_border};
            }}
            """
        )
        self._schedule_message_layout_sync()


__all__ = ["InteractiveManagedChatPanel"]
