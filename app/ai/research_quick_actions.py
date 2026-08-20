"""Compact source-bound actions shown directly below a translation result."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton

from app.models.reading_actions import (
    READING_CONTEXT_TRANSLATE,
    READING_EXPLAIN,
    READING_SUMMARIZE,
)


RESEARCH_NOTE_SAVE = "research_note_save"


@dataclass(frozen=True, slots=True)
class QuickActionSpec:
    key: str
    label: str
    tooltip: str


QUICK_ACTION_SPECS: tuple[QuickActionSpec, ...] = (
    QuickActionSpec(READING_CONTEXT_TRANSLATE, "译", "结合当前阅读上下文翻译"),
    QuickActionSpec(READING_EXPLAIN, "解释", "结合上下文解释这段内容"),
    QuickActionSpec(READING_SUMMARIZE, "总结", "总结当前选中的内容"),
    QuickActionSpec(RESEARCH_NOTE_SAVE, "笔记", "加入研究笔记"),
)


class SelectionQuickActionBar(QFrame):
    """One-row Academic Companion affordance for the current selection."""

    action_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SelectionQuickActionBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(5)
        layout.addStretch(1)

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
            layout.addWidget(button)
        layout.addStretch(1)
        self.hide()

    @property
    def buttons(self) -> dict[str, QToolButton]:
        return dict(self._buttons)

    def set_source_available(self, available: bool) -> None:
        enabled = bool(available)
        self.setVisible(enabled)
        for button in self._buttons.values():
            button.setEnabled(enabled)

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
                padding: 4px 10px;
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


__all__ = [
    "QUICK_ACTION_SPECS",
    "RESEARCH_NOTE_SAVE",
    "QuickActionSpec",
    "SelectionQuickActionBar",
]
