"""Compact source-bound actions and research-memory feedback surfaces."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
)

from app.models.reading_actions import (
    READING_CONTEXT_TRANSLATE,
    READING_EXPLAIN,
    READING_SUMMARIZE,
)


RESEARCH_NOTE_SAVE = "research_note_save"
QUICK_ACTION_COMPACT_WIDTH = 420


@dataclass(frozen=True, slots=True)
class QuickActionSpec:
    key: str
    label: str
    tooltip: str
    compact_label: str = ""


QUICK_ACTION_SPECS: tuple[QuickActionSpec, ...] = (
    QuickActionSpec(READING_CONTEXT_TRANSLATE, "译", "结合当前阅读上下文翻译", "译"),
    QuickActionSpec(READING_EXPLAIN, "解释", "结合上下文解释这段内容", "解"),
    QuickActionSpec(READING_SUMMARIZE, "总结", "总结当前选中的内容", "总"),
    QuickActionSpec(RESEARCH_NOTE_SAVE, "笔记", "加入研究笔记", "记"),
)


class SelectionQuickActionBar(QFrame):
    """One-row Academic Companion affordance for the current selection."""

    action_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SelectionQuickActionBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._compact = False

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(6, 4, 6, 4)
        self._layout.setSpacing(5)
        self._layout.addStretch(1)

        self._buttons: dict[str, QToolButton] = {}
        for spec in QUICK_ACTION_SPECS:
            button = QToolButton(self)
            button.setObjectName(
                f"SelectionQuick{spec.key.title().replace('_', '')}Button"
            )
            button.setText(spec.label)
            button.setToolTip(spec.tooltip)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAutoRaise(False)
            button.setMinimumHeight(30)
            button.clicked.connect(
                lambda _checked=False, key=spec.key: self.action_requested.emit(key)
            )
            self._buttons[spec.key] = button
            self._layout.addWidget(button)
        self._layout.addStretch(1)
        self.hide()

    @property
    def buttons(self) -> dict[str, QToolButton]:
        return dict(self._buttons)

    @property
    def compact(self) -> bool:
        return self._compact

    def set_compact(self, compact: bool) -> None:
        resolved = bool(compact)
        if resolved == self._compact:
            return
        self._compact = resolved
        self._layout.setSpacing(3 if resolved else 5)
        self._layout.setContentsMargins(3 if resolved else 6, 4, 3 if resolved else 6, 4)
        for spec in QUICK_ACTION_SPECS:
            button = self._buttons.get(spec.key)
            if button is not None:
                button.setText(spec.compact_label if resolved and spec.compact_label else spec.label)
                button.setMinimumWidth(34 if resolved else 0)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self.set_compact(self.width() < QUICK_ACTION_COMPACT_WIDTH)

    def set_source_available(self, available: bool) -> None:
        enabled = bool(available)
        self.setVisible(enabled)
        for button in self._buttons.values():
            button.setEnabled(enabled)
        if enabled:
            self.set_compact(self.width() < QUICK_ACTION_COMPACT_WIDTH)

    def apply_palette(self, palette: dict[str, str]) -> None:
        self.setStyleSheet(
            f"""
            QFrame#SelectionQuickActionBar {{
                background-color: transparent;
                border: none;
            }}
            QToolButton {{
                color: {palette['text']};
                background-color: {palette['menu_background']};
                border: 1px solid {palette['border']};
                border-radius: 7px;
                padding: 4px 9px;
                font-size: 12px;
            }}
            QToolButton:hover:enabled {{
                color: {palette['text']};
                background-color: {palette['hover']};
                border-color: {palette['accent']};
            }}
            QToolButton:pressed:enabled {{
                border-color: {palette['accent']};
            }}
            QToolButton:disabled {{
                color: {palette['muted_text']};
                background-color: transparent;
                border-color: {palette['border']};
            }}
            """
        )


class ResearchNoteToast(QFrame):
    """Non-modal inline feedback with an optional jump to Research Notes."""

    view_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ResearchNoteToast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 6, 7, 6)
        layout.setSpacing(8)
        self.message_label = QLabel("", self)
        self.message_label.setObjectName("ResearchNoteToastMessage")
        self.message_label.setWordWrap(True)
        self.view_button = QPushButton("查看", self)
        self.view_button.setObjectName("ResearchNoteToastView")
        self.view_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_button.setFixedHeight(28)
        layout.addWidget(self.message_label, 1)
        layout.addWidget(self.view_button)
        self.view_button.clicked.connect(self.view_requested.emit)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(
        self,
        message: object,
        *,
        show_view: bool = True,
        timeout_ms: int = 2200,
    ) -> None:
        text = str(message or "").strip()
        if not text:
            self.hide()
            return
        self.message_label.setText(text)
        self.view_button.setVisible(bool(show_view))
        self.show()
        self.raise_()
        self._timer.start(max(600, int(timeout_ms)))

    def apply_palette(self, palette: dict[str, str]) -> None:
        self.setStyleSheet(
            f"""
            QFrame#ResearchNoteToast {{
                color: {palette['text']};
                background-color: {palette['menu_background']};
                border: 1px solid {palette['accent']};
                border-radius: 9px;
            }}
            QLabel#ResearchNoteToastMessage {{
                color: {palette['text']};
                font-size: 12px;
            }}
            QPushButton#ResearchNoteToastView {{
                color: {palette['accent']};
                background: transparent;
                border: 1px solid {palette['border']};
                border-radius: 6px;
                padding: 3px 8px;
                font-weight: 600;
            }}
            QPushButton#ResearchNoteToastView:hover {{
                background-color: {palette['hover']};
                border-color: {palette['accent']};
            }}
            """
        )


__all__ = [
    "QUICK_ACTION_COMPACT_WIDTH",
    "QUICK_ACTION_SPECS",
    "RESEARCH_NOTE_SAVE",
    "QuickActionSpec",
    "ResearchNoteToast",
    "SelectionQuickActionBar",
]
