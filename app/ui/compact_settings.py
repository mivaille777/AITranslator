"""Compact, scrollable layout adapter for the settings dialog."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGroupBox, QScrollArea, QVBoxLayout, QWidget


SETTINGS_WINDOW_DEFAULT_WIDTH = 620
SETTINGS_WINDOW_DEFAULT_HEIGHT = 660
SETTINGS_WINDOW_MIN_WIDTH = 540
SETTINGS_WINDOW_MIN_HEIGHT = 500
SETTINGS_WINDOW_MAX_HEIGHT = 720
SETTINGS_SCROLL_STEP = 48


def apply_compact_settings_layout(window: Any) -> QScrollArea | None:
    """Place settings groups in a bounded vertical scroll area.

    The introductory text, status label, and Save/Cancel buttons remain fixed.
    The function is idempotent so reopening the same non-modal window does not
    rebuild or duplicate its layout.
    """

    existing = getattr(window, "_settings_scroll_area", None)
    if isinstance(existing, QScrollArea):
        _apply_window_bounds(window)
        return existing

    root_layout = window.layout()
    if not isinstance(root_layout, QVBoxLayout):
        return None

    groups: list[QGroupBox] = []
    for index in range(root_layout.count()):
        item = root_layout.itemAt(index)
        widget = item.widget() if item is not None else None
        if isinstance(widget, QGroupBox):
            groups.append(widget)

    if not groups:
        _apply_window_bounds(window)
        return None

    content = QWidget(window)
    content.setObjectName("SettingsScrollContent")
    content.setAutoFillBackground(False)
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 2, 0)
    content_layout.setSpacing(10)

    for group in groups:
        root_layout.removeWidget(group)
        group.setParent(content)
        content_layout.addWidget(group)
    content_layout.addStretch(1)

    scroll_area = QScrollArea(window)
    scroll_area.setObjectName("SettingsScrollArea")
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll_area.setWidget(content)
    scroll_area.viewport().setAutoFillBackground(False)
    scroll_area.verticalScrollBar().setSingleStep(SETTINGS_SCROLL_STEP)

    status_label = getattr(window, "status_label", None)
    insertion_index = root_layout.indexOf(status_label) if status_label is not None else -1
    if insertion_index < 0:
        button_box = getattr(window, "button_box", None)
        insertion_index = root_layout.indexOf(button_box) if button_box is not None else -1
    if insertion_index < 0:
        insertion_index = root_layout.count()
    root_layout.insertWidget(insertion_index, scroll_area, 1)

    window._settings_scroll_area = scroll_area
    window._settings_scroll_content = content
    _apply_window_bounds(window)
    return scroll_area


def ensure_settings_widget_visible(window: Any, widget: QWidget | None) -> None:
    """Scroll the compact settings viewport until ``widget`` is visible."""

    scroll_area = apply_compact_settings_layout(window)
    if scroll_area is None or widget is None:
        return
    scroll_area.ensureWidgetVisible(widget, 16, 16)


def _apply_window_bounds(window: Any) -> None:
    window.setMinimumSize(SETTINGS_WINDOW_MIN_WIDTH, SETTINGS_WINDOW_MIN_HEIGHT)
    window.setMaximumHeight(SETTINGS_WINDOW_MAX_HEIGHT)
    window.resize(SETTINGS_WINDOW_DEFAULT_WIDTH, SETTINGS_WINDOW_DEFAULT_HEIGHT)


__all__ = [
    "SETTINGS_SCROLL_STEP",
    "SETTINGS_WINDOW_DEFAULT_HEIGHT",
    "SETTINGS_WINDOW_DEFAULT_WIDTH",
    "SETTINGS_WINDOW_MAX_HEIGHT",
    "SETTINGS_WINDOW_MIN_HEIGHT",
    "SETTINGS_WINDOW_MIN_WIDTH",
    "apply_compact_settings_layout",
    "ensure_settings_widget_visible",
]
