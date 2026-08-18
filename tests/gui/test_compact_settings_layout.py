"""Qt coverage for the compact settings viewport adapter."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from app.ui.compact_settings import (
    SETTINGS_WINDOW_DEFAULT_HEIGHT,
    SETTINGS_WINDOW_MAX_HEIGHT,
    apply_compact_settings_layout,
    ensure_settings_widget_visible,
)


def _build_tall_settings_dialog() -> QDialog:
    window = QDialog()
    root = QVBoxLayout(window)
    root.addWidget(QLabel("说明"))
    for index in range(8):
        group = QGroupBox(f"Group {index}")
        group.setMinimumHeight(120)
        root.addWidget(group)
        if index == 1:
            window.ai_group = group
    window.status_label = QLabel()
    root.addWidget(window.status_label)
    window.button_box = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save
        | QDialogButtonBox.StandardButton.Cancel
    )
    root.addWidget(window.button_box)
    return window


def test_compact_settings_layout_bounds_height_and_adds_scrollbar(qtbot) -> None:
    window = _build_tall_settings_dialog()
    qtbot.addWidget(window)

    scroll = apply_compact_settings_layout(window)
    assert scroll is not None
    window.show()
    qtbot.wait(30)

    assert window.height() <= SETTINGS_WINDOW_MAX_HEIGHT
    assert window.height() == SETTINGS_WINDOW_DEFAULT_HEIGHT
    assert window.maximumHeight() == SETTINGS_WINDOW_MAX_HEIGHT
    assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.verticalScrollBar().maximum() > 0
    assert window.button_box.parentWidget() is window
    assert window.status_label.parentWidget() is window


def test_compact_settings_layout_is_idempotent_and_can_reveal_ai_group(qtbot) -> None:
    window = _build_tall_settings_dialog()
    qtbot.addWidget(window)

    first = apply_compact_settings_layout(window)
    second = apply_compact_settings_layout(window)
    assert first is second

    window.show()
    qtbot.wait(30)
    first.verticalScrollBar().setValue(first.verticalScrollBar().maximum())
    ensure_settings_widget_visible(window, window.ai_group)

    assert first.verticalScrollBar().value() < first.verticalScrollBar().maximum()
