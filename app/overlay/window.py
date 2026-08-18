"""Transparent, frameless, always-on-top overlay window."""

from __future__ import annotations

from collections.abc import Sequence
import math
import re
from typing import Any

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QParallelAnimationGroup,
    Property,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QGuiApplication, QScreen
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.overlay.context_menu import (
    OVERLAY_THEMES,
    TARGET_LANGUAGE_CODE,
    OverlayContextMenu,
    language_display_name,
    normalize_language_code,
    symbol_icon,
)
from app.overlay.positioning import PositionManager, PositionMode
from app.overlay.win32_adapter import Win32OverlayAdapter

DEFAULT_TEST_TEXT = "Overlay test / 悬浮翻译测试"
DEFAULT_MAX_WIDTH = 900
DEFAULT_MIN_WIDTH = 240
DEFAULT_MIN_HEIGHT = 56
DEFAULT_FONT_FAMILY = "Segoe UI"
DEFAULT_FONT_SIZE = 24
# ``DEFAULT_OPACITY`` is retained as the legacy setting name. The visual
# implementation now stores background and text alpha independently.
DEFAULT_OPACITY = 1.0
DEFAULT_BACKGROUND_OPACITY = 1.0
DEFAULT_TEXT_OPACITY = 1.0
DEFAULT_THEME = "dark"
DEFAULT_SOURCE_LANGUAGE = "auto"
DEFAULT_TARGET_LANGUAGE = TARGET_LANGUAGE_CODE
SHOW_ANIMATION_MILLISECONDS = 160
CONTENT_ANIMATION_MILLISECONDS = 150
HOVER_ANIMATION_MILLISECONDS = 120
RESIZE_ANIMATION_MILLISECONDS = 200
LOADING_INTERVAL_MILLISECONDS = 300
COPY_FEEDBACK_MILLISECONDS = 1000
_RGBA_COLOR_RE = re.compile(
    r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",
    re.IGNORECASE,
)


