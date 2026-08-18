"""Safe Qt screen and overlay-position calculations."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QCursor, QGuiApplication, QScreen

from app.infrastructure.config import ConfigManager

FALLBACK_SCREEN_GEOMETRY = QRect(0, 0, 1920, 1080)
DEFAULT_POSITION_MODE = "desktop_lyrics_bottom"
DEFAULT_POSITION_MARGIN = 24
DEFAULT_CUSTOM_POSITION = (80, 80)
DEFAULT_MOUSE_OFFSET = (16, 16)


class PositionMode(str, Enum):
    """Supported overlay placement strategies."""

    DESKTOP_LYRICS_BOTTOM = "desktop_lyrics_bottom"
    DESKTOP_LYRICS_CENTER = "desktop_lyrics_center"
    DESKTOP_LYRICS_TOP = "desktop_lyrics_top"
    MOUSE_FOLLOW = "mouse_follow"
    CUSTOM_FIXED_POSITION = "custom_fixed_position"


SUPPORTED_POSITION_MODES = tuple(item.value for item in PositionMode)


def _screen_for_position(position: QPoint | None, screen: QScreen | None) -> QScreen | None:
    if screen is not None:
        return screen

    application = QGuiApplication.instance()
    if application is None:
        return None

    if position is not None:
        screen_at_position = application.screenAt(position)
        if screen_at_position is not None:
            return screen_at_position

    return application.primaryScreen()


def available_geometry(
    *,
    screen: QScreen | None = None,
    reference_position: QPoint | None = None,
) -> QRect:
    """Return a usable screen rectangle, with a safe headless fallback."""

    resolved_screen = _screen_for_position(reference_position, screen)
    if resolved_screen is None:
        return QRect(FALLBACK_SCREEN_GEOMETRY)
    return QRect(resolved_screen.availableGeometry())


def clamp_position(
    position: QPoint,
    window_size: QSize,
    *,
    screen: QScreen | None = None,
    available_screen: QRect | None = None,
) -> QPoint:
    """Keep a window's top-left point inside the selected screen."""

    bounds = QRect(available_screen) if available_screen is not None else available_geometry(
        screen=screen,
        reference_position=position,
    )
    if bounds.width() <= 0 or bounds.height() <= 0:
        return QPoint(bounds.left(), bounds.top())

    width = max(1, window_size.width())
    height = max(1, window_size.height())
    maximum_x = max(bounds.left(), bounds.right() - width + 1)
    maximum_y = max(bounds.top(), bounds.bottom() - height + 1)

    return QPoint(
        min(max(position.x(), bounds.left()), maximum_x),
        min(max(position.y(), bounds.top()), maximum_y),
    )


def centered_position(
    window_size: QSize,
    *,
    screen: QScreen | None = None,
    available_screen: QRect | None = None,
) -> QPoint:
    """Return a centered, valid position for a window."""

    bounds = QRect(available_screen) if available_screen is not None else available_geometry(
        screen=screen,
    )
    return clamp_position(
        QPoint(
            bounds.left() + (bounds.width() - window_size.width()) // 2,
            bounds.top() + (bounds.height() - window_size.height()) // 2,
        ),
        window_size,
        available_screen=bounds,
    )


