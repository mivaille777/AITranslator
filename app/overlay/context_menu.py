"""Dark, keyboard-friendly context menu for the translation overlay."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from app.ui.design_tokens import (
    CONTROL,
    ICON,
    LAYOUT,
    RADIUS,
    SPACING,
    THEMES,
    legacy_overlay_palette,
)
from app.ui.svg_icons import icon_names, svg_icon


# Compatibility facade for code written before the design system. The actual
# theme source of truth now lives in app.ui.design_tokens.
OVERLAY_THEMES: dict[str, dict[str, str]] = {
    name: legacy_overlay_palette(name) for name in THEMES
}

THEME_LABELS = {
    "dark": "深色（默认）",
    "soft": "深色柔和",
    "contrast": "高对比度",
}

FONT_SIZE_OPTIONS = (12, 14, 16, 18, 20, 24, 28, 32)
OPACITY_OPTIONS = (0.2, 0.4, 0.6, 0.8, 1.0)
TARGET_LANGUAGE_CODE = "zh-CN"
TARGET_LANGUAGE_LABEL = "中文"
LANGUAGE_OPTIONS = (
    ("auto", "自动检测", "AUTO"),
    ("en", "英语", "EN"),
    ("ja", "日语", "JA"),
    ("ko", "韩语", "KO"),
    ("fr", "法语", "FR"),
    ("de", "德语", "DE"),
    ("es", "西班牙语", "ES"),
    ("zh-CN", "中文", "中文"),
)

# Keep the public constants for compatibility, but derive their values from the
# shared design system so menu metrics no longer drift independently.
SETTINGS_MENU_MAX_VISIBLE_ITEMS = LAYOUT.menu_visible_items
SETTINGS_MENU_ITEM_HEIGHT = CONTROL.normal_height + SPACING.xxs
SETTINGS_MENU_MIN_WIDTH = LAYOUT.menu_min_width
SETTINGS_MENU_MAX_HEIGHT = LAYOUT.menu_max_height
SETTINGS_MENU_OUTER_MARGIN = SPACING.sm

_ACTION_ICON_NAMES: dict[str, str] = {
    "copy_original": "copy",
    "copy_translation": "copy",
    "ai_translate": "translate",
    "ai_polish": "edit",
    "hide": "hide",
    "lock_position": "lock",
    "always_on_top": "pin",
    "show_original": "eye",
    "settings": "settings",
    "ai_settings": "sparkle",
    "about": "info",
    "exit": "power",
}

# Transitional bridge for large legacy surfaces such as OverlayWindow. Existing
# callers can keep passing their old glyph token while the renderer is already
# SVG-based. New code should call svg_icon() with a semantic name directly.
_LEGACY_SYMBOL_ICON_NAMES: dict[str, str] = {
    "☰": "menu",
    "…": "more",
    "⋯": "more",
    "▣": "copy",
    "▤": "copy",
    "＋": "add",
    "+": "add",
    "←": "back",
    "⌫": "delete",
    "■": "stop",
    "↻": "refresh",
    "↶": "undo",
    "✦": "sparkle",
    "译": "translate",
    "✎": "edit",
    "◌": "hide",
    "⌖": "lock",
    "↥": "pin",
    "文": "document",
    "◐": "opacity",
    "◒": "sparkle",
    "A": "font",
    "⚙": "settings",
    "ⓘ": "info",
    "⏻": "power",
    "记": "note",
    "库": "library",
    "簿": "history",
}


def normalize_language_code(value: object, *, fallback: str = "auto") -> str:
    """Return a canonical preset source-language code."""

    candidate = str(value).strip()
    for code, _label, _compact in LANGUAGE_OPTIONS:
        if candidate.lower() == code.lower():
            return code
    return fallback


def language_display_name(
    source_language: object,
    target_language: object,
    *,
    compact: bool = False,
) -> str:
    """Return the compact language direction shown on the Overlay."""

    source_code = normalize_language_code(source_language)
    source_compact = next(
        compact
        for code, _label, compact in LANGUAGE_OPTIONS
        if code == source_code
    )
    target = str(target_language).strip().lower()
    target_label = TARGET_LANGUAGE_LABEL if target in {"zh-cn", "zh"} else str(
        target_language
    ).strip() or TARGET_LANGUAGE_LABEL
    if compact and target_label == TARGET_LANGUAGE_LABEL:
        target_label = "中"
    if compact:
        return f"{source_compact}→{target_label}"
    return f"{source_compact} → {target_label}"


def symbol_icon(symbol: str, color: str, size: int = ICON.md) -> QIcon:
    """Compatibility wrapper that renders legacy glyph tokens as local SVG."""

    candidate = str(symbol or "").strip()
    semantic = _LEGACY_SYMBOL_ICON_NAMES.get(candidate)
    if semantic is None and candidate.lower() in icon_names():
        semantic = candidate.lower()
    return svg_icon(semantic or "document", color, size=size)


class ScrollableSettingsMenu(QMenu):
    """A bounded submenu whose settings actions live in a scroll area.

    ``QMenu`` only adds its own edge scrollers after it reaches screen bounds.
    Settings can grow independently of the desktop size, so this submenu uses
    an explicit ``QScrollArea``. Existing ``QAction`` objects remain the source
    of truth, preserving controller routing, shortcuts, enabled state, icons,
    and test access through ``actions_by_name``.
    """

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        max_height: int = SETTINGS_MENU_MAX_HEIGHT,
        max_visible_items: int = SETTINGS_MENU_MAX_VISIBLE_ITEMS,
    ) -> None:
        super().__init__(title, parent)
        self._max_height = max(CONTROL.large_height * 3, int(max_height))
        self._max_visible_items = max(1, int(max_visible_items))
        self._buttons: list[QToolButton] = []
        self._content_height = 0
        self._viewport_height = 0

        self.setMaximumHeight(self._max_height)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setObjectName("OverlaySettingsScrollArea")
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll_area.setMinimumWidth(SETTINGS_MENU_MIN_WIDTH)
        self._scroll_area.verticalScrollBar().setSingleStep(SETTINGS_MENU_ITEM_HEIGHT)

        self._scroll_content = QWidget(self._scroll_area)
        self._scroll_content.setObjectName("OverlaySettingsScrollContent")
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(
            SPACING.xs,
            SPACING.xs,
            SPACING.xs,
            SPACING.xs,
        )
        self._scroll_layout.setSpacing(SPACING.xxs)
        self._scroll_area.setWidget(self._scroll_content)

        self._scroll_action = QWidgetAction(self)
        self._scroll_action.setObjectName("OverlaySettingsScrollAction")
        self._scroll_action.setDefaultWidget(self._scroll_area)
        super().addAction(self._scroll_action)
        self._sync_scroll_extent()

    @property
    def scroll_area(self) -> QScrollArea:
        """Expose the bounded scroll area for state inspection and tests."""

        return self._scroll_area

    @property
    def has_overflow(self) -> bool:
        """Return whether not all settings rows fit in the visible viewport."""

        return self._content_height > self._viewport_height

    @property
    def visible_item_limit(self) -> int:
        return self._max_visible_items

    def add_scrollable_action(self, action: QAction) -> None:
        """Render one existing semantic action as a scrollable menu row."""

        button = QToolButton(self._scroll_content)
        button.setObjectName(f"{action.objectName()}Button")
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setAutoRaise(True)
        button.setFixedHeight(SETTINGS_MENU_ITEM_HEIGHT)
        button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._scroll_layout.addWidget(button)
        self._buttons.append(button)

        # QWidgetAction rows do not automatically collapse the whole menu
        # hierarchy after their QAction fires, so close the submenu chain here.
        action.triggered.connect(self._close_menu_chain)
        self._sync_scroll_extent()

    def _close_menu_chain(self, *_args: object) -> None:
        menu: QWidget | None = self
        while isinstance(menu, QMenu):
            menu.close()
            menu = menu.parentWidget()

    def _sync_scroll_extent(self) -> None:
        count = len(self._buttons)
        spacing = max(0, self._scroll_layout.spacing())
        rows_height = count * SETTINGS_MENU_ITEM_HEIGHT
        gaps_height = max(0, count - 1) * spacing
        self._content_height = SETTINGS_MENU_OUTER_MARGIN + rows_height + gaps_height
        visible_count = min(count, self._max_visible_items)
        visible_rows = visible_count * SETTINGS_MENU_ITEM_HEIGHT
        visible_gaps = max(0, visible_count - 1) * spacing
        natural_viewport_height = (
            SETTINGS_MENU_OUTER_MARGIN + visible_rows + visible_gaps
        )
        max_viewport_height = max(1, self._max_height - SPACING.lg)
        self._viewport_height = min(natural_viewport_height, max_viewport_height)
        if count == 0:
            self._viewport_height = 1

        # A minimum content height larger than the viewport is what makes the
        # QScrollArea expose its native scrollbar once the row limit is hit.
        self._scroll_content.setMinimumHeight(max(1, self._content_height))
        self._scroll_area.setFixedHeight(max(1, self._viewport_height))

    def apply_palette(self, palette: dict[str, str]) -> None:
        """Style the embedded scrolling controls with the Overlay palette."""

        self._scroll_area.setStyleSheet(
            f"""
            QScrollArea#OverlaySettingsScrollArea {{
                background-color: {palette['menu_background']};
                border: none;
            }}
            QScrollBar:vertical {{
                background: {palette['menu_background']};
                width: {RADIUS.lg}px;
                margin: {SPACING.xs}px {SPACING.xxs}px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {palette['border']};
                min-height: {ICON.xl}px;
                border-radius: {RADIUS.xs}px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {palette['accent']};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            """
        )
        self._scroll_content.setStyleSheet(
            f"""
            QWidget#OverlaySettingsScrollContent {{
                background-color: {palette['menu_background']};
            }}
            QToolButton {{
                background-color: transparent;
                color: {palette['text']};
                border: none;
                border-radius: {RADIUS.sm}px;
                padding: {SPACING.sm}px {SPACING.md}px;
                text-align: left;
            }}
            QToolButton:hover {{
                background-color: {palette['hover']};
                color: {palette['text']};
            }}
            QToolButton:disabled {{
                color: {palette['muted_text']};
            }}
            """
        )


class OverlayContextMenu(QMenu):
    """Context menu whose events are semantic and handled by the controller."""

    action_requested = Signal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("OverlayContextMenu")
        self.setSeparatorsCollapsible(False)
        self._menus: list[QMenu] = [self]
        self._theme_name = "dark"
        self._actions: dict[str, QAction] = {}
        self._background_opacity_actions: dict[float, QAction] = {}
        self._text_opacity_actions: dict[float, QAction] = {}
        self._font_size_actions: dict[int, QAction] = {}
        self._theme_actions: dict[str, QAction] = {}
        self._source_language_actions: dict[str, QAction] = {}
        self._build()
        # Keep the old private name as an alias for callers written before
        # the split opacity controls were introduced.
        self._opacity_actions = self._background_opacity_actions
        self.apply_theme(self._theme_name)

    @property
    def actions_by_name(self) -> dict[str, QAction]:
        """Return the primary actions for tests and state synchronization."""

        return dict(self._actions)

    @property
    def theme_name(self) -> str:
        return self._theme_name

    @property
    def language_menu(self) -> QMenu:
        """Return the source-language menu used by the header button."""

        return self._language_menu

    @property
    def ai_menu(self) -> QMenu:
        """Return the compact AI translation/polish submenu."""

        return self._ai_menu

    @property
    def settings_menu(self) -> ScrollableSettingsMenu:
        """Return the bounded, scrollable Settings submenu."""

        return self._settings_menu

    @property
    def source_language_actions(self) -> dict[str, QAction]:
        """Return preset source-language actions for state sync and tests."""

        return dict(self._source_language_actions)

    def _build(self) -> None:
        self._add_action("复制原文", "copy_original", icon_name="copy")
        self._add_action("复制译文", "copy_translation", icon_name="copy")

        self._ai_menu = self._make_submenu("AI 助手", "AI", "sparkle")
        self._add_submenu_action(
            self._ai_menu,
            "AI 翻译",
            "ai_translate",
            icon_name="translate",
        )
        self._add_submenu_action(
            self._ai_menu,
            "AI 润色",
            "ai_polish",
            icon_name="edit",
        )
        self.addSeparator()

        self._add_action("隐藏悬浮窗", "hide", icon_name="hide")
        self._add_action(
            "锁定位置",
            "lock_position",
            checkable=True,
            icon_name="lock",
        )
        self._add_action(
            "置顶显示",
            "always_on_top",
            checkable=True,
            icon_name="pin",
        )
        self._add_action(
            "显示原文",
            "show_original",
            checkable=True,
            icon_name="eye",
        )
        self.addSeparator()

        self._language_menu = self._make_submenu("翻译语言", "Language", "language")
        target_action = QAction(
            f"目标语言：{TARGET_LANGUAGE_LABEL}",
            self._language_menu,
        )
        target_action.setEnabled(False)
        self._language_menu.addAction(target_action)
        self._language_menu.addSeparator()
        source_label_action = QAction("源语言", self._language_menu)
        source_label_action.setEnabled(False)
        self._language_menu.addAction(source_label_action)
        source_group = QActionGroup(self)
        source_group.setExclusive(True)
        for code, label, _compact in LANGUAGE_OPTIONS:
            action = QAction(label, self._language_menu)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, selected=code: self._emit(
                    "source_language",
                    selected,
                )
            )
            source_group.addAction(action)
            self._language_menu.addAction(action)
            self._source_language_actions[code] = action

        self._background_opacity_menu, self._background_opacity_actions = (
            self._make_opacity_submenu(
                "背景透明度",
                "BackgroundOpacity",
                "opacity",
                "background_opacity",
            )
        )
        self._text_opacity_menu, self._text_opacity_actions = (
            self._make_opacity_submenu(
                "字体透明度",
                "TextOpacity",
                "font",
                "text_opacity",
            )
        )

        self._font_size_menu = self._make_submenu("字体大小", "FontSize", "font")
        font_group = QActionGroup(self)
        font_group.setExclusive(True)
        for size in FONT_SIZE_OPTIONS:
            action = QAction(f"{size}px", self._font_size_menu)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, selected=size: self._emit(
                    "font_size",
                    selected,
                )
            )
            font_group.addAction(action)
            self._font_size_menu.addAction(action)
            self._font_size_actions[size] = action

        self._theme_menu = self._make_submenu("主题切换", "Theme", "sparkle")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for name in THEMES:
            action = QAction(THEME_LABELS[name], self._theme_menu)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, selected=name: self._emit(
                    "theme",
                    selected,
                )
            )
            theme_group.addAction(action)
            self._theme_menu.addAction(action)
            self._theme_actions[name] = action

        self.addSeparator()
        self._settings_menu = self._make_scrollable_settings_submenu(
            "设置",
            "Settings",
            "settings",
        )
        self._add_submenu_action(
            self._settings_menu,
            "常规设置...",
            "settings",
            icon_name="settings",
        )
        self._add_submenu_action(
            self._settings_menu,
            "AI 大模型与 API Key...",
            "ai_settings",
            icon_name="sparkle",
        )
        self._add_action("关于", "about", icon_name="info")
        self.addSeparator()
        self._add_action("退出", "exit", icon_name="power")

    def _add_action(
        self,
        text: str,
        key: str,
        *,
        checkable: bool = False,
        icon_name: str | None = None,
    ) -> QAction:
        action = QAction(text, self)
        action.setObjectName(f"OverlayContext{key.title().replace('_', '')}Action")
        action.setCheckable(checkable)
        if icon_name:
            action.setIcon(svg_icon(icon_name, OVERLAY_THEMES["dark"]["text"]))
        action.triggered.connect(
            lambda checked=False, action_key=key: self._emit(
                action_key,
                bool(checked) if checkable else None,
            )
        )
        self.addAction(action)
        self._actions[key] = action
        return action

    def _add_submenu_action(
        self,
        menu: QMenu,
        text: str,
        key: str,
        *,
        icon_name: str | None = None,
    ) -> QAction:
        """Add a semantic action to a submenu while keeping one action index."""

        action = QAction(text, menu)
        action.setObjectName(f"OverlayContext{key.title().replace('_', '')}Action")
        if icon_name:
            action.setIcon(svg_icon(icon_name, OVERLAY_THEMES["dark"]["text"]))
        action.triggered.connect(
            lambda _checked=False, action_key=key: self._emit(action_key, None)
        )
        if isinstance(menu, ScrollableSettingsMenu):
            menu.add_scrollable_action(action)
        else:
            menu.addAction(action)
        self._actions[key] = action
        return action

    def _make_submenu(self, title: str, key: str, icon_name: str) -> QMenu:
        menu = QMenu(title, self)
        menu.setObjectName(f"OverlayContext{key}Menu")
        menu.setIcon(svg_icon(icon_name, OVERLAY_THEMES["dark"]["text"]))
        self.addMenu(menu)
        self._menus.append(menu)
        return menu

    def _make_scrollable_settings_submenu(
        self,
        title: str,
        key: str,
        icon_name: str,
    ) -> ScrollableSettingsMenu:
        menu = ScrollableSettingsMenu(title, self)
        menu.setObjectName(f"OverlayContext{key}Menu")
        menu.setIcon(svg_icon(icon_name, OVERLAY_THEMES["dark"]["text"]))
        self.addMenu(menu)
        self._menus.append(menu)
        return menu

    def _make_opacity_submenu(
        self,
        title: str,
        key: str,
        icon_name: str,
        action_key: str,
    ) -> tuple[QMenu, dict[float, QAction]]:
        """Create one independent opacity submenu and its checkable actions."""

        menu = self._make_submenu(title, key, icon_name)
        actions: dict[float, QAction] = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for value in OPACITY_OPTIONS:
            action = QAction(f"{int(value * 100)}%", menu)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, selected=value: self._emit(
                    action_key,
                    selected,
                )
            )
            group.addAction(action)
            menu.addAction(action)
            actions[value] = action
        return menu, actions

    def _emit(self, key: str, value: object = None) -> None:
        self.action_requested.emit(key, value)

    def set_ai_enabled(self, enabled: bool) -> None:
        """Enable AI operations only while source text is available."""

        enabled = bool(enabled)
        self._ai_menu.setEnabled(enabled)
        for key in ("ai_translate", "ai_polish"):
            action = self._actions.get(key)
            if action is not None:
                action.setEnabled(enabled)

    def set_lock_checked(self, checked: bool) -> None:
        action = self._actions.get("lock_position")
        if action is None:
            return
        blocked = action.blockSignals(True)
        action.setChecked(bool(checked))
        action.blockSignals(blocked)

    def set_always_on_top_checked(self, checked: bool) -> None:
        action = self._actions.get("always_on_top")
        if action is None:
            return
        blocked = action.blockSignals(True)
        action.setChecked(bool(checked))
        action.blockSignals(blocked)

    def set_original_checked(self, checked: bool) -> None:
        action = self._actions.get("show_original")
        if action is None:
            return
        blocked = action.blockSignals(True)
        action.setChecked(bool(checked))
        action.blockSignals(blocked)

    def sync_state(
        self,
        *,
        locked: bool,
        always_on_top: bool,
        font_size: int,
        theme: str,
        background_opacity: float | None = None,
        text_opacity: float | None = None,
        opacity: float | None = None,
        original_visible: bool = False,
        source_language: str = "auto",
        target_language: str = TARGET_LANGUAGE_CODE,
        ai_enabled: bool = True,
    ) -> None:
        """Update checkmarks before the menu is shown.

        ``opacity`` remains an optional compatibility alias for older
        callers; new callers should provide both independent values.
        """

        self.set_lock_checked(locked)
        self.set_always_on_top_checked(always_on_top)
        self.set_original_checked(original_visible)
        self.set_ai_enabled(ai_enabled)
        if background_opacity is None:
            background_opacity = opacity if opacity is not None else 1.0
        if text_opacity is None:
            text_opacity = opacity if opacity is not None else 1.0
        self._set_checked_value(self._background_opacity_actions, background_opacity)
        self._set_checked_value(self._text_opacity_actions, text_opacity)
        self._set_checked_value(self._font_size_actions, font_size)
        normalized_theme = theme if theme in self._theme_actions else "dark"
        self._set_checked_value(self._theme_actions, normalized_theme)
        normalized_source = normalize_language_code(source_language)
        self._set_checked_value(
            self._source_language_actions,
            normalized_source,
        )

    @staticmethod
    def _set_checked_value(mapping: dict, value: object) -> None:
        for candidate, action in mapping.items():
            blocked = action.blockSignals(True)
            if isinstance(candidate, float):
                checked = abs(float(value) - candidate) < 0.001
            else:
                checked = candidate == value
            action.setChecked(checked)
            action.blockSignals(blocked)

    def apply_theme(self, theme: str) -> None:
        """Apply the reference palette to this menu and its submenus."""

        self._theme_name = theme if theme in OVERLAY_THEMES else "dark"
        palette = OVERLAY_THEMES[self._theme_name]
        for menu in self._menus:
            menu.setStyleSheet(
                f"""
                QMenu#{menu.objectName()} {{
                    background-color: {palette['menu_background']};
                    color: {palette['text']};
                    border: 1px solid {palette['border']};
                    border-radius: {RADIUS.md}px;
                    padding: {SPACING.sm}px 0px;
                }}
                QMenu#{menu.objectName()}::item {{
                    background-color: transparent;
                    color: {palette['text']};
                    padding: {SPACING.sm}px {SPACING.md}px {SPACING.sm}px {SPACING.xxl}px;
                    margin: {SPACING.xxs}px {SPACING.xs}px;
                    min-width: {LAYOUT.menu_item_min_width}px;
                    border-radius: {RADIUS.sm}px;
                }}
                QMenu#{menu.objectName()}::item:selected {{
                    background-color: {palette['hover']};
                    color: {palette['text']};
                }}
                QMenu#{menu.objectName()}::item:disabled {{
                    color: {palette['muted_text']};
                }}
                QMenu#{menu.objectName()}::separator {{
                    height: 1px;
                    background-color: {palette['border']};
                    margin: {SPACING.sm}px {SPACING.md}px;
                }}
                """
            )
        icon_color = palette["text"]
        for key, action in self._actions.items():
            icon_name = _ACTION_ICON_NAMES.get(key)
            if icon_name:
                action.setIcon(svg_icon(icon_name, icon_color, size=ICON.md))
        self._ai_menu.setIcon(svg_icon("sparkle", palette["accent"], size=ICON.md))
        self._settings_menu.setIcon(svg_icon("settings", icon_color, size=ICON.md))
        self._settings_menu.apply_palette(palette)
        self._background_opacity_menu.setIcon(svg_icon("opacity", icon_color, size=ICON.md))
        self._text_opacity_menu.setIcon(svg_icon("font", icon_color, size=ICON.md))
        self._language_menu.setIcon(svg_icon("language", icon_color, size=ICON.md))
        self._font_size_menu.setIcon(svg_icon("font", icon_color, size=ICON.md))
        self._theme_menu.setIcon(svg_icon("sparkle", icon_color, size=ICON.md))


__all__ = [
    "FONT_SIZE_OPTIONS",
    "LANGUAGE_OPTIONS",
    "OPACITY_OPTIONS",
    "OVERLAY_THEMES",
    "SETTINGS_MENU_ITEM_HEIGHT",
    "SETTINGS_MENU_MAX_HEIGHT",
    "SETTINGS_MENU_MAX_VISIBLE_ITEMS",
    "SETTINGS_MENU_MIN_WIDTH",
    "TARGET_LANGUAGE_CODE",
    "TARGET_LANGUAGE_LABEL",
    "OverlayContextMenu",
    "ScrollableSettingsMenu",
    "THEME_LABELS",
    "language_display_name",
    "normalize_language_code",
    "symbol_icon",
]