class OverlayWindow(QWidget):
    """A readable transparent window for displaying translation text."""

    context_action = Signal(str, object)

    def _get_content_fade_opacity(self) -> float:
        return self._content_fade_opacity

    def _set_content_fade_opacity(self, value: float) -> None:
        self._content_fade_opacity = min(1.0, max(0.0, float(value)))
        if hasattr(self, "_label") and hasattr(self, "_theme_name"):
            self._apply_content_style(OVERLAY_THEMES[self._theme_name])

    contentFadeOpacity = Property(
        float,
        _get_content_fade_opacity,
        _set_content_fade_opacity,
    )

    def _get_header_emphasis(self) -> float:
        return self._header_emphasis

    def _set_header_emphasis(self, value: float) -> None:
        self._header_emphasis = min(1.0, max(0.0, float(value)))
        if hasattr(self, "_header") and hasattr(self, "_theme_name"):
            self._apply_header_style(OVERLAY_THEMES[self._theme_name])

    headerEmphasis = Property(
        float,
        _get_header_emphasis,
        _set_header_emphasis,
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        max_width: int = DEFAULT_MAX_WIDTH,
        win32_adapter: Win32OverlayAdapter | None = None,
        position_manager: PositionManager | None = None,
        config_manager: Any | None = None,
    ) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(parent, flags)

        if config_manager is not None:
            max_width = getattr(config_manager, "overlay_max_width", max_width)
        self._max_width = self._coerce_max_width(max_width)
        self._font_family = (
            str(
                getattr(
                    config_manager,
                    "overlay_font_family",
                    DEFAULT_FONT_FAMILY,
                )
            ).strip()
            or DEFAULT_FONT_FAMILY
        )
        self._font_size = self._coerce_font_size(
            getattr(config_manager, "overlay_font_size", DEFAULT_FONT_SIZE)
        )
        legacy_opacity = self._coerce_opacity(
            getattr(config_manager, "overlay_opacity", DEFAULT_OPACITY)
        )
        self._background_opacity = self._coerce_opacity(
            getattr(
                config_manager,
                "overlay_background_opacity",
                legacy_opacity,
            )
        )
        self._text_opacity = self._coerce_opacity(
            getattr(
                config_manager,
                "overlay_text_opacity",
                DEFAULT_TEXT_OPACITY,
            )
        )
        # Compatibility alias for code that still reads ``opacity``.
        self._opacity = self._background_opacity
        self._theme_name = self._coerce_theme(
            getattr(config_manager, "overlay_theme", DEFAULT_THEME)
        )
        self._source_language = normalize_language_code(
            getattr(
                config_manager,
                "translation_source_language",
                DEFAULT_SOURCE_LANGUAGE,
            )
        )
        self._target_language = str(
            getattr(
                config_manager,
                "translation_target_language",
                DEFAULT_TARGET_LANGUAGE,
            )
        ).strip() or DEFAULT_TARGET_LANGUAGE
        self._original_visible = bool(
            getattr(config_manager, "overlay_show_original", False)
        )
        self._source_text = ""
        self._translation_text = ""
        self._hovered = False
        self._content_fade_opacity = 1.0
        self._header_emphasis = 0.82
        self._loading_active = False
        self._loading_phase = 0
        self._show_animation: QParallelAnimationGroup | None = None
        self._content_animation: QPropertyAnimation | None = None
        self._header_animation: QPropertyAnimation | None = None
        self._resize_animation: QPropertyAnimation | None = None
        self._copy_feedback_active = False
        self._win32_adapter = win32_adapter or Win32OverlayAdapter()
        self._position_manager = position_manager or PositionManager()
        self._preferred_screen: QScreen | None = None
        self._is_locked = False
        self._always_on_top = True
        self._dragging = False
        self._drag_offset = QPoint()

        self.setObjectName("OverlayWindow")
        # Showing a result must never move keyboard focus away from the
        # application whose selection will be copied on the next hotkey.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setMinimumSize(
            QSize(
                min(DEFAULT_MIN_WIDTH, self._max_width),
                DEFAULT_MIN_HEIGHT,
            )
        )

        self._header = QWidget(self)
        self._header.setObjectName("OverlayHeader")
        self._header.setMouseTracking(True)
        self._header_layout = QHBoxLayout(self._header)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(6)

        self._language_button = QToolButton(self._header)
        self._language_button.setObjectName("OverlayLanguageButton")
        self._language_button.setText(
            language_display_name(self._source_language, self._target_language)
        )
        self._language_button.setToolTip("选择源语言")
        self._language_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._language_button.setAutoRaise(True)
        self._language_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        self._language_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self._language_button.setMinimumWidth(0)
        self._language_button.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        self._copy_button = QToolButton(self._header)
        self._copy_button.setObjectName("OverlayCopyButton")
        self._copy_button.setText("")
        self._copy_button.setToolTip("复制译文")
        self._copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_button.setAutoRaise(True)
        self._copy_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self._copy_button.setIconSize(QSize(22, 22))
        self._copy_button.setFixedSize(38, 34)

        self._menu_button = QToolButton(self._header)
        self._menu_button.setObjectName("OverlayMenuButton")
        self._menu_button.setText("")
        self._menu_button.setToolTip("更多操作")
        self._menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_button.setAutoRaise(True)
        self._menu_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self._menu_button.setIconSize(QSize(24, 24))
        self._menu_button.setFixedSize(38, 34)

        self._header_layout.addWidget(self._language_button, 0)
        self._header_layout.addStretch(1)
        self._header_layout.addWidget(self._copy_button)
        self._header_layout.addWidget(self._menu_button)
        self._header.installEventFilter(self)

        self._content = QWidget(self)
        self._content.setObjectName("OverlayContent")
        self._content.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(3)

        self._source_label = QLabel(self._content)
        self._source_label.setObjectName("OverlaySourceLabel")
        self._source_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._source_label.setWordWrap(True)
        self._source_label.setTextFormat(Qt.TextFormat.PlainText)
        self._source_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self._source_label.setFont(
            QFont(
                self._font_family,
                max(8, min(14, round(self._font_size * 0.55))),
            )
        )
        self._source_label.setVisible(self._original_visible)

        self._label = QLabel(self._content)
        self._label.setObjectName("OverlayTextLabel")
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # Let the top-level window receive mouse events while unlocked so it
        # can implement drag behavior. Locked click-through is handled by the
        # Windows adapter, not by this Qt attribute.
        self._label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self._label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        self._label.setMaximumWidth(self._max_width)
        self._label.setFont(QFont(self._font_family, self._font_size))
        self._source_label.setFont(
            QFont(
                self._font_family,
                max(8, min(14, round(self._font_size * 0.55))),
            )
        )
        self._shadow_effect = QGraphicsDropShadowEffect(self._label)
        self._shadow_effect.setBlurRadius(14)
        self._shadow_effect.setOffset(0, 2)
        self._label.setGraphicsEffect(self._shadow_effect)

        self._content_layout.addWidget(self._source_label)
        self._content_layout.addWidget(self._label)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 10, 10)
        self._layout.setSpacing(3)
        self._layout.addWidget(self._header)
        self._layout.addWidget(self._content)

        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(LOADING_INTERVAL_MILLISECONDS)
        self._loading_timer.timeout.connect(self._advance_loading)
        self._copy_feedback_timer = QTimer(self)
        self._copy_feedback_timer.setSingleShot(True)
        self._copy_feedback_timer.timeout.connect(self._restore_copy_button)

        self._context_menu = OverlayContextMenu(self)
        self._language_button.setMenu(self._context_menu.language_menu)
        self._context_menu.language_menu.aboutToShow.connect(
            self._sync_context_menu_state
        )
        self._copy_button.clicked.connect(self._emit_copy_translation)
        self._menu_button.clicked.connect(self._open_overflow_menu)
        self._context_menu.action_requested.connect(self._handle_context_action)
        self._apply_theme(self._theme_name)
        self._set_content(
            "",
            DEFAULT_TEST_TEXT,
            self._source_language,
            self._target_language,
        )
        # A top-level opacity would multiply both the background and the
        # text. Keep the window fully opaque and apply alpha in the label's
        # background/text colors instead.
        self.setWindowOpacity(1.0)

    @staticmethod
    def _coerce_max_width(value: object) -> int:
        try:
            return min(10000, max(120, int(value)))
        except (TypeError, ValueError):
            return DEFAULT_MAX_WIDTH

    @staticmethod
    def _coerce_font_size(value: object) -> int:
        try:
            return min(200, max(8, int(value)))
        except (TypeError, ValueError):
            return DEFAULT_FONT_SIZE

    @staticmethod
    def _coerce_opacity(value: object) -> float:
        try:
            opacity = float(value)
            if not math.isfinite(opacity):
                raise ValueError("opacity must be finite")
            return min(1.0, max(0.1, opacity))
        except (TypeError, ValueError):
            return DEFAULT_OPACITY

    @staticmethod
    def _rgba_with_opacity(
        color: str,
        opacity: float,
        *,
        multiply_existing_alpha: bool = False,
    ) -> str:
        """Return a QSS rgba color with the requested visual opacity."""

        qcolor = QColor(color)
        if not qcolor.isValid():
            match = _RGBA_COLOR_RE.fullmatch(str(color).strip())
            if match is not None:
                qcolor = QColor(
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                    int(match.group(4)),
                )
        if not qcolor.isValid():
            return color
        if opacity >= 0.999:
            return color
        alpha = qcolor.alpha()
        if multiply_existing_alpha:
            alpha = round(alpha * opacity)
        else:
            alpha = round(255 * opacity)
        return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {alpha})"

    @staticmethod
    def _coerce_theme(value: object) -> str:
        normalized = str(value).strip().lower()
        aliases = {
            "dark": "dark",
            "soft": "soft",
            "dark_soft": "soft",
            "contrast": "contrast",
            "high_contrast": "contrast",
        }
        return aliases.get(normalized, DEFAULT_THEME)

    @property
    def max_width(self) -> int:
        """Maximum width used for wrapped overlay content."""

        return self._max_width

    @property
    def text_label(self) -> QLabel:
        """Return the label for read-only presentation and GUI tests."""

        return self._label

    def text(self) -> str:
        """Return the currently displayed text."""

        return self._label.text()

    @property
    def source_text(self) -> str:
        """Return the source text associated with the current result."""

        return self._source_text

    @property
    def translation_text(self) -> str:
        """Return the translated text associated with the current result."""

        return self._translation_text

    @property
    def original_visible(self) -> bool:
        """Return whether the optional source-text row is visible."""

        return self._original_visible

    @property
    def source_language(self) -> str:
        """Return the selected preset source-language code."""

        return self._source_language

    @property
    def target_language(self) -> str:
        """Return the displayed target-language code."""

        return self._target_language

    @property
    def language_button(self) -> QToolButton:
        """Return the compact language selector in the header."""

        return self._language_button

    @property
    def copy_button(self) -> QToolButton:
        """Return the translation-copy button in the header."""

        return self._copy_button

    @property
    def menu_button(self) -> QToolButton:
        """Return the overflow-menu button in the header."""

        return self._menu_button

    @property
    def font_family(self) -> str:
        """Return the configured Overlay font family."""

        return self._font_family

    @property
    def font_size(self) -> int:
        """Return the configured Overlay font size."""

        return self._font_size

    @property
    def opacity(self) -> float:
        """Return the legacy opacity alias, mapped to the background."""

        return self._opacity

    @property
    def background_opacity(self) -> float:
        """Return the independent Overlay background opacity."""

        return self._background_opacity

    @property
    def text_opacity(self) -> float:
        """Return the independent Overlay text opacity."""

        return self._text_opacity

    @property
    def theme_name(self) -> str:
        """Return the active reference palette name."""

        return self._theme_name

    @property
    def context_menu(self) -> OverlayContextMenu:
        """Return the overlay menu for controller wiring and GUI tests."""

        return self._context_menu

    @property
    def always_on_top(self) -> bool:
        """Return whether the overlay requests topmost presentation."""

        return self._always_on_top

    @property
    def is_dragging(self) -> bool:
        """Return whether the user is currently dragging the Overlay."""

        return self._dragging

    @property
    def is_loading(self) -> bool:
        """Return whether the overlay is currently showing its loading state."""

        return self._loading_active

    @property
    def is_hovered(self) -> bool:
        """Return whether the pointer is currently inside the Overlay card."""

        return self._hovered

    def apply_style(
        self,
        *,
        font_family: str | None = None,
        font_size: int | None = None,
        opacity: float | None = None,
        background_opacity: float | None = None,
        text_opacity: float | None = None,
        max_width: int | None = None,
    ) -> None:
        """Apply safe visual settings and resize the current content."""

        if font_family is not None:
            candidate_family = str(font_family).strip()
            if candidate_family:
                self._font_family = candidate_family
        if font_size is not None:
            self._font_size = self._coerce_font_size(font_size)
        if opacity is not None:
            # Older callers supplied one value for both visual layers.
            legacy_opacity = self._coerce_opacity(opacity)
            if background_opacity is None:
                background_opacity = legacy_opacity
            if text_opacity is None:
                text_opacity = legacy_opacity
        if background_opacity is not None:
            self._background_opacity = self._coerce_opacity(background_opacity)
        if text_opacity is not None:
            self._text_opacity = self._coerce_opacity(text_opacity)
        self._opacity = self._background_opacity
        if max_width is not None:
            self._max_width = self._coerce_max_width(max_width)

        self._label.setFont(QFont(self._font_family, self._font_size))
        self._source_label.setFont(
            QFont(
                self._font_family,
                max(8, min(14, round(self._font_size * 0.55))),
            )
        )
        self._label.setMaximumWidth(self._max_width)
        self.setMinimumSize(
            QSize(
                min(DEFAULT_MIN_WIDTH, self._max_width),
                DEFAULT_MIN_HEIGHT,
            )
        )
        self.setWindowOpacity(1.0)
        self._apply_theme(self._theme_name)
        self._content_layout.activate()
        self._layout.activate()
        self._label.adjustSize()
        self.adjustSize()
        self._clamp_current_position()

    def _apply_header_style(self, palette: dict[str, str]) -> None:
        """Apply the animated header emphasis without a graphics effect."""

        header_text = self._rgba_with_opacity(
            palette["text"],
            self._header_emphasis,
        )
        header_muted_text = self._rgba_with_opacity(
            palette["muted_text"],
            self._header_emphasis,
        )
        self._header.setStyleSheet(
            f"""
            QWidget#OverlayHeader {{
                background-color: transparent;
                border: none;
            }}
            QToolButton#OverlayLanguageButton,
            QToolButton#OverlayCopyButton,
            QToolButton#OverlayMenuButton {{
                color: {header_text};
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 2px 6px;
                font-size: 13px;
            }}
            QToolButton#OverlayLanguageButton::menu-indicator {{
                image: none;
                width: 0px;
            }}
            QToolButton#OverlayLanguageButton:hover,
            QToolButton#OverlayCopyButton:hover,
            QToolButton#OverlayMenuButton:hover {{
                color: {header_text};
                background-color: {palette['hover']};
                border: 1px solid {palette['accent']};
            }}
            QToolButton#OverlayCopyButton:disabled {{
                color: {header_muted_text};
            }}
            """
        )

    def _apply_content_style(self, palette: dict[str, str]) -> None:
        """Apply content alpha as colors so animations do not nest painters."""

        fade = self._content_fade_opacity
        content_background = self._rgba_with_opacity(
            palette["label_background"],
            self._background_opacity * fade,
            multiply_existing_alpha=True,
        )
        content_text = self._rgba_with_opacity(
            palette["text"],
            self._text_opacity * fade,
        )
        source_text = self._rgba_with_opacity(
            palette["muted_text"],
            self._text_opacity * fade,
        )
        self._source_label.setStyleSheet(
            f"""
            QLabel#OverlaySourceLabel {{
                color: {source_text};
                background-color: transparent;
                border: none;
                padding: 0px 4px;
            }}
            """
        )
        self._label.setStyleSheet(
            f"""
            QLabel#OverlayTextLabel {{
                color: {content_text};
                background-color: {content_background};
                border: none;
                border-radius: 8px;
                padding: 8px 8px 10px 8px;
            }}
            """
        )

    def _apply_theme(self, theme: str) -> None:
        """Apply the selected palette without changing the configured font."""

        self._theme_name = self._coerce_theme(theme)
        palette = OVERLAY_THEMES[self._theme_name]
        background_color = self._rgba_with_opacity(
            palette["label_background"],
            self._background_opacity,
            multiply_existing_alpha=True,
        )
        self.setStyleSheet(
            f"""
            QWidget#OverlayWindow {{
                background-color: {background_color};
                border: 1px solid {palette['border']};
                border-radius: 12px;
            }}
            QWidget#OverlayContent {{
                background-color: transparent;
                border: none;
            }}
            """
        )
        self._apply_header_style(palette)
        self._apply_content_style(palette)
        self._copy_button.setIcon(
            symbol_icon(
                "✓" if self._copy_feedback_active else "▣",
                palette["accent"] if self._copy_feedback_active else palette["text"],
                size=22,
            )
        )
        self._menu_button.setIcon(symbol_icon("⋯", palette["text"], size=24))
        self._shadow_effect.setColor(QColor(palette["shadow"]))
        self._context_menu.apply_theme(self._theme_name)

    def _update_header_layout(self) -> None:
        """Keep the language control within the left quarter of the header."""

        available_width = self._header.contentsRect().width()
        if available_width <= 0:
            available_width = max(1, self.width() - 20)
        language_width = max(1, int(available_width * 0.25))
        self._language_button.setMaximumWidth(language_width)
        self._language_button.setText(
            language_display_name(
                self._source_language,
                self._target_language,
                compact=language_width < 88,
            )
        )

    def _update_language_button(self) -> None:
        self._update_header_layout()

    def set_languages(
        self,
        source_language: object = DEFAULT_SOURCE_LANGUAGE,
        target_language: object = DEFAULT_TARGET_LANGUAGE,
    ) -> tuple[str, str]:
        """Update the language direction shown by the Overlay header."""

        self._source_language = normalize_language_code(source_language)
        self._target_language = (
            str(target_language).strip() or DEFAULT_TARGET_LANGUAGE
        )
        self._update_language_button()
        self._sync_context_menu_state()
        return self._source_language, self._target_language

    def set_source_language(self, source_language: object) -> str:
        """Apply one of the preset source languages."""

        return self.set_languages(source_language, self._target_language)[0]

    def set_original_visible(self, visible: bool) -> bool:
        """Show or hide the optional source-text row and resize the card."""

        previous_size = QSize(self.size())
        self._original_visible = bool(visible)
        self._source_label.setVisible(
            self._original_visible and bool(self._source_text)
        )
        self._resize_to_content(
            animate=True,
            start_size=previous_size,
        )
        self._sync_context_menu_state()
        return self._original_visible

    def _stop_show_animation(self) -> None:
        animation = self._show_animation
        if animation is None:
            return
        animation.stop()
        self._show_animation = None

    def _stop_content_animation(self, *, reset: bool = False) -> None:
        animation = self._content_animation
        if animation is not None:
            animation.stop()
            self._content_animation = None
        if reset:
            self.contentFadeOpacity = 1.0

    def _stop_header_animation(self) -> None:
        animation = self._header_animation
        if animation is None:
            return
        animation.stop()
        self._header_animation = None

    def _stop_resize_animation(self) -> None:
        animation = self._resize_animation
        if animation is None:
            return
        animation.stop()
        self._resize_animation = None

    def _stop_loading(self) -> None:
        self._loading_active = False
        self._loading_phase = 0
        self._loading_timer.stop()

    def _advance_loading(self) -> None:
        """Advance the lightweight animated loading indicator."""

        if not self._loading_active:
            return
        dot_states = ("", " ·", " · ·", " · · ·")
        self._label.setText(
            f"翻译中{dot_states[self._loading_phase % len(dot_states)]}"
        )
        self._loading_phase += 1

    def _animate_content(self) -> None:
        """Fade newly arrived content in without blocking the GUI thread."""

        if not self.isVisible():
            self.contentFadeOpacity = 1.0
            return
        self._stop_content_animation(reset=True)
        animation = QPropertyAnimation(
            self,
            b"contentFadeOpacity",
            self,
        )
        animation.setDuration(CONTENT_ANIMATION_MILLISECONDS)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(
            lambda current=animation: self._finish_content_animation(current)
        )
        self._content_animation = animation
        animation.start()

    def _finish_content_animation(self, animation: QPropertyAnimation) -> None:
        if self._content_animation is not animation:
            return
        self.contentFadeOpacity = 1.0
        self._content_animation = None

    def _resize_to_content(
        self,
        *,
        animate: bool = False,
        start_size: QSize | None = None,
    ) -> None:
        """Resize immediately or reveal the new card height over 200ms."""

        original_size = QSize(start_size) if start_size is not None else QSize(self.size())
        self._content_layout.activate()
        self._layout.activate()
        self._source_label.adjustSize()
        self._label.adjustSize()
        self.adjustSize()
        target_size = QSize(self.size())
        if (
            animate
            and self.isVisible()
            and original_size.isValid()
            and original_size != target_size
        ):
            self._stop_resize_animation()
            self.resize(original_size)
            animation = QPropertyAnimation(self, b"size", self)
            animation.setDuration(RESIZE_ANIMATION_MILLISECONDS)
            animation.setStartValue(original_size)
            animation.setEndValue(target_size)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.finished.connect(
                lambda current=animation: self._finish_resize_animation(current)
            )
            self._resize_animation = animation
            animation.start()
        else:
            self._stop_resize_animation()
        self._clamp_current_position()

    def _finish_resize_animation(self, animation: QPropertyAnimation) -> None:
        if self._resize_animation is not animation:
            return
        self._resize_animation = None
        self._clamp_current_position()

    def _emit_copy_translation(self) -> None:
        """Emit the header copy intent without exposing text to the UI layer."""

        self.context_action.emit("copy_translation", None)

    def show_copy_feedback(self) -> bool:
        """Show a short check-mark acknowledgement after a successful copy."""

        if not self._translation_text:
            return False
        palette = OVERLAY_THEMES[self._theme_name]
        self._copy_feedback_active = True
        self._copy_button.setIcon(
            symbol_icon("✓", palette["accent"], size=22)
        )
        self._copy_button.setToolTip("已复制")
        self._copy_feedback_timer.start(COPY_FEEDBACK_MILLISECONDS)
        return True

    def _restore_copy_button(self) -> None:
        self._copy_feedback_active = False
        palette = OVERLAY_THEMES[self._theme_name]
        self._copy_button.setIcon(symbol_icon("▣", palette["text"], size=22))
        self._copy_button.setToolTip("复制译文")

    def _open_overflow_menu(self) -> None:
        """Open the existing semantic menu below the header controls."""

        self.open_context_menu(
            self._menu_button.mapToGlobal(
                QPoint(0, self._menu_button.height()),
            )
        )

    def set_theme(self, theme: str) -> str:
        """Apply and return a safe theme identifier."""

        self._apply_theme(theme)
        self._sync_context_menu_state()
        return self._theme_name

    def set_always_on_top(self, enabled: bool) -> bool:
        """Toggle topmost presentation while preserving no-activate behavior."""

        was_visible = self.isVisible()
        previous_position = QPoint(self.pos())
        previous_opacity = self.windowOpacity()
        self._always_on_top = bool(enabled)
        # QWidget may hide a top-level window when a native window flag is
        # changed. Capture visibility before changing it and explicitly
        # restore the presentation state afterwards; otherwise clicking the
        # context-menu action makes the Overlay appear to disappear.
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._always_on_top)
        if was_visible:
            self.move(previous_position)
            self.show()
            self.raise_()
            if self._show_animation is None:
                self.setWindowOpacity(previous_opacity)
        self._win32_adapter.set_topmost(self, enabled=self._always_on_top)
        if was_visible:
            # Qt can finish recreating/reordering the native window after the
            # synchronous call above. Reassert the final z-order once the
            # event queue has processed the flag change.
            QTimer.singleShot(0, self._reassert_topmost)
        self._sync_context_menu_state()
        return self._always_on_top

    def _reassert_topmost(self) -> None:
        """Apply the final native z-order after Qt completes a flag update."""

        if not self.isVisible():
            return
        self._win32_adapter.set_topmost(
            self,
            enabled=self._always_on_top,
        )

    @property
    def is_locked(self) -> bool:
        """Whether the overlay is currently locked and click-through."""

        return self._is_locked

    @property
    def position_manager(self) -> PositionManager:
        """Return the component responsible for all placement calculations."""

        return self._position_manager

    @property
    def position_mode(self) -> str:
        """Return the active overlay placement mode."""

        return self._position_manager.position_mode

    def set_position_mode(self, mode: str | PositionMode) -> str:
        """Change placement mode and reposition a visible overlay."""

        selected_mode = self._position_manager.set_position_mode(mode)
        if self.isVisible():
            self._position_for_mode()
        return selected_mode

    def set_custom_position(self, position: QPoint | Sequence[int]) -> QPoint:
        """Remember a fixed position and apply it when that mode is active."""

        custom_position = self._position_manager.set_custom_position(position)
        if (
            self.isVisible()
            and self.position_mode == PositionMode.CUSTOM_FIXED_POSITION.value
        ):
            self._position_for_mode()
        return custom_position

    def _set_content(
        self,
        source_text: object | None,
        translated_text: object | None,
        source_language: object,
        target_language: object,
        *,
        animate: bool = False,
    ) -> None:
        previous_translation = self._translation_text
        self._stop_loading()
        self._source_text = "" if source_text is None else str(source_text)
        self._translation_text = (
            "" if translated_text is None else str(translated_text)
        )
        self._source_language = normalize_language_code(source_language)
        self._target_language = (
            str(target_language).strip() or DEFAULT_TARGET_LANGUAGE
        )
        self._source_label.setText(self._source_text)
        self._label.setText(self._translation_text)
        self._source_label.setVisible(
            self._original_visible and bool(self._source_text)
        )
        self._copy_button.setEnabled(bool(self._translation_text))
        self._update_language_button()
        self._resize_to_content()
        if animate and self.isVisible() and previous_translation != self._translation_text:
            self._animate_content()
        else:
            self._stop_content_animation(reset=True)

    def _set_text(self, text: object | None, *, animate: bool = False) -> None:
        self._set_content(
            "",
            text,
            self._source_language,
            self._target_language,
            animate=animate,
        )

    def show_text(self, text: object | None) -> None:
        """Update the text, resize to fit it, and show the overlay."""

        self._set_text(text, animate=self.isVisible())
        self.show_overlay()

    def show_loading(
        self,
        source_text: object | None,
        source_language: object = DEFAULT_SOURCE_LANGUAGE,
        target_language: object = DEFAULT_TARGET_LANGUAGE,
    ) -> None:
        """Show a compact animated loading state while a provider is running."""

        was_visible = self.isVisible()
        self._set_content(
            source_text,
            "翻译中",
            source_language,
            target_language,
            animate=was_visible,
        )
        self._loading_active = True
        self._loading_phase = 0
        self._loading_timer.start()
        self.show_overlay()

    def show_translation(
        self,
        source_text: object | None,
        translated_text: object | None,
        source_language: object = DEFAULT_SOURCE_LANGUAGE,
        target_language: object = DEFAULT_TARGET_LANGUAGE,
    ) -> None:
        """Display a translation result with optional source-text context."""

        was_visible = self.isVisible()
        self._set_content(
            source_text,
            translated_text,
            source_language,
            target_language,
            animate=was_visible,
        )
        self.show_overlay()

    def show_overlay(self) -> None:
        """Show the overlay without explicitly activating it."""

        self._position_for_mode()
        was_visible = self.isVisible()
        self.show()
        self.raise_()
        self._win32_adapter.set_topmost(self, enabled=self._always_on_top)
        if was_visible:
            self.setWindowOpacity(1.0)
            return

        target_position = QPoint(self.pos())
        self._stop_show_animation()
        self.move(target_position + QPoint(0, 8))
        self.setWindowOpacity(0.0)
        animation = QParallelAnimationGroup(self)
        fade = QPropertyAnimation(self, b"windowOpacity", animation)
        fade.setDuration(SHOW_ANIMATION_MILLISECONDS)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        slide = QPropertyAnimation(self, b"pos", animation)
        slide.setDuration(SHOW_ANIMATION_MILLISECONDS)
        slide.setStartValue(target_position + QPoint(0, 8))
        slide.setEndValue(target_position)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.addAnimation(fade)
        animation.addAnimation(slide)
        animation.finished.connect(
            lambda current=animation: self._finish_show_animation(current)
        )
        self._show_animation = animation
        animation.start()

    def _finish_show_animation(self, animation: QParallelAnimationGroup) -> None:
        if self._show_animation is not animation:
            return
        self.setWindowOpacity(1.0)
        self._show_animation = None

    def hide_overlay(self) -> None:
        """Hide the overlay window."""

        self._hovered = False
        self._stop_loading()
        self._stop_show_animation()
        self._stop_content_animation(reset=True)
        self._stop_resize_animation()
        self.setWindowOpacity(1.0)
        self.hide()

    def lock_overlay(self) -> bool:
        """Lock the overlay above other windows and make it click-through."""

        if self._is_locked:
            return True

        locked = self._win32_adapter.set_locked(self, locked=True)
        if locked:
            self._dragging = False
            self._is_locked = True
            self._win32_adapter.set_topmost(self, enabled=True)
            self._context_menu.set_lock_checked(True)
        return bool(locked)

    def unlock_overlay(self) -> bool:
        """Unlock the overlay so it can receive mouse input and be dragged."""

        if not self._is_locked:
            return True

        unlocked = self._win32_adapter.set_locked(self, locked=False)
        if unlocked:
            self._is_locked = False
            self._win32_adapter.set_topmost(
                self,
                enabled=self._always_on_top,
            )
            self._context_menu.set_lock_checked(False)
        return bool(unlocked)

    def _sync_context_menu_state(self) -> None:
        self._context_menu.sync_state(
            locked=self._is_locked,
            always_on_top=self._always_on_top,
            background_opacity=self._background_opacity,
            text_opacity=self._text_opacity,
            font_size=self._font_size,
            theme=self._theme_name,
            original_visible=self._original_visible,
            source_language=self._source_language,
            target_language=self._target_language,
        )

    def open_context_menu(self, global_position: QPoint) -> bool:
        """Open the styled menu at a global screen position when interactive."""

        if self._is_locked:
            return False
        if self._context_menu.isVisible():
            return True
        self._sync_context_menu_state()
        self._context_menu.popup(global_position)
        return True

    def _handle_context_action(self, key: str, value: object) -> None:
        """Apply local visual actions, then notify the application controller."""

        if key == "opacity":
            self.apply_style(opacity=float(value))
        elif key == "background_opacity":
            self.apply_style(background_opacity=float(value))
        elif key == "text_opacity":
            self.apply_style(text_opacity=float(value))
        elif key == "show_original":
            value = self.set_original_visible(bool(value))
        elif key == "source_language":
            value = self.set_source_language(value)
        elif key == "font_size":
            self.apply_style(font_size=int(value))
        elif key == "theme":
            self.set_theme(str(value))
        elif key == "always_on_top":
            value = self.set_always_on_top(bool(value))
        elif key == "lock_position":
            requested = bool(value)
            if requested:
                self.lock_overlay()
            else:
                self.unlock_overlay()
            value = self._is_locked
        elif key == "hide":
            self.hide_overlay()
        self._sync_context_menu_state()
        self.context_action.emit(key, value)

    def move_clamped(
        self,
        position: QPoint | Sequence[int],
        *,
        screen: QScreen | None = None,
    ) -> None:
        """Move the window while keeping it within a usable screen area."""

        if isinstance(position, QPoint):
            point = position
        else:
            coordinates = list(position)
            if len(coordinates) != 2:
                raise ValueError("position must contain exactly two coordinates")
            point = QPoint(int(coordinates[0]), int(coordinates[1]))

        self._preferred_screen = screen
        self.move(
            self._position_manager.clamp_position(
                point,
                self.size(),
                screen=screen,
            )
        )

    def center_on_screen(self, screen: QScreen | None = None) -> None:
        """Place the overlay in the center of a screen safely."""

        self._position_manager.set_position_mode(PositionMode.DESKTOP_LYRICS_CENTER)
        self._preferred_screen = screen
        self.move(
            self._position_manager.centered_position(
                self.size(),
                screen=screen,
            )
        )

    def _clamp_current_position(self) -> None:
        self.move(
            self._position_manager.clamp_position(
                self.pos(),
                self.size(),
                screen=self._preferred_screen,
            )
        )

    def _position_for_mode(self) -> None:
        """Apply the configured placement mode to the current window size."""

        preferred_screen = self._preferred_screen
        if self.position_mode == PositionMode.MOUSE_FOLLOW.value:
            # Mouse-follow must resolve the screen from the current cursor,
            # even after a previous manual drag remembered another monitor.
            preferred_screen = None
        self.move(
            self._position_manager.position_for(
                self.size(),
                screen=preferred_screen,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        super().resizeEvent(event)
        if hasattr(self, "_language_button"):
            self._update_header_layout()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override name
        """Forward blank-header mouse events to the draggable top-level window."""

        if watched is self._header:
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonPress:
                self.mousePressEvent(event)
                return True
            if event_type == QEvent.Type.MouseMove:
                self.mouseMoveEvent(event)
                return True
            if event_type == QEvent.Type.MouseButtonRelease:
                self.mouseReleaseEvent(event)
                return True
        return super().eventFilter(watched, event)

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override name
        super().enterEvent(event)
        self._hovered = True
        palette = OVERLAY_THEMES[self._theme_name]
        glow = QColor(palette["accent"])
        glow.setAlpha(105)
        self._shadow_effect.setColor(glow)
        self._shadow_effect.setBlurRadius(22)
        self._animate_header_opacity(1.0)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override name
        super().leaveEvent(event)
        self._hovered = False
        self._shadow_effect.setColor(QColor(OVERLAY_THEMES[self._theme_name]["shadow"]))
        self._shadow_effect.setBlurRadius(14)
        self._animate_header_opacity(0.82)

    def _animate_header_opacity(self, target: float) -> None:
        """Animate the toolbar emphasis on hover without changing text size."""

        self._stop_header_animation()
        if abs(self._header_emphasis - target) < 0.01:
            self.headerEmphasis = target
            return
        animation = QPropertyAnimation(
            self,
            b"headerEmphasis",
            self,
        )
        animation.setDuration(HOVER_ANIMATION_MILLISECONDS)
        animation.setStartValue(self._header_emphasis)
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        animation.finished.connect(
            lambda current=animation: self._finish_header_animation(current)
        )
        self._header_animation = animation
        animation.start()

    def _finish_header_animation(self, animation: QPropertyAnimation) -> None:
        if self._header_animation is animation:
            self._header_animation = None

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if self._is_locked:
            event.ignore()
            return

        if event.button() == Qt.MouseButton.RightButton:
            self.open_context_menu(event.globalPosition().toPoint())
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if self._is_locked:
            event.ignore()
            return

        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            global_position = event.globalPosition().toPoint()
            screen = QGuiApplication.screenAt(global_position)
            self.move_clamped(global_position - self._drag_offset, screen=screen)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._dragging
            self._dragging = False
            if was_dragging:
                self._position_manager.remember_manual_position(self.pos())
                self._position_manager.set_position_mode(
                    PositionMode.CUSTOM_FIXED_POSITION,
                )
                # The global mouse listener can observe the same release a
                # few milliseconds before or after Qt. Keep a drag release
                # from leaving the visible result hidden by a competing
                # selection callback.
                if not self.isVisible():
                    self.show_overlay()
                else:
                    self.raise_()
                    self._win32_adapter.set_topmost(
                        self,
                        enabled=self._always_on_top,
                    )
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt override name
        if self._is_locked:
            event.ignore()
            return
        self.open_context_menu(event.globalPos())
        event.accept()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        self._stop_loading()
        self._stop_show_animation()
        self._stop_content_animation(reset=True)
        self._stop_header_animation()
        self._stop_resize_animation()
        self._copy_feedback_timer.stop()
        if self._is_locked:
            self._win32_adapter.set_locked(self, locked=False)
            self._is_locked = False
            self._dragging = False
            self._context_menu.set_lock_checked(False)
        super().closeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override name
        super().showEvent(event)
        self._clamp_current_position()
        self._win32_adapter.set_topmost(self, enabled=self._always_on_top)
        QTimer.singleShot(0, self._reassert_topmost)


__all__ = [
    "DEFAULT_FONT_FAMILY",
    "DEFAULT_FONT_SIZE",
    "DEFAULT_MAX_WIDTH",
    "DEFAULT_MIN_HEIGHT",
    "DEFAULT_MIN_WIDTH",
    "DEFAULT_OPACITY",
    "DEFAULT_TEST_TEXT",
    "DEFAULT_THEME",
    "OverlayWindow",
]
