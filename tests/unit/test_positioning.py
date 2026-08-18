"""Geometry-only PositionManager tests for Step15."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QRect, QSize

from app.overlay.positioning import (
    DEFAULT_POSITION_MODE,
    PositionManager,
    PositionMode,
)


SCREEN_1920 = QRect(0, 0, 1920, 1080)
WINDOW_SIZE = QSize(500, 200)


def test_bottom_center_and_top_modes_use_available_geometry() -> None:
    bottom = PositionManager(mode=PositionMode.DESKTOP_LYRICS_BOTTOM, margin=24)
    center = PositionManager(mode=PositionMode.DESKTOP_LYRICS_CENTER)
    top = PositionManager(mode=PositionMode.DESKTOP_LYRICS_TOP, margin=24)

    assert bottom.position_for(WINDOW_SIZE, available_screen=SCREEN_1920) == QPoint(
        710,
        856,
    )
    assert center.position_for(WINDOW_SIZE, available_screen=SCREEN_1920) == QPoint(
        710,
        440,
    )
    assert top.position_for(WINDOW_SIZE, available_screen=SCREEN_1920) == QPoint(
        710,
        24,
    )


@pytest.mark.parametrize(
    "screen",
    [
        QRect(0, 0, 1920, 1080),
        QRect(0, 0, 2560, 1440),
        QRect(0, 0, 3840, 2160),
        QRect(-1920, 0, 1920, 1080),
    ],
)
def test_bottom_mode_stays_inside_positive_or_negative_screen(screen: QRect) -> None:
    manager = PositionManager(mode=PositionMode.DESKTOP_LYRICS_BOTTOM, margin=24)

    position = manager.position_for(WINDOW_SIZE, available_screen=screen)
    overlay = QRect(position, WINDOW_SIZE)

    assert screen.contains(overlay.topLeft())
    assert screen.contains(overlay.bottomRight())


def test_mouse_follow_uses_cursor_screen_and_clamps_at_edge() -> None:
    screen = QRect(-1920, 0, 1920, 1080)
    manager = PositionManager(
        mode=PositionMode.MOUSE_FOLLOW,
        mouse_offset=(16, 16),
    )

    position = manager.position_for(
        WINDOW_SIZE,
        mouse_position=QPoint(-10, 100),
        available_screen=screen,
    )

    assert position == QPoint(-500, 116)
    assert screen.contains(QRect(position, WINDOW_SIZE).bottomRight())


def test_custom_fixed_position_is_clamped_and_manual_position_can_be_remembered() -> None:
    screen = QRect(-1920, 0, 1920, 1080)
    manager = PositionManager(
        mode=PositionMode.CUSTOM_FIXED_POSITION,
        custom_position=(1000, 100),
    )

    assert manager.position_for(WINDOW_SIZE, available_screen=screen) == QPoint(
        -500,
        100,
    )

    manager.remember_manual_position(QPoint(-1500, 300))
    assert manager.custom_position == QPoint(-1500, 300)
    assert manager.position_for(WINDOW_SIZE, available_screen=screen) == QPoint(
        -1500,
        300,
    )


def test_invalid_mode_falls_back_to_safe_default() -> None:
    manager = PositionManager(mode="not-a-real-mode")

    assert manager.position_mode == DEFAULT_POSITION_MODE
    assert manager.set_position_mode("also-invalid") == DEFAULT_POSITION_MODE
