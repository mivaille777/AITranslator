"""Selection-capture extensions for the Overlay chat input."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QHBoxLayout, QToolButton

from app.ai.chat.ui import OverlayChatPanel


class SelectionCaptureChatPanel(OverlayChatPanel):
    """Chat panel that can receive one mouse-selected text snippet safely."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selection_capture_armed = False
        self._last_auto_insert_snapshot: tuple[str, int] | None = None
        self._programmatic_input_change = False

        self.input_edit.installEventFilter(self)
        self.input_edit.textChanged.connect(self._on_input_text_changed)

        self.undo_selection_button = QToolButton(self)
        self.undo_selection_button.setObjectName("OverlayChatUndoSelectionButton")
        self.undo_selection_button.setText("↶")
        self.undo_selection_button.setToolTip("撤销最近一次划词输入")
        self.undo_selection_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_selection_button.setFixedSize(44, 44)
        self.undo_selection_button.setEnabled(False)
        self.undo_selection_button.clicked.connect(
            lambda _checked=False: self.undo_last_selection_input()
        )

        root = self.layout()
        input_item = root.itemAt(root.count() - 1) if root is not None else None
        input_row = input_item.layout() if input_item is not None else None
        if isinstance(input_row, QHBoxLayout):
            input_row.insertWidget(max(0, input_row.count() - 1), self.undo_selection_button)

    @property
    def selection_capture_armed(self) -> bool:
        """Return whether the next external mouse selection should be captured."""

        return bool(
            self._selection_capture_armed
            and self.isVisible()
            and self.input_edit.isEnabled()
        )

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override
        if watched is self.input_edit and event.type() == QEvent.Type.FocusIn:
            # Once the user has placed the caret in Chat, keep capture armed
            # across the temporary focus loss required to select text in a
            # different application. Closing Chat explicitly disarms it.
            self._selection_capture_armed = True
        return super().eventFilter(watched, event)

    def focus_input(self) -> None:
        self._selection_capture_armed = True
        super().focus_input()

    def disarm_selection_capture(self) -> None:
        self._selection_capture_armed = False

    def _on_input_text_changed(self) -> None:
        if self._programmatic_input_change:
            return
        # Once the user edits after an automatic insertion, restoring the old
        # whole-input snapshot could destroy intentional manual changes.
        self._last_auto_insert_snapshot = None
        self._sync_undo_button()

    def _sync_undo_button(self) -> None:
        self.undo_selection_button.setEnabled(
            self._last_auto_insert_snapshot is not None
            and self.input_edit.isEnabled()
        )

    def insert_selected_text(self, text: object) -> bool:
        """Insert one captured selection at the cursor and expose one-step undo."""

        selected = str(text or "").strip()
        if not selected or not self.input_edit.isEnabled():
            return False

        before = self.input_edit.toPlainText()
        cursor = self.input_edit.textCursor()
        position = cursor.position()
        prefix = ""
        suffix = ""
        if position > 0 and not before[position - 1].isspace():
            prefix = "\n"
        if position < len(before) and not before[position].isspace():
            suffix = "\n"

        self._last_auto_insert_snapshot = (before, position)
        self._programmatic_input_change = True
        try:
            cursor.insertText(f"{prefix}{selected}{suffix}")
            self.input_edit.setTextCursor(cursor)
        finally:
            self._programmatic_input_change = False

        self._selection_capture_armed = True
        self._sync_undo_button()
        self.focus_input()
        return True

    def undo_last_selection_input(self) -> bool:
        """Restore the exact input state from before the latest auto insertion."""

        snapshot = self._last_auto_insert_snapshot
        if snapshot is None:
            return False
        previous_text, previous_position = snapshot

        self._programmatic_input_change = True
        try:
            self.input_edit.setPlainText(previous_text)
            cursor = self.input_edit.textCursor()
            cursor.setPosition(min(len(previous_text), max(0, previous_position)))
            self.input_edit.setTextCursor(cursor)
        finally:
            self._programmatic_input_change = False

        self._last_auto_insert_snapshot = None
        self._sync_undo_button()
        self.focus_input()
        return True

    def set_busy(self, busy: bool) -> None:
        super().set_busy(busy)
        self._sync_undo_button()

    def apply_palette(self, palette: dict[str, str]) -> None:
        super().apply_palette(palette)
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QToolButton#OverlayChatUndoSelectionButton {{
                color: {palette['text']};
                background-color: {palette['menu_background']};
                border: 1px solid {palette['border']};
                border-radius: 7px;
                font-size: 18px;
            }}
            QToolButton#OverlayChatUndoSelectionButton:hover:enabled {{
                border-color: {palette['accent']};
                background-color: {palette['hover']};
            }}
            QToolButton#OverlayChatUndoSelectionButton:disabled {{
                color: {palette['muted_text']};
                border-color: {palette['border']};
            }}
            """
        )


__all__ = ["SelectionCaptureChatPanel"]
