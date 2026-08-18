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
    QAbstractScrollArea,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
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

DEFAULT_TEST_TEXT = "Overlay test / æ‚¬æµ®ç¿»è¯‘æµ‹è¯•"
DEFAULT_MAX_WIDTH = 900
DEFAULT_MIN_WIDTH = 240
DEFAULT_MIN_HEIGHT = 56
DEFAULT_FONT_FAMILY = "Segoe UI"
DEFAULT_FONT_SIZE = 24
DEFAULT_MAX_HEIGHT = 520
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


class OverlayScrollArea(QScrollArea):
    """Scroll area whose compact size follows the current content naturally."""

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override name
        widget = self.widget()
        if widget is None:
            return super().sizeHint()
        content_hint = widget.sizeHint()
        frame = self.frameWidth() * 2
        size = QSize(
            max(0, content_hint.width() + frame),
            max(0, content_hint.height() + frame),
        )
        owner = self.parentWidget()
        owner_layout = owner.layout() if owner is not None else None
        if owner is not None and owner_layout is not None:
            margins = owner_layout.contentsMargins()
            maximum_width = max(
                1,
                owner.maximumWidth() - margins.left() - margins.right(),
            )
            header = getattr(owner, "_header", None)
            header_height = header.sizeHint().height() if header is not None else 0
            maximum_height = max(
                1,
                owner.maximumHeight()
                - margins.top()
                - margins.bottom()
                - header_height
                - owner_layout.spacing(),
            )
            size.setWidth(min(size.width(), maximum_width))
            size.setHeight(min(size.height(), maximum_height))
        return size


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
        max_height: int = DEFAULT_MAX_HEIGHT,
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
            max_height = getattr(config_manager, "overlay_max_height", max_height)
        self._max_width = self._coerce_max_width(max_width)
        self._max_height = self._coerce_max_height(max_height)
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
        self._set_window_size_limits()

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
        self._language_button.setToolTip("é€‰æ‹©æºè¯­è¨€")
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
        self._copy_button.setToolTip("å¤åˆ¶è¯‘æ–‡")
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
        self._menu_button.setToolTip("æ›´å¤šæ“ä½œ")
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

        self._content_scroll = OverlayScrollArea(self)
        self._content_scroll.setObjectName("OverlayContentScroll")
        self._content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content_scroll.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._content_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._content_scroll.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        self._content_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._content_scroll.setMouseTracking(True)
        self._content_scroll.viewport().setMouseTracking(True)
        self._content_scroll.viewport().installEventFilter(self)

        self._content = QWidget()
        self._content.setObjectName("OverlayContent")
        self._content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
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
        # Both text rows must occupy the same content column.  Keeping the
        # source row at QLabel's default ``Preferred`` width lets a later
        # layout pass (for example after a modal About dialog closes) shrink
        # it to its own size hint while the translation row keeps the card
        # width.  An expanding policy makes the source background and its
        # wrapping follow the translation card reliably.
        self._source_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._source_label.setMaximumWidth(self._max_width)
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
            QSizePolicy.Policy.Expanding,
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
        self._label.×MûöÚ$z{-®éÜj×Âæ–ÖFS×6VÆbæ—5f—6–&ÆR‚’¢6VÆbç6†÷uö÷fW&Æ’‚ ¢FVb6†÷uöÆöF–ær€¢6VÆbÀ¢6÷W&6U÷FW‡C¢ö&¦V7BÂæöæRÀ¢6÷W&6UöÆæwVvS¢ö&¦V7BÒDTdTÅEõ4õU$4UôÄäuTtRÀ¢F&vWEöÆæwVvS¢ö&¦V7BÒDTdTÅEõD$tUEôÄäuTtRÀ¢’ÓâæöæS ¢""%6†÷r6ö×7Bæ–ÖFVBÆöF–ær7FFRv†–ÆR&÷f–FW"—2'Vææ–ærâ""  ¢v5÷f—6–&ÆRÒ6VÆbæ—5f—6–&ÆR‚¢6VÆbå÷6WEö6öçFVçB€¢6÷W&6U÷FW‡BÀ¢.{û¾ŠùKŠÒ"À¢6÷W&6UöÆæwVvRÀ¢F&vWEöÆæwVvRÀ¢æ–ÖFS×v5÷f—6–&ÆRÀ¢¢6VÆbåöÆöF–æuö7F—fRÒG'VP¢6VÆbåöÆöF–æu÷†6RÒ ¢6VÆbåöÆöF–æu÷F–ÖW"ç7F'B‚¢6VÆbç6†÷uö÷fW&Æ’‚ ¢FVb6†÷u÷G&ç6ÆF–öâ€¢6VÆbÀ¢6÷W&6U÷FW‡C¢ö&¦V7BÂæöæRÀ¢G&ç6ÆFVE÷FW‡C¢ö&¦V7BÂæöæRÀ¢6÷W&6UöÆæwVvS¢ö&¦V7BÒDTdTÅEõ4õU$4UôÄäuTtRÀ¢F&vWEöÆæwVvS¢ö&¦V7BÒDTdTÅEõD$tUEôÄäuTtRÀ¢’ÓâæöæS ¢""$F—7Æ’G&ç6ÆF–öâ&W7VÇBv—F‚÷F–öæÂ6÷W&6R×FW‡B6öçFW‡Bâ""  ¢v5÷f—6–&ÆRÒ6VÆbæ—5f—6–&ÆR‚¢6VÆbå÷6WEö6öçFVçB€¢6÷W&6U÷FW‡BÀ¢G&ç6ÆFVE÷FW‡BÀ¢6÷W&6UöÆæwVvRÀ¢F&vWEöÆæwVvRÀ¢æ–ÖFS×v5÷f—6–&ÆRÀ¢¢6VÆbç6†÷uö÷fW&Æ’‚ ¢FVb6†÷uö÷fW&Æ’‡6VÆb’ÓâæöæS ¢""%6†÷rF†R÷fW&Æ’v—F†÷WBW‡Æ–6—FÇ’7F—fF–ær—Bâ""  ¢6VÆbå÷÷6—F–öåöf÷%öÖöFR‚¢v5÷f—6–&ÆRÒ6VÆbæ—5f—6–&ÆR‚¢6VÆbç6†÷r‚¢6VÆbç&—6Uò‚¢6VÆbå÷v–ã3%öFFW"ç6WE÷F÷Ö÷7B‡6VÆbÂVæ&ÆVC×6VÆbåöÇv—5ööå÷F÷¢–bv5÷f—6–&ÆS ¢6VÆbç6WEv–æF÷t÷6—G’ƒã¢&WGW&à ¢F&vWE÷÷6—F–öâÒö–çB‡6VÆbç÷2‚’¢6VÆbå÷7F÷÷6†÷uöæ–ÖF–öâ‚¢6VÆbæÖ÷fR‡F&vWE÷÷6—F–öâ²ö–çBƒÂ‚’¢6VÆbç6WEv–æF÷t÷6—G’ƒã¢æ–ÖF–öâÒ&ÆÆVÄæ–ÖF–öäw&÷W‡6VÆb¢fFRÒ&÷W'G”æ–ÖF–öâ‡6VÆbÂ"'v–æF÷t÷6—G’"Âæ–ÖF–öâ¢fFRç6WDGW&F–öâ…4„õuôä”ÔD”ôåôÔ”ÄÄ•4T4ôäE2¢fFRç6WE7F'EfÇVRƒã¢fFRç6WDVæEfÇVRƒã¢fFRç6WDV6–æt7W'fR…V6–æt7W'fRåG—Rä÷WD7V&–2¢6Æ–FRÒ&÷W'G”æ–ÖF–öâ‡6VÆbÂ"'÷2"Âæ–ÖF–öâ¢6Æ–FRç6WDGW&F–öâ…4„õuôä”ÔD”ôåôÔ”ÄÄ•4T4ôäE2¢6Æ–FRç6WE7F'EfÇVR‡F&vWE÷÷6—F–öâ²ö–çBƒÂ‚’¢6Æ–FRç6WDVæEfÇVR‡F&vWE÷÷6—F–öâ¢6Æ–FRç6WDV6–æt7W'fR…V6–æt7W'fRåG—Rä÷WD7V&–2¢æ–ÖF–öâæFDæ–ÖF–öâ†fFR¢æ–ÖF–öâæFDæ–ÖF–öâ‡6Æ–FR¢æ–ÖF–öâæf–æ—6†VBæ6öææV7B€¢ÆÖ&F7W'&VçCÖæ–ÖF–öã¢6VÆbåöf–æ—6…÷6†÷uöæ–ÖF–öâ†7W'&VçB¢¢6VÆbå÷6†÷uöæ–ÖF–öâÒæ–ÖF–öà¢æ–ÖF–öâç7F'B‚ ¢FVböf–æ—6…÷6†÷uöæ–ÖF–öâ‡6VÆbÂæ–ÖF–öã¢&ÆÆVÄæ–ÖF–öäw&÷W’ÓâæöæS ¢–b6VÆbå÷6†÷uöæ–ÖF–öâ—2æ÷Bæ–ÖF–öã ¢&WGW&à¢6VÆbç6WEv–æF÷t÷6—G’ƒã¢6VÆbå÷6†÷uöæ–ÖF–öâÒæöæP ¢FVb†–FUö÷fW&Æ’‡6VÆb’ÓâæöæS ¢""$†–FRF†R÷fW&Æ’v–æF÷râ""  ¢6VÆbåö†÷fW&VBÒfÇ6P¢6VÆbå÷7F÷öÆöF–ær‚¢6VÆbå÷7F÷÷6†÷uöæ–ÖF–öâ‚¢6VÆbå÷7F÷ö6öçFVçEöæ–ÖF–öâ‡&W6WCÕG'VR¢6VÆbå÷7F÷÷&W6—¦Uöæ–ÖF–öâ‚¢6VÆbç6WEv–æF÷t÷6—G’ƒã¢6VÆbæ†–FR‚ ¢FVbÆö6µö÷fW&Æ’‡6VÆb’Óâ&ööÃ ¢""$Æö6²F†R÷fW&Æ’&÷fR÷F†W"v–æF÷w2æBÖ¶R—B6Æ–6²×F‡&÷Vv‚â""  ¢–b6VÆbåö—5öÆö6¶VC ¢&WGW&âG'VP ¢Æö6¶VBÒ6VÆbå÷v–ã3%öFFW"ç6WEöÆö6¶VB‡6VÆbÂÆö6¶VCÕG'VR¢–bÆö6¶VC ¢6VÆbåöG&vv–ærÒfÇ6P¢6VÆbåö—5öÆö6¶VBÒG'VP¢6VÆbå÷v–ã3%öFFW"ç6WE÷F÷Ö÷7B‡6VÆbÂVæ&ÆVCÕG'VR¢6VÆbåö6öçFW‡EöÖVçRç6WEöÆö6µö6†V6¶VB…G'VR¢&WGW&â&ööÂ†Æö6¶VB ¢FVbVæÆö6µö÷fW&Æ’‡6VÆb’Óâ&ööÃ ¢""%VæÆö6²F†R÷fW&Æ’6ò—B6â&V6V—fRÖ÷W6R–çWBæB&RG&vvVBâ""  ¢–bæ÷B6VÆbåö—5öÆö6¶VC ¢&WGW&âG'VP ¢VæÆö6¶VBÒ6VÆbå÷v–ã3%öFFW"ç6WEöÆö6¶VB‡6VÆbÂÆö6¶VCÔfÇ6R¢–bVæÆö6¶VC ¢6VÆbåö—5öÆö6¶VBÒfÇ6P¢6VÆbå÷v–ã3%öFFW"ç6WE÷F÷Ö÷7B€¢6VÆbÀ¢Væ&ÆVC×6VÆbåöÇv—5ööå÷F÷À¢¢6VÆbåö6öçFW‡EöÖVçRç6WEöÆö6µö6†V6¶VB„fÇ6R¢&WGW&â&ööÂ‡VæÆö6¶VB ¢FVb÷7–æ5ö6öçFW‡EöÖVçU÷7FFR‡6VÆb’ÓâæöæS ¢6VÆbåö6öçFW‡EöÖVçRç7–æ5÷7FFR€¢Æö6¶VC×6VÆbåö—5öÆö6¶VBÀ¢Çv—5ööå÷F÷×6VÆbåöÇv—5ööå÷F÷À¢&6¶w&÷VæEö÷6—G“×6VÆbåö&6¶w&÷VæEö÷6—G’À¢FW‡Eö÷6—G“×6VÆbå÷FW‡Eö÷6—G’À¢föçE÷6—¦S×6VÆbåöföçE÷6—¦RÀ¢F†VÖS×6VÆbå÷F†VÖUöæÖRÀ¢÷&–v–æÅ÷f—6–&ÆS×6VÆbåö÷&–v–æÅ÷f—6–&ÆRÀ¢6÷W&6UöÆæwVvS×6VÆbå÷6÷W&6UöÆæwVvRÀ¢F&vWEöÆæwVvS×6VÆbå÷F&vWEöÆæwVvRÀ¢ ¢FVb÷Våö6öçFW‡EöÖVçR‡6VÆbÂvÆö&Å÷÷6—F–öã¢ö–çB’Óâ&ööÃ ¢""$÷VâF†R7G–ÆVBÖVçRBvÆö&Â67&VVâ÷6—F–öâv†Vâ–çFW&7F—fRâ""  ¢–b6VÆbåö—5öÆö6¶VC ¢&WGW&âfÇ6P¢–b6VÆbåö6öçFW‡EöÖVçRæ—5f—6–&ÆR‚“ ¢&WGW&âG'VP¢6VÆbå÷7–æ5ö6öçFW‡EöÖVçU÷7FFR‚¢6VÆbåö6öçFW‡EöÖVçRç÷W†vÆö&Å÷÷6—F–öâ¢&WGW&âG'VP ¢FVbö†æFÆUö6öçFW‡Eö7F–öâ‡6VÆbÂ¶W“¢7G"ÂfÇVS¢ö&¦V7B’ÓâæöæS ¢""$Ç’Æö6Âf—7VÂ7F–öç2ÂF†Vâæ÷F–g’F†RÆ–6F–öâ6öçG&öÆÆW"â""  ¢–b¶W’ÓÒ&÷6—G’# ¢6VÆbæÇ•÷7G–ÆR†÷6—G“ÖfÆöB‡fÇVR’¢VÆ–b¶W’ÓÒ&&6¶w&÷VæEö÷6—G’# ¢6VÆbæÇ•÷7G–ÆR†&6¶w&÷VæEö÷6—G“ÖfÆöB‡fÇVR’¢VÆ–b¶W’ÓÒ'FW‡Eö÷6—G’# ¢6VÆbæÇ•÷7G–ÆR‡FW‡Eö÷6—G“ÖfÆöB‡fÇVR’¢VÆ–b¶W’ÓÒ'6†÷uö÷&–v–æÂ# ¢fÇVRÒ6VÆbç6WEö÷&–v–æÅ÷f—6–&ÆR†&ööÂ‡fÇVR’¢VÆ–b¶W’ÓÒ'6÷W&6UöÆæwVvR# ¢fÇVRÒ6VÆbç6WE÷6÷W&6UöÆæwVvR‡fÇVR¢VÆ–b¶W’ÓÒ&föçE÷6—¦R# ¢6VÆbæÇ•÷7G–ÆR†föçE÷6—¦SÖ–çB‡fÇVR’¢VÆ–b¶W’ÓÒ'F†VÖR# ¢6VÆbç6WE÷F†VÖR‡7G"‡fÇVR’¢VÆ–b¶W’ÓÒ&Çv—5ööå÷F÷# ¢fÇVRÒ6VÆbç6WEöÇv—5ööå÷F÷†&ööÂ‡fÇVR’¢VÆ–b¶W’ÓÒ&Æö6µ÷÷6—F–öâ# ¢&WVW7FVBÒ&ööÂ‡fÇVR¢–b&WVW7FVC ¢6VÆbæÆö6µö÷fW&Æ’‚¢VÇ6S ¢6VÆbçVæÆö6µö÷fW&Æ’‚¢fÇVRÒ6VÆbåö—5öÆö6¶V@¢VÆ–b¶W’ÓÒ&†–FR# ¢6VÆbæ†–FUö÷fW&Æ’‚¢6VÆbå÷7–æ5ö6öçFW‡EöÖVçU÷7FFR‚¢6VÆbæ6öçFW‡Eö7F–öâæVÖ—B†¶W’ÂfÇVR ¢FVbÖ÷fUö6Æ×VB€¢6VÆbÀ¢÷6—F–öã¢ö–çBÂ6WVVæ6U¶–çEÒÀ¢¢À¢67&VVã¢67&VVâÂæöæRÒæöæRÀ¢’ÓâæöæS ¢""$Ö÷fRF†Rv–æF÷rv†–ÆR¶VW–ær—Bv—F†–âW6&ÆR67&VVâ&Vâ""  ¢–b—6–ç7Fæ6R‡÷6—F–öâÂö–çB“ ¢ö–çBÒ÷6—F–öà¢VÇ6S ¢6ö÷&F–æFW2ÒÆ—7B‡÷6—F–öâ¢–bÆVâ†6ö÷&F–æFW2’Ò# ¢&—6RfÇVTW'&÷"‚'÷6—F–öâ×W7B6öçF–âW†7FÇ’Gvò6ö÷&F–æFW2"¢ö–çBÒö–çB†–çB†6ö÷&F–æFW5³Ò’Â–çB†6ö÷&F–æFW5³Ò’ ¢6VÆbå÷&VfW'&VE÷67&VVâÒ67&VVà¢6VÆbæÖ÷fR€¢6VÆbå÷÷6—F–öåöÖævW"æ6Æ×÷÷6—F–öâ€¢ö–çBÀ¢6VÆbç6—¦R‚’À¢67&VVã×67&VVâÀ¢¢ ¢FVb6VçFW%ööå÷67&VVâ‡6VÆbÂ67&VVã¢67&VVâÂæöæRÒæöæR’ÓâæöæS ¢""%Æ6RF†R÷fW&Æ’–âF†R6VçFW"öb67&VVâ6fVÇ’â""  ¢6VÆbå÷÷6—F–öåöÖævW"ç6WE÷÷6—F–öåöÖöFR…÷6—F–öäÖöFRäDU4µDõôÅ•$”55ô4TåDU"¢6VÆbå÷&VfW'&VE÷67&VVâÒ67&VVà¢6VÆbæÖ÷fR€¢6VÆbå÷÷6—F–öåöÖævW"æ6VçFW&VE÷÷6—F–öâ€¢6VÆbç6—¦R‚’À¢67&VVã×67&VVâÀ¢¢ ¢FVbö6Æ×ö7W'&VçE÷÷6—F–öâ‡6VÆb’ÓâæöæS ¢6VÆbæÖ÷fR€¢6VÆbå÷÷6—F–öåöÖævW"æ6Æ×÷÷6—F–öâ€¢6VÆbç÷2‚’À¢6VÆbç6—¦R‚’À¢67&VVã×6VÆbå÷&VfW'&VE÷67&VVâÀ¢¢ ¢FVb÷÷6—F–öåöf÷%öÖöFR‡6VÆb’ÓâæöæS ¢""$Ç’F†R6öæf–wW&VBÆ6VÖVçBÖöFRFòF†R7W'&VçBv–æF÷r6—¦Râ""  ¢&VfW'&VE÷67&VVâÒ6VÆbå÷&VfW'&VE÷67&VVà¢–b6VÆbç÷6—F–öåöÖöFRÓÒ÷6—F–öäÖöFRäÔõU4UôdôÄÄõrçfÇVS ¢2Ö÷W6RÖföÆÆ÷r×W7B&W6öÇfRF†R67&VVâg&öÒF†R7W'&VçB7W'6÷"À¢2WfVâgFW"&Wf–÷W2ÖçVÂG&r&VÖVÖ&W&VBæ÷F†W"Ööæ—F÷"à¢&VfW'&VE÷67&VVâÒæöæP¢6VÆbæÖ÷fR€¢6VÆbå÷÷6—F–öåöÖævW"ç÷6—F–öåöf÷"€¢6VÆbç6—¦R‚’À¢67&VVã×&VfW'&VE÷67&VVâÀ¢¢ ¢FVb&W6—¦TWfVçB‡6VÆbÂWfVçB’ÓâæöæS¢2æ÷¢ãƒ"ÒB÷fW'&–FRæÖP¢7WW"‚’ç&W6—¦TWfVçB†WfVçB¢–b†6GG"‡6VÆbÂ%öÆæwVvUö'WGFöâ"“ ¢6VÆbå÷WFFUö†VFW%öÆ–÷WB‚ ¢FVbWfVçDf–ÇFW"‡6VÆbÂvF6†VBÂWfVçB’Óâ&ööÃ¢2æ÷¢ãƒ"ÒB÷fW'&–FRæÖP¢""$f÷'v&BG&röÖVçRÖ÷W6RWfVçG2v†–ÆRÆVf–ærv†VVÂWfVçG2FòBâ""  ¢–bvF6†VB—26VÆbåö†VFW# ¢WfVçE÷G—RÒWfVçBçG—R‚¢–bWfVçE÷G—RÓÒWfVçBåG—RäÖ÷W6T'WGFöå&W73 ¢6VÆbæÖ÷W6U&W74WfVçB†WfVçB¢&WGW&âG'VP¢–bWfVçE÷G—RÓÒWfVçBåG—RäÖ÷W6TÖ÷fS ¢6VÆbæÖ÷W6TÖ÷fTWfVçB†WfVçB¢&WGW&âG'VP¢–bWfVçE÷G—RÓÒWfVçBåG—RäÖ÷W6T'WGFöå&VÆV6S ¢6VÆbæÖ÷W6U&VÆV6TWfVçB†WfVçB¢&WGW&âG'VP¢–b€¢†6GG"‡6VÆbÂ%ö6öçFVçE÷67&öÆÂ"¢æBvF6†VB—26VÆbåö6öçFVçE÷67&öÆÂçf–Ww÷'B‚¢“ ¢WfVçE÷G—RÒWfVçBçG—R‚¢–bWfVçE÷G—RÓÒWfVçBåG—RäÖ÷W6T'WGFöå&W73 ¢6VÆbæÖ÷W6U&W74WfVçB†WfVçB¢&WGW&âG'VP¢–bWfVçE÷G—RÓÒWfVçBåG—RäÖ÷W6TÖ÷fS ¢6VÆbæÖ÷W6TÖ÷fTWfVçB†WfVçB¢&WGW&âG'VP¢–bWfVçE÷G—RÓÒWfVçBåG—RäÖ÷W6T'WGFöå&VÆV6S ¢6VÆbæÖ÷W6U&VÆV6TWfVçB†WfVçB¢&WGW&âG'VP¢&WGW&â7WW"‚’æWfVçDf–ÇFW"‡vF6†VBÂWfVçB ¢FVbVçFW$WfVçB‡6VÆbÂWfVçB’ÓâæöæS¢2æ÷¢ãƒ"ÒB÷fW'&–FRæÖP¢7WW"‚’æVçFW$WfVçB†WfVçB¢6VÆbåö†÷fW&VBÒG'VP¢ÆWGFRÒõdU$Ä•õD„TÔU5·6VÆbå÷F†VÖUöæÖUĞ¢vÆ÷rÒ6öÆ÷"‡ÆWGFU²&66VçB%Ò¢vÆ÷rç6WDÇ†ƒR¢6VÆbå÷6†F÷uöVffV7Bç6WD6öÆ÷"†vÆ÷r¢6VÆbå÷6†F÷uöVffV7Bç6WD&ÇW%&F—W2ƒ#"¢6VÆbåöæ–ÖFUö†VFW%ö÷6—G’ƒã ¢FVbÆVfTWfVçB‡6VÆbÂWfVçB’ÓâæöæS¢2æ÷¢ãƒ"ÒB÷fW'&–FRæÖP¢7WW"‚’æÆVfTWfVçB†WfVçB¢6VÆbåö†÷fW&VBÒfÇ6P¢6VÆbå÷6†F÷uöVffV7Bç6WD6öÆ÷"…6öÆ÷"„õdU$Ä•õD„TÔU5·6VÆbå÷F†VÖUöæÖUÕ²'6†F÷r%Ò’¢6VÆbå÷6†F÷uöVffV7Bç6WD&ÇW%&F—W2ƒB¢6VÆbåöæ–ÖFUö†VFW%ö÷6—G’ƒãƒ" ¢FVböæ–ÖFUö†VFW%ö÷6—G’‡6VÆbÂF&vWC¢fÆöB’ÓâæöæS ¢""$æ–ÖFRF†RFööÆ&"V×†6—2öâ†÷fW"v—F†÷WB6†æv–ærFW‡B6—¦Râ""  ¢6VÆbå÷7F÷ö†VFW%öæ–ÖF–öâ‚¢–b'2‡6VÆbåö†VFW%öV×†6—2ÒF&vWB’Âã ¢6VÆbæ†VFW$V×†6—2ÒF&vW@¢&WGW&à¢æ–ÖF–öâÒ&÷W'G”æ–ÖF–öâ€¢6VÆbÀ¢"&†VFW$V×†6—2"À¢6VÆbÀ¢¢æ–ÖF–öâç6WDGW&F–öâ„„õdU%ôä”ÔD”ôåôÔ”ÄÄ•4T4ôäE2¢æ–ÖF–öâç6WE7F'EfÇVR‡6VÆbåö†VFW%öV×†6—2¢æ–ÖF–öâç6WDVæEfÇVR‡F&vWB¢æ–ÖF–öâç6WDV6–æt7W'fR…V6–æt7W'fRåG—Rä–ä÷WD7V&–2¢æ–ÖF–öâæf–æ—6†VBæ6öææV7B€¢ÆÖ&F7W'&VçCÖæ–ÖF–öã¢6VÆbåöf–æ—6…ö†VFW%öæ–ÖF–öâ†7W'&VçB¢¢6VÆbåö†VFW%öæ–ÖF–öâÒæ–ÖF–öà¢æ–ÖF–öâç7F'B‚ ¢FVböf–æ—6…ö†VFW%öæ–ÖF–öâ‡6VÆbÂæ–ÖF–öã¢&÷W'G”æ–ÖF–öâ’ÓâæöæS ¢–b6VÆbåö†VFW%öæ–ÖF–öâ—2æ–ÖF–öã ¢6VÆbåö†VFW%öæ–ÖF–öâÒæöæP ¢FVbÖ÷W6U&W74WfVçB‡6VÆbÂWfVçB’ÓâæöæS¢2æ÷¢ãƒ"ÒB÷fW'&–FRæÖP¢–b6VÆbåö—5öÆö6¶VC ¢WfVçBæ–væ÷&R‚¢&WGW&à ¢–bWfVçBæ'WGFöâ‚’ÓÒBäÖ÷W6T'WGFöâå&–v‡D'WGFöã ¢6VÆbæ÷Våö6öçFW‡EöÖVçR†WfVçBævÆö&Å÷6—F–öâ‚’çFõö–çB‚’¢WfVçBæ66WB‚¢&WGW&à ¢–bWfVçBæ'WGFöâ‚’ÓÒBäÖ÷W6T'WGFöâäÆVgD'WGFöã ¢6VÆbåöG&vv–ærÒG'VP¢6VÆbåöG&uööfg6WBÒ€¢WfVçBævÆö&Å÷6—F–öâ‚’çFõö–çB‚’Ò6VÆbæg&ÖTvVöÖWG'’‚’çF÷ÆVgB‚¢¢WfVçBæ66WB‚¢&WGW&à ¢7WW"‚’æÖ÷W6U&W74WfVçB†WfVçB ¢FVbÖ÷W6TÖ÷fTWfVçB‡6VÆbÂWfVçB’ÓâæöæS¢2æ÷¢ãƒ"ÒB÷fW'&–FRæÖP¢–b6VÆbåö—5öÆö6¶VC ¢WfVçBæ–væ÷&R‚¢&WGW&à ¢–b6VÆbåöG&vv–æræBWfVçBæ'WGFöç2‚’bBäÖ÷W6T'WGFöâäÆVgD'WGFöã ¢vÆö&Å÷÷6—F–öâÒWfVçBævÆö&Å÷6—F–öâ‚’çFõö–çB‚¢67&VVâÒwV”Æ–6F–öâç67&VVäB†vÆö&Å÷÷6—F–öâ¢6VÆbæÖ÷fUö6Æ×VB†vÆö&Å÷÷6—F–öâÒ6VÆbåöG&uööfg6WBÂ67&VVã×67&VVâ¢WfVçBæ66WB‚¢&WGW&à ¢7WW"‚’æÖ÷W6TÖ÷fTWfVçB†WfVçB ¢FVbÖ÷W6U&VÆV6TWfVçB‡6VÆbÂWfVçB’ÓâæöæS¢2æ÷¢ãƒ"ÒB÷fW'&–FRæÖP¢–bWfVçBæ'WGFöâ‚’ÓÒBäÖ÷W6T'WGFöâäÆVgD'WGFöã ¢v5öG&vv–ærÒ6VÆbåöG&vv–æp¢6VÆbåöG&vv–ærÒfÇ6P¢–bv5öG&vv–æs ¢6VÆbå÷÷6—F–öåöÖævW"ç&VÖVÖ&W%öÖçVÅ÷÷6—F–öâ‡6VÆbç÷2‚’¢6VÆbå÷÷6—F–öåöÖævW"ç6WE÷÷6—F–öåöÖöFR€¢÷6—F–öäÖöFRä5U5DôÕôd•„TEõõ4•D”ôâÀ¢¢2F†RvÆö&ÂÖ÷W6RÆ—7FVæW"6âö'6W'fRF†R6ÖR&VÆV6R¢2fWrÖ–ÆÆ—6V6öæG2&Vf÷&R÷"gFW"Bâ¶VWG&r&VÆV6P¢2g&öÒÆVf–ærF†Rf—6–&ÆR&W7VÇB†–FFVâ'’6ö×WF–æp¢26VÆV7F–öâ6ÆÆ&6²à¢–bæ÷B6VÆbæ—5f—6–&ÆR‚“ ¢6VÆbç6†÷uö÷fW&Æ’‚¢VÇ6S ¢6VÆbç&—6Uò‚¢6VÆbå÷v–ã3%öFFW"ç6WE÷F÷Ö÷7B€¢6VÆbÀ¢Væ&ÆVC×6VÆbåöÇv—5ööå÷F÷À¢¢WfVçBæ66WB‚¢&WGW&à ¢7WW"‚’æÖ÷W6U&VÆV6TWfVçB†WfVçB ¢FVb6öçFW‡DÖVçTWfVçB‡6VÆbÂWfVçB’ÓâæöæS¢2æ÷¢ãƒ"ÒB÷fW'&–FRæÖP¢–b6VÆbåö—5öÆö6¶VC ¢WfVçBæ–væ÷&R‚¢&WGW&à¢6VÆbæ÷Våö6öçFW‡EöÖVçR†WfVçBævÆö&Å÷2‚’¢WfVçBæ66WB‚ ¢FVb6Æ÷6TWfVçB‡6VÆbÂWfVçB’ÓâæöæS¢2æ÷¢ãƒ"ÒB÷fW'&–FRæÖP¢6VÆbå÷7F÷öÆöF–ær‚¢6VÆbå÷7F÷÷6†÷uöæ–ÖF–öâ‚¢6VÆbå÷7F÷ö6öçFVçEöæ–ÖF–öâ‡&W6WCÕG'VR¢6VÆbå÷7F÷ö†VFW%öæ–ÖF–öâ‚¢6VÆbå÷7F÷÷&W6—¦Uöæ–ÖF–öâ‚¢6VÆbåö6÷•öfVVF&6µ÷F–ÖW"ç7F÷‚¢–b6VÆbåö—5öÆö6¶VC ¢6VÆbå÷v–ã3%öFFW"ç6WEöÆö6¶VB‡6VÆbÂÆö6¶VCÔfÇ6R¢6VÆbåö—5öÆö6¶VBÒfÇ6P¢6VÆbåöG&vv–ærÒfÇ6P¢6VÆbåö6öçFW‡EöÖVçRç6WEöÆö6µö6†V6¶VB„fÇ6R¢7WW"‚’æ6Æ÷6TWfVçB†WfVçB ¢FVb6†÷tWfVçB‡6VÆbÂWfVçB’ÓâæöæS¢2æ÷¢ãƒ"ÒB÷fW'&–FRæÖP¢7WW"‚’ç6†÷tWfVçB†WfVçB¢6VÆbåö6Æ×ö7W'&VçE÷÷6—F–öâ‚¢6VÆbå÷v–ã3%öFFW"ç6WE÷F÷Ö÷7B‡6VÆbÂVæ&ÆVC×6VÆbåöÇv—5ööå÷F÷¢F–ÖW"ç6–ævÆU6†÷BƒÂ6VÆbå÷&V76W'E÷F÷Ö÷7B  ¥õöÆÅõòÒ°¢$DTdTÅEôdôåEôdÔ”Å’"À¢$DTdTÅEôdôåEõ4•¤R"À¢$DTdTÅEôÔ…ô„T”t…B"À¢$DTdTÅEôÔ…õt”ED‚"À¢$DTdTÅEôÔ”åô„T”t…B"À¢$DTdTÅEôÔ”åõt”ED‚"À¢$DTdTÅEôõ4•E’"À¢$DTdTÅEõDU5EõDU…B"À¢$DTdTÅEõD„TÔR"À¢$÷fW&Æ•v–æF÷r"À¥Ğ