"""Responsive settings layout adapters.

Legacy dialogs still receive one bounded scroll area. The production AITrans
SettingsWindow declares category groups and is upgraded to a product-style
left navigation without recreating its controls or changing persistence logic.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QListWidget,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.overlay.context_menu import OVERLAY_THEMES
from app.ui.design_tokens import RADIUS, SETTINGS, SPACING, TYPOGRAPHY


# Public compatibility constants are now derived from the Settings component
# tokens rather than maintained as a second layout source of truth.
SETTINGS_WINDOW_DEFAULT_WIDTH = SETTINGS.default_width
SETTINGS_WINDOW_NAV_WIDTH = SETTINGS.navigation_width
SETTINGS_WINDOW_DEFAULT_HEIGHT = SETTINGS.default_height
SETTINGS_WINDOW_MIN_WIDTH = SETTINGS.minimum_width
SETTINGS_WINDOW_NAV_MIN_WIDTH = SETTINGS.navigation_minimum_width
SETTINGS_WINDOW_MIN_HEIGHT = SETTINGS.minimum_height
SETTINGS_WINDOW_MAX_HEIGHT = SETTINGS.maximum_height
SETTINGS_SCROLL_STEP = SETTINGS.scroll_step
SETTINGS_NAVIGATION_WIDTH = SETTINGS.navigation_rail_width


def apply_compact_settings_layout(window: Any) -> QScrollArea | None:
    """Apply the best bounded settings layout supported by ``window``."""

    existing = getattr(window, "_settings_scroll_area", None)
    if isinstance(existing, QScrollArea):
        _apply_window_bounds(window)
        return existing

    categories = getattr(window, "_settings_category_groups", None)
    if categories:
        return _apply_navigation_settings_layout(window, categories)
    return _apply_legacy_scroll_layout(window)


def _apply_navigation_settings_layout(
    window: Any,
    categories: object,
) -> QScrollArea | None:
    root_layout = window.layout()
    if not isinstance(root_layout, QVBoxLayout):
        return None

    normalized: list[tuple[str, tuple[QGroupBox, ...]]] = []
    all_groups: list[QGroupBox] = []
    for raw in categories:
        try:
            name, widgets = raw
        except (TypeError, ValueError):
            continue
        groups = tuple(widget for widget in widgets if isinstance(widget, QGroupBox))
        if not groups:
            continue
        normalized.append((str(name), groups))
        all_groups.extend(groups)
    if not normalized:
        return _apply_legacy_scroll_layout(window)

    for group in all_groups:
        root_layout.removeWidget(group)

    container = QWidget(window)
    container.setObjectName("SettingsNavigationContainer")
    container_layout = QHBoxLayout(container)
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.setSpacing(SPACING.md)

    nav = QListWidget(container)
    nav.setObjectName("SettingsNavigation")
    nav.setFixedWidth(SETTINGS_NAVIGATION_WIDTH)
    nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    nav.setSpacing(SPACING.xxs)
    for name, _groups in normalized:
        nav.addItem(name)
    container_layout.addWidget(nav)

    scroll_area = QScrollArea(container)
    scroll_area.setObjectName("SettingsScrollArea")
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll_area.verticalScrollBar().setSingleStep(SETTINGS_SCROLL_STEP)

    content = QWidget(scroll_area)
    content.setObjectName("SettingsScrollContent")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(
        SPACING.xxs,
        SPACING.xxs,
        SPACING.sm,
        SPACING.xxs,
    )
    content_layout.setSpacing(SPACING.md)
    for group in all_groups:
        group.setParent(content)
        content_layout.addWidget(group)
    content_layout.addStretch(1)
    scroll_area.setWidget(content)
    scroll_area.viewport().setAutoFillBackground(False)
    container_layout.addWidget(scroll_area, 1)

    status_label = getattr(window, "status_label", None)
    insertion_index = root_layout.indexOf(status_label) if status_label is not None else -1
    if insertion_index < 0:
        button_box = getattr(window, "button_box", None)
        insertion_index = root_layout.indexOf(button_box) if button_box is not None else -1
    if insertion_index < 0:
        insertion_index = root_layout.count()
    root_layout.insertWidget(insertion_index, container, 1)

    group_rows: dict[int, int] = {}
    for row, (_name, groups) in enumerate(normalized):
        for group in groups:
            group_rows[id(group)] = row

    def activate(row: int) -> None:
        if row < 0 or row >= len(normalized):
            return
        active = set(normalized[row][1])
        for group in all_groups:
            group.setVisible(group in active)
        scroll_area.verticalScrollBar().setValue(0)
        content.updateGeometry()

    nav.currentRowChanged.connect(activate)
    window._settings_scroll_area = scroll_area
    window._settings_scroll_content = content
    window._settings_navigation_container = container
    window._settings_nav_list = nav
    window._settings_category_names = tuple(name for name, _groups in normalized)
    window._settings_group_rows = group_rows

    pending = str(getattr(window, "_pending_settings_category", "") or "")
    names = window._settings_category_names
    row = names.index(pending) if pending in names else 0
    nav.setCurrentRow(row)
    activate(row)
    _apply_product_style(window)
    _apply_window_bounds(window)
    return scroll_area


def _apply_legacy_scroll_layout(window: Any) -> QScrollArea | None:
    """Keep the original adapter for generic/older settings dialogs."""

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
    content_layout.setContentsMargins(0, 0, SPACING.xxs, 0)
    content_layout.setSpacing(SPACING.md)

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
    """Select the owning category, then reveal ``widget`` in the viewport."""

    scroll_area = apply_compact_settings_layout(window)
    if scroll_area is None or widget is None:
        return
    nav = getattr(window, "_settings_nav_list", None)
    group_rows = getattr(window, "_settings_group_rows", {})
    if isinstance(nav, QListWidget) and isinstance(group_rows, dict):
        row = group_rows.get(id(widget))
        if isinstance(row, int):
            nav.setCurrentRow(row)
    scroll_area.ensureWidgetVisible(widget, SPACING.lg, SPACING.lg)


def _apply_product_style(window: Any) -> None:
    manager = getattr(window, "settings_manager", None)
    theme = str(getattr(manager, "overlay_theme", "dark") or "dark")
    palette = OVERLAY_THEMES.get(theme, OVERLAY_THEMES["dark"])
    window.setStyleSheet(
        f"""
        QDialog#SettingsWindow {{
            background-color: {palette['surface_elevated']};
            color: {palette['text_primary']};
            font-family: "{TYPOGRAPHY.family}";
            font-size: {TYPOGRAPHY.body}px;
        }}
        QLabel#SettingsIntro,
        QLabel#SettingsReadingNote,
        QLabel#BrowserIntegrationHelp,
        QLabel#ResearchDataHelp {{
            color: {palette['text_secondary']};
        }}
        QListWidget#SettingsNavigation {{
            color: {palette['text_secondary']};
            background: transparent;
            border: none;
            outline: none;
            padding: {SPACING.xxs}px;
        }}
        QListWidget#SettingsNavigation::item {{
            border-radius: {RADIUS.md}px;
            padding: {SPACING.sm}px {SPACING.md}px;
            margin: {SPACING.xxs}px 0;
        }}
        QListWidget#SettingsNavigation::item:selected {{
            color: {palette['text_primary']};
            background-color: {palette['surface_hover']};
        }}
        QGroupBox {{
            color: {palette['text_primary']};
            border: 1px solid {palette['border_subtle']};
            border-radius: {RADIUS.lg}px;
            margin-top: {SPACING.md}px;
            padding-top: {SPACING.sm}px;
            font-weight: {TYPOGRAPHY.weight_semibold};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: {SPACING.md}px;
            padding: 0 {SPACING.xs}px;
            color: {palette['accent']};
        }}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            color: {palette['text_primary']};
            background-color: {palette['content_surface']};
            border: 1px solid {palette['border_subtle']};
            border-radius: {RADIUS.sm}px;
            padding: {SPACING.xs}px {SPACING.sm}px;
            selection-background-color: {palette['accent']};
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {palette['accent']};
        }}
        QPushButton {{
            color: {palette['text_primary']};
            background-color: transparent;
            border: 1px solid {palette['border_subtle']};
            border-radius: {RADIUS.sm}px;
            padding: {SPACING.sm}px {SPACING.md}px;
        }}
        QPushButton:hover:enabled {{
            background-color: {palette['surface_hover']};
            border-color: {palette['accent']};
        }}
        QCheckBox {{ color: {palette['text_primary']}; }}
        QLabel#SettingsStatusLabel {{ color: {palette['accent']}; }}
        """
    )


def _apply_window_bounds(window: Any) -> None:
    if getattr(window, "_settings_navigation_container", None) is not None:
        window.setMinimumSize(SETTINGS_WINDOW_NAV_MIN_WIDTH, SETTINGS_WINDOW_MIN_HEIGHT)
        window.setMaximumHeight(SETTINGS_WINDOW_MAX_HEIGHT)
        window.resize(SETTINGS_WINDOW_NAV_WIDTH, SETTINGS_WINDOW_DEFAULT_HEIGHT)
        return
    window.setMinimumSize(SETTINGS_WINDOW_MIN_WIDTH, SETTINGS_WINDOW_MIN_HEIGHT)
    window.setMaximumHeight(SETTINGS_WINDOW_MAX_HEIGHT)
    window.resize(SETTINGS_WINDOW_DEFAULT_WIDTH, SETTINGS_WINDOW_DEFAULT_HEIGHT)


__all__ = [
    "SETTINGS_NAVIGATION_WIDTH",
    "SETTINGS_SCROLL_STEP",
    "SETTINGS_WINDOW_DEFAULT_HEIGHT",
    "SETTINGS_WINDOW_DEFAULT_WIDTH",
    "SETTINGS_WINDOW_MAX_HEIGHT",
    "SETTINGS_WINDOW_MIN_HEIGHT",
    "SETTINGS_WINDOW_MIN_WIDTH",
    "SETTINGS_WINDOW_NAV_WIDTH",
    "apply_compact_settings_layout",
    "ensure_settings_widget_visible",
]
