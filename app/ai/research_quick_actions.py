"""Compact source-bound actions and research-memory feedback surfaces."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton

from app.models.reading_actions import (
    READING_CONTEXT_TRANSLATE,
    READING_EXPLAIN,
    READING_SUMMARIZE,
)
from app.ui.design_tokens import (
    CONTROL,
    LAYOUT,
    MOTION,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)


RESEARCH_NOTE_SAVE = "research_note_save"
# The full Chinese labels comfortably fit the normal compact translation card.
# Abbreviations are reserved for an intentionally/manual narrow surface rather
# than transient construction widths reported by Qt.
QUICK_ACTION_COMPACT_WIDTH = LAYOUT.quick_action_compact_width


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
    """One-row Academic Companion affordance for the current selection.

    Compact mode is controlled by the owning Overlay's stable outer width. The
    bar deliberately does not infer mode from its own transient layout width,
    which can be tiny during Qt construction/offscreen layout passes.
    """

    action_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SelectionQuickActionBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._compact = False
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(
            RADIUS.sm,
            SPACING.xs,
            RADIUS.sm,
            SPACING.xs,
        )
        self._layout.setSpacing(SPACING.xs)
        self._layout.addStretch(1)
        self._buttons: dict[str, QToolButton] = {}
        for spec in QUICK_ACTION_SPECS:
            button = QToolButton(self)
            button.setObjectName(f"SelectionQuick{spec.key.title().replace('_', '')}Button")
            button.setText(spec.label)
            button.setToolTip(spec.tooltip)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAutoRaise(False)
            button.setMinimumHeight(CONTROL.compact_height)
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
        self._layout.setSpacing(SPACING.xxs if resolved else SPACING.xs)
        horizontal = SPACING.xxs if resolved else RADIUS.sm
        self._layout.setContentsMargins(
            horizontal,
            SPACING.xs,
            horizontal,
            SPACING.xs,
        )
        for spec in QUICK_ACTION_SPECS:
            button = self._buttons.get(spec.key)
            if button is not None:
                button.setText(
                    spec.compact_label if resolved and spec.compact_label else spec.label
                )
                button.setMinimumWidth(CONTROL.touch_target_min if resolved else 0)

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
                border-radius: {RADIUS.sm}px;
                padding: {SPACING.xs}px {SPACING.sm}px;
                font-size: {TYPOGRAPHY.body}px;
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
    dismissed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ResearchNoteToast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SPACING.sm,
            RADIUS.sm,
            SPACING.sm,
            RADIUS.sm,
        )
        layout.setSpacing(SPACING.sm)
        self.message_label = QLabel("", self)
        self.message_label.setObjectName("ResearchNoteToastMessage")
        self.message_label.setWordWrap(True)
        self.view_button = QPushButton("查看", self)
        self.view_button.setObjectName("ResearchNoteToastView")
        self.view_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_button.setFixedHeight(CONTROL.compact_height)
        layout.addWidget(self.message_label, 1)
        layout.addWidget(self.view_button)
        self.view_button.clicked.connect(self._view)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self.hide()

    def _view(self) -> None:
        self.view_requested.emit()
        self.dismiss()

    def dismiss(self) -> None:
        was_visible = not self.isHidden()
        self._timer.stop()
        self.hide()
        if was_visible:
            self.dismissed.emit()

    def show_message(
        self,
        message: object,
        *,
        show_view: bool = True,
        timeout_ms: int = MOTION.toast_ms,
    ) -> None:
        text = str(message or "").strip()
        if not text:
            self.dismiss()
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
                border-radius: {RADIUS.lg}px;
            }}
            QLabel#ResearchNoteToastMessage {{
                color: {palette['text']};
                font-size: {TYPOGRAPHY.body}px;
            }}
            QPushButton#ResearchNoteToastView {{
                color: {palette['accent']};
                background: transparent;
                border: 1px solid {palette['border']};
                border-radius: {RADIUS.sm}px;
                padding: {SPACING.xxs}px {SPACING.sm}px;
                font-weight: {TYPOGRAPHY.weight_semibold};
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
