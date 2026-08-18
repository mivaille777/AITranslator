"""Dark, keyboard-friendly context menu for the translation overlay."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu


OVERLAY_THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "label_background": "rgba(30, 41, 59, 242)",
        "menu_background": "#1E293B",
        "text": "#F8FAFC",
        "muted_text": "#CBD5E1",
        "border": "#334155",
        "hover": "#334155",
        "accent": "#60A5FA",
        "shadow": "rgba(0, 0, 0, 165)",
    },
    "soft": {
        "label_background": "rgba(43, 47, 54, 242)",
        "menu_background": "#2B2F36",
        "text": "#F5F7FA",
        "muted_text": "#D5DAE2",
        "border": "#494F5A",
        "hover": "#494F5A",
        "accent": "#AEB9C9",
        "shadow": "rgba(0, 0, 0, 150)",
    },
    "contrast": {
        "label_background": "rgba(13, 17, 23, 248)",
        "menu_background": "#0D1117",
        "text": "#00E6B8",
        "muted_text": "#B7FFF1",
        "border": "#00E6B8",
        "hover": "#173C3A",
        "accent": "#00E6B8",
        "shadow": "rgba(0, 0, 0, 190)",
    },
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


def _symbol_icon(symbol: str, color: str, size: int = 18) -> QIcon:
    """Create a small self-contained line-style icon without external assets."""

    icon_size = max(12, int(size))
    pixmap = QPixmap(icon_size, icon_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QColor(color))
    painter.setFont(QFont("Segoe UI Symbol", max(10, round(icon_size * 0.62))))
    painter.drawText(
        QRect(0, 0, icon_size, icon_size),
        Qt.AlignmentFlag.AlignCenter,
        symbol,
    )
    painter.end()
    return QIcon(pixmap)


def symbol_icon(symbol: str, color: str, size: int = 18) -> QIcon:
    """Return a generated glyph icon for compact Overlay controls."""

    return _symbol_icon(symbol, color, size)


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
    def source_language_actions(self) -> dict[str, QAction]:
        """Return preset source-language actions for state sync and tests."""

        return dict(self._source_language_actions)

    def _build(self) -> None:
        self._add_action(
            "复制原文",
            "copy_original",
            symbol="▣",
        )
        self._add_action(
            "复制译文",
            "copy_translation",
            symbol="▤",
        )

        self._ai_menu = self._make_submenu("AI 助手", "AI", "✦")
        self._add_submenu_action(
            self._ai_menu,
            "AI 翻译",
            "ai_translate",
            symbol="译",
        )
        self._add_submenu_action(
            self._ai_menu,
            "AI 润色",
            "ai_polish",
            symbol="✎",
        )
        self.addSeparator()

        self._add_action("隐藏悬浮窗", "hide", symbol="◌")
        self._add_action(
            "锁定位置",
            "lock_position",
            checkable=True,
            symbol="⌖",
        )
        self._add_action(
            "置顶显示",
            "always_on_top",
            checkable=True,
            symbol="↥",
        )
        self._add_action(
            "显示原文",
            "show_original",
            checkable=True,
            symbol="文",
        )
        self.addSeparator()

        self._language_menu = self._make_submenu("翻译语言", "Language", "文")
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
                "◐",
                "background_opacity",
            )
        )
        self._text_opacity_menu, self._text_opacity_actions = (
            self._make_opacity_submenu(
                "字体透明度",
                "TextOpacity",
                "A",
                "text_opacity",
            )
        )

        self._font_size_menu = self._make_submenu("字体大小", "FontSize", "A")
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

        self._theme_menu = self._make_submenu("主题切换", "Theme", "◒")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for name in ("dark", "soft", "contrast"):
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
        self._add_action("设置...", "settings", symbol="⚙")
        self._add_action("关于", "about", symbol="ⓘ")
        self.addSeparator()
        self._add_action("退出", "exit", symbol="⏻")

    def _add_action(
        self,
        text: str,
        key: str,
        *,
        checkable: bool = False,
        symbol: str | None = None,
    ) -> QAction:
        action = QAction(text, self)
        action.setObjectName(f"OverlayContext{key.title().replace('_', '')}Action")
        action.setCheckable(checkable)
        if symbol:
            action.setIcon(_symbol_icon(symbol, OVERLAY_THEMES["dark"]["text"]))
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
        symbol: str | None = None,
    ) -> QAction:
        """Add a semantic action to a submenu while keeping one action index."""

        action = QAction(text, menu)
        action.setObjectName(f"OverlayContext{key.title().replace('_', '')}Action")
        if symbol:
            action.setIcon(_symbol_icon(symbol, OVERLAY_THEMES["dark"]["text"]))
        action.triggered.connect(
            lambda _checked=False, action_key=key: self._emit(action_key, None)
        )
        menu.addAction(action)
        self._actions[key] = action
        return action

    def _make_submenu(self, title: str, key: str, symbol: str) -> QMenu:
        menu = QMenu(title, self)
        menu.setObjectName(f"OverlayContext{key}Menu")
        menu.setIcon(_symbol_icon(symbol, OVERLAY_THEMES["dark"]["text"]))
        self.addMenu(menu)
        self._menus.append(menu)
        return menu

    def _make_opacity_submenu(
        self,
        title: str,
        key: str,
        symbol: str,
        action_key: str,
    ) -> tuple[QMenu, dict[float, QAction]]:
        """Create one independent opacity submenu and its checkable actions."""

        menu = self._make_submenu(title, key, symbol)
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
                    border-radius: 8px;
                    padding: 7px 0px;
                }}
                QMenu#{menu.objectName()}::item {{
                    background-color: transparent;
                    color: {palette['text']};
                    padding: 7px 10px 7px 30px;
                    margin: 1px 4px;
                    min-width: 150px;
                    border-radius: 5px;
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
                    margin: 6px 12px;
                }}
                """
            )
        icon_color = palette["text"]
        for action in self._actions.values():
            # Repaint the generated glyphs for high-contrast mode too.
            symbol = {
                "copyoriginal": "▣",
                "copytranslation": "▤",
                "aitranslate": "译",
                "aipolish": "✎",
                "hide": "◌",
                "lockposition": "⌖",
                "alwaysontop": "↥",
                "showoriginal": "文",
                "settings": "⚙",
                "about": "ⓘ",
                "exit": "⏻",
            }.get(
                action.objectName()
                .replace("OverlayContext", "")
                .replace("Action", "")
                .lower()
            )
            if symbol:
                action.setIcon(_symbol_icon(symbol, icon_color))
        self._ai_menu.setIcon(_symbol_icon("✦", palette["accent"]))
        self._background_opacity_menu.setIcon(_symbol_icon("◐", icon_color))
        self._text_opacity_menu.setIcon(_symbol_icon("A", icon_color))
        self._language_menu.setIcon(_symbol_icon("文", icon_color))
        self._font_size_menu.setIcon(_symbol_icon("A", icon_color))
        self._theme_menu.setIcon(_symbol_icon("◒", icon_color))


__all__ = [
    "FONT_SIZE_OPTIONS",
    "LANGUAGE_OPTIONS",
    "OPACITY_OPTIONS",
    "OVERLAY_THEMES",
    "TARGET_LANGUAGE_CODE",
    "TARGET_LANGUAGE_LABEL",
    "OverlayContextMenu",
    "THEME_LABELS",
    "language_display_name",
    "normalize_language_code",
    "symbol_icon",
]