class PositionManager:
    """Calculate overlay positions in Qt's logical desktop coordinates.

    ``QScreen.availableGeometry()`` already reflects the current monitor's
    work area and DPI-aware logical coordinates. Keeping all mode-specific
    calculations here lets the QWidget remain responsible only for rendering
    and mouse dragging.
    """

    def __init__(
        self,
        *,
        config_manager: ConfigManager | Any | None = None,
        mode: str | PositionMode | None = None,
        margin: int | None = None,
        custom_position: QPoint | Sequence[int] | None = None,
        mouse_offset: QPoint | Sequence[int] | None = None,
        cursor_position_reader: Callable[[], QPoint] | None = None,
    ) -> None:
        self.config_manager = config_manager or ConfigManager()
        configured_mode = (
            mode
            if mode is not None
            else getattr(
                self.config_manager,
                "overlay_position_mode",
                DEFAULT_POSITION_MODE,
            )
        )
        self._position_mode = self._coerce_mode(configured_mode)

        configured_margin = (
            margin
            if margin is not None
            else getattr(
                self.config_manager,
                "overlay_position_margin",
                DEFAULT_POSITION_MARGIN,
            )
        )
        self._margin = self._coerce_nonnegative_int(
            configured_margin,
            DEFAULT_POSITION_MARGIN,
        )

        configured_custom = (
            custom_position
            if custom_position is not None
            else getattr(
                self.config_manager,
                "overlay_custom_position",
                DEFAULT_CUSTOM_POSITION,
            )
        )
        self._custom_position = self._coerce_point(
            configured_custom,
            DEFAULT_CUSTOM_POSITION,
        )

        configured_offset = (
            mouse_offset
            if mouse_offset is not None
            else getattr(
                self.config_manager,
                "overlay_mouse_offset",
                DEFAULT_MOUSE_OFFSET,
            )
        )
        self._mouse_offset = self._coerce_point(
            configured_offset,
            DEFAULT_MOUSE_OFFSET,
        )
        self._cursor_position_reader = cursor_position_reader or QCursor.pos

    @staticmethod
    def _coerce_mode(value: object) -> str:
        candidate = value.value if isinstance(value, PositionMode) else str(value)
        candidate = candidate.strip().lower()
        if candidate in SUPPORTED_POSITION_MODES:
            return candidate
        return DEFAULT_POSITION_MODE

    @staticmethod
    def _coerce_nonnegative_int(value: object, fallback: int) -> int:
        try:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError("value must be finite")
            return max(0, int(number))
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _coerce_point(
        value: object,
        fallback: QPoint | Sequence[int],
    ) -> QPoint:
        try:
            if isinstance(value, QPoint):
                return QPoint(value)
            coordinates = list(value)  # type: ignore[arg-type]
            if len(coordinates) != 2:
                raise ValueError("point must contain two coordinates")
            return QPoint(int(coordinates[0]), int(coordinates[1]))
        except (TypeError, ValueError):
            if isinstance(fallback, QPoint):
                return QPoint(fallback)
            return QPoint(int(fallback[0]), int(fallback[1]))

    @property
    def position_mode(self) -> str:
        """Return the active placement mode."""

        return self._position_mode

    @property
    def mode(self) -> str:
        """Alias for callers that use the shorter mode name."""

        return self.position_mode

    @property
    def margin(self) -> int:
        """Return the edge margin in logical pixels."""

        return self._margin

    @property
    def custom_position(self) -> QPoint:
        """Return the remembered fixed position."""

        return QPoint(self._custom_position)

    @property
    def mouse_offset(self) -> QPoint:
        """Return the cursor-to-overlay offset for mouse-follow mode."""

        return QPoint(self._mouse_offset)

    def set_position_mode(self, mode: str | PositionMode) -> str:
        """Set the active mode, falling back safely for invalid values."""

        self._position_mode = self._coerce_mode(mode)
        return self._position_mode

    def set_custom_position(
        self,
        position: QPoint | Sequence[int],
    ) -> QPoint:
        """Remember a user-selected fixed position for future placements."""

        self._custom_position = self._coerce_point(
            position,
            self._custom_position,
        )
        return self.custom_position

    remember_manual_position = set_custom_position

    def clamp_position(
        self,
        position: QPoint | Sequence[int],
        window_size: QSize,
        *,
        screen: QScreen | None = None,
        available_screen: QRect | None = None,
    ) -> QPoint:
        """Clamp a point to the selected screen work area."""

        point = self._coerce_point(position, (0, 0))
        return clamp_position(
            point,
            window_size,
            screen=screen,
            available_screen=available_screen,
        )

    def position_for(
        self,
        window_size: QSize,
        *,
        mode: str | PositionMode | None = None,
        screen: QScreen | None = None,
        reference_position: QPoint | None = None,
        mouse_position: QPoint | None = None,
        available_screen: QRect | None = None,
    ) -> QPoint:
        """Return a valid top-left point for the active placement mode."""

        selected_mode = (
            self._coerce_mode(mode) if mode is not None else self._position_mode
        )
        cursor_position = (
            QPoint(mouse_position)
            if mouse_position is not None
            else self._read_cursor_position()
        )
        reference = (
            QPoint(reference_position)
            if reference_position is not None
            else cursor_position
        )
        bounds = (
            QRect(available_screen)
            if available_screen is not None
            else available_geometry(
                screen=screen,
                reference_position=reference,
            )
        )

        if selected_mode == PositionMode.DESKTOP_LYRICS_BOTTOM.value:
            candidate = QPoint(
                bounds.left() + (bounds.width() - window_size.width()) // 2,
                bounds.bottom() - window_size.height() + 1 - self._margin,
            )
        elif selected_mode == PositionMode.DESKTOP_LYRICS_CENTER.value:
            candidate = QPoint(
                bounds.left() + (bounds.width() - window_size.width()) // 2,
                bounds.top() + (bounds.height() - window_size.height()) // 2,
            )
        elif selected_mode == PositionMode.DESKTOP_LYRICS_TOP.value:
            candidate = QPoint(
                bounds.left() + (bounds.width() - window_size.width()) // 2,
                bounds.top() + self._margin,
            )
        elif selected_mode == PositionMode.MOUSE_FOLLOW.value:
            candidate = cursor_position + self._mouse_offset
        else:
            candidate = QPoint(self._custom_position)

        return clamp_position(
            candidate,
            window_size,
            available_screen=bounds,
        )

    def centered_position(
        self,
        window_size: QSize,
        *,
        screen: QScreen | None = None,
        available_screen: QRect | None = None,
    ) -> QPoint:
        """Return a centered position without changing the active mode."""

        return self.position_for(
            window_size,
            mode=PositionMode.DESKTOP_LYRICS_CENTER,
            screen=screen,
            available_screen=available_screen,
        )

    def _read_cursor_position(self) -> QPoint:
        try:
            return self._coerce_point(self._cursor_position_reader(), (0, 0))
        except Exception:
            return QPoint(0, 0)


__all__ = [
    "DEFAULT_CUSTOM_POSITION",
    "DEFAULT_MOUSE_OFFSET",
    "DEFAULT_POSITION_MARGIN",
    "DEFAULT_POSITION_MODE",
    "FALLBACK_SCREEN_GEOMETRY",
    "PositionManager",
    "PositionMode",
    "SUPPORTED_POSITION_MODES",
    "available_geometry",
    "centered_position",
    "clamp_position",
]
