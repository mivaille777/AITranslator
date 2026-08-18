"""pytest-qt coverage for the overlay window."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QMouseEvent

from app.overlay.positioning import clamp_position, centered_position
from app.overlay.window import DEFAULT_TEST_TEXT, OverlayWindow


def test_overlay_window_has_base_window_properties(qtbot) -> None:
    window = OverlayWindow()
    qtbot.addWidget(window)

    assert isinstance(window, OverlayWindow)
    assert window.text() == DEFAULT_TEST_TEXT
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert not window.isVisible()


def test_show_text_updates_text_and_visibility(qtbot) -> None:
    window = OverlayWindow()
    qtbot.addWidget(window)

    window.show_text("Hello / 你好")
    qtbot.wait(10)

    assert window.text() == "Hello / 你好"
    assert window.text_label.text() == "Hello / 你好"
    assert window.isVisible()


def test_overlay_show_and_content_animations_finish_cleanly(qtbot) -> None:
    window = OverlayWindow()
    qtbot.addWidget(window)

    window.show_text("first result")
    assert window.isVisible()
    qtbot.wait(220)

    assert window._show_animation is None
    assert window.windowOpacity() == 1.0

    window.show_text("second result")
    assert window.text() == "second result"
    assert window._content_animation is not None
    qtbot.wait(180)
    assert window._content_animation is None
    assert window._content_fade_opacity == 1.0


def test_loading_indicator_cycles_and_stops_for_result(qtbot) -> None:
    window = OverlayWindow()
    qtbot.addWidget(window)

    window.show_loading("source text", "en", "zh-CN")
    assert window.is_loading
    assert window.text().startswith("翻译中")
    first_loading_text = window.text()
    qtbot.waitUntil(
        lambda: window.text() != first_loading_text,
        timeout=1000,
    )

    assert window.is_loading
    assert window.text().startswith("翻译中")
    assert window.text() != first_loading_text

    window.show_translation("source text", "译文结果", "en", "zh-CN")
    assert not window.is_loading
    assert window.translation_text == "译文结果"
    qtbot.wait(180)
    assert window.text() == "译文结果"


def test_original_visibility_and_hover_use_short_transitions(qtbot) -> None:
    window = OverlayWindow()
    qtbot.addWidget(window)
    window.show_translation("source text", "译文结果", "en", "zh-CN")
    qtbot.wait(180)
    height_without_source = window.height()

    window.set_original_visible(True)
    assert window.original_visible
    qtbot.wait(240)
    assert window.height() > height_without_source

    window._animate_header_opacity(1.0)
    qtbot.wait(150)
    assert window._header_emphasis == 1.0
    window._animate_header_opacity(0.82)
    qtbot.wait(150)
    assert window._header_emphasis == 0.82


def test_hide_and_show_overlay_state(qtbot) -> None:
    window = OverlayWindow()
    qtbot.addWidget(window)

    window.show_overlay()
    assert window.isVisible()


def test_toggling_topmost_keeps_visible_overlay_visible(qtbot) -> None:
    window = OverlayWindow()
    qtbot.addWidget(window)
    window.show_text("topmost test")
    qtbot.wait(220)
    original_position = QPoint(window.pos())

    assert window.set_always_on_top(False) is False
    assert window.isVisible()
    assert not window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert window.pos() == original_position

    assert window.set_always_on_top(True) is True
    assert window.isVisible()
    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert window.pos() == original_position


def test_lock_and_unlock_overlay_updates_state_and_adapter(qtbot) -> None:
    adapter = MagicMock()
    adapter.set_locked.return_value = True
    window = OverlayWindow(win32_adapter=adapter)
    qtbot.addWidget(window)

    assert not window.is_locked
    assert window.lock_overlay()
    assert window.is_locked
    adapter.set_locked.assert_called_once_with(window, locked=True)

    assert window.unlock_overlay()
    assert not window.is_locked
    assert adapter.set_locked.call_args_list[-1].args == (window,)
    assert adapter.set_locked.call_args_list[-1].kwargs == {"locked": False}


def test_unlocked_overlay_handles_drag_events(qtbot) -> None:
    adapter = MagicMock()
    window = OverlayWindow(win32_adapter=adapter)
    qtbot.addWidget(window)
    window.show_overlay()
    window.resize(260, 70)
    window.move(20, 20)

    original_position = window.pos()
    start = QPointF(original_position + QPoint(10, 10))
    target = start + QPointF(40, 30)
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(10, 10),
        start,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mousePressEvent(press)
    assert window._dragging

    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(50, 40),
        QPointF(50, 40),
        target,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mouseMoveEvent(move)

    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(50, 40),
        QPointF(50, 40),
        target,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mouseReleaseEvent(release)

    assert not window._dragging
    assert window.pos() == original_position + QPoint(40, 30)
    assert window.position_mode == "custom_fixed_position"
    assert window.isVisible()


def test_locked_overlay_does_not_start_drag(qtbot) -> None:
    adapter = MagicMock()
    adapter.set_locked.return_value = True
    window = OverlayWindow(win32_adapter=adapter)
    qtbot.addWidget(window)
    assert window.lock_overlay()

    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(10, 10),
        QPointF(10, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mousePressEvent(press)

    assert not window._dragging

    window.hide_overlay()
    assert not window.isVisible()

    window.show_overlay()
    assert window.isVisible()


def test_empty_text_is_safe(qtbot) -> None:
    window = OverlayWindow()
    qtbot.addWidget(window)

    window.show_text("")

    assert window.text() == ""
    assert window.width() > 0
    assert window.height() > 0


def test_long_text_wraps_within_maximum_width(qtbot) -> None:
    window = OverlayWindow(max_width=640)
    qtbot.addWidget(window)
    long_text = ("A long sentence for wrapping. " * 200).strip()

    window.show_text(long_text)

    assert window.text() == long_text
    assert window.width() <= window.max_width
    assert window.height() > 56


def test_positioning_clamps_negative_and_oversized_coordinates() -> None:
    screen = QRect(-1920, 0, 1920, 1080)
    size = QSize(500, 200)

    assert clamp_position(QPoint(-3000, -100), size, available_screen=screen) == QPoint(
        -1920,
        0,
    )
    assert clamp_position(QPoint(1000, 1000), size, available_screen=screen) == QPoint(
        -500,
        880,
    )
    assert centered_position(size, available_screen=screen) == QPoint(-1210, 440)
