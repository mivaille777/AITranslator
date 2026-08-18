"""Qt-level tests for Step14 automatic mouse-selection wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import QObject, Signal

from app.controller import AppController
from app.infrastructure.config import ConfigManager
from app.input.hotkey_manager import GlobalHotkeyManager
from app.input.mouse_selection_manager import MOUSE_SELECTION_SOURCE
from app.models.events import TranslationTriggerEvent
from app.models.selection import SelectedText
from app.translation.fake_provider import FakeTranslationProvider
from app.translation.manager import TranslationManager
from app.ui.tray import TrayManager


class FakeOverlayManager:
    def __init__(self) -> None:
        self.is_locked = False
        self.shown_text: list[str] = []
        self.hide_calls = 0
        self.cursor_over_overlay = False

    def show_text(self, text: str) -> None:
        self.shown_text.append(text)

    def hide_overlay(self) -> None:
        self.hide_calls += 1

    def contains_global_point(self, _x: int, _y: int) -> bool:
        return self.cursor_over_overlay

    def lock_overlay(self) -> bool:
        self.is_locked = True
        return True

    def unlock_overlay(self) -> bool:
        self.is_locked = False
        return True


class FakeSelectionManager:
    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls = 0

    def get_selected_text(self) -> SelectedText:
        self.calls += 1
        return SelectedText(self._texts[min(self.calls - 1, len(self._texts) - 1)])


class FakeMouseSelectionManager(QObject):
    triggered = Signal(object)

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> bool:
        self.start_calls += 1
        return True

    def stop(self) -> None:
        self.stop_calls += 1


def _make_controller(qapp, *, selection_manager, mouse_manager):
    tray = TrayManager(parent=qapp)
    tray.hide()
    hotkey = GlobalHotkeyManager(
        parent=qapp,
        listener_factory=lambda _mapping: None,
    )
    overlay = FakeOverlayManager()
    logger = MagicMock()
    controller = AppController(
        qapp,
        config_manager=ConfigManager(),
        overlay_manager=overlay,
        tray_manager=tray,
        hotkey_manager=hotkey,
        mouse_selection_manager=mouse_manager,
        selection_manager=selection_manager,
        translation_manager=TranslationManager(
            provider=FakeTranslationProvider(),
        ),
        logger=logger,
    )
    return controller, overlay, tray, logger


def _auto_event() -> TranslationTriggerEvent:
    return TranslationTriggerEvent(
        hotkey=MOUSE_SELECTION_SOURCE,
        source=MOUSE_SELECTION_SOURCE,
    )


def test_auto_selection_allows_repeating_same_normalized_text(
    qapp,
    qtbot,
) -> None:
    selection = FakeSelectionManager(["  same   text  ", "same text"])
    mouse_manager = FakeMouseSelectionManager(qapp)
    controller, overlay, _tray, logger = _make_controller(
        qapp,
        selection_manager=selection,
        mouse_manager=mouse_manager,
    )

    try:
        mouse_manager.triggered.emit(_auto_event())
        qtbot.waitUntil(lambda: len(overlay.shown_text) == 1, timeout=2000)

        mouse_manager.triggered.emit(_auto_event())
        qtbot.waitUntil(lambda: len(overlay.shown_text) == 2, timeout=2000)

        assert selection.calls == 2
        assert controller.latest_request_id == 2
        assert overlay.shown_text == [
            "[TEST TRANSLATION] same text",
            "[TEST TRANSLATION] same text",
        ]
    finally:
        controller.shutdown()


def test_auto_selection_over_overlay_does_not_hide_or_capture(
    qapp,
    qtbot,
) -> None:
    selection = FakeSelectionManager(["text behind overlay"])
    mouse_manager = FakeMouseSelectionManager(qapp)
    controller, overlay, _tray, logger = _make_controller(
        qapp,
        selection_manager=selection,
        mouse_manager=mouse_manager,
    )

    try:
        overlay.cursor_over_overlay = True
        mouse_manager.triggered.emit(_auto_event())
        qtbot.wait(50)

        assert selection.calls == 0
        assert overlay.hide_calls == 0
        logger.info.assert_any_call("auto_selection_ignored overlay_hover")
    finally:
        controller.shutdown()


def test_paused_translation_does_not_capture_mouse_selection(qapp, qtbot) -> None:
    selection = FakeSelectionManager(["paused text"])
    mouse_manager = FakeMouseSelectionManager(qapp)
    controller, _overlay, _tray, logger = _make_controller(
        qapp,
        selection_manager=selection,
        mouse_manager=mouse_manager,
    )

    try:
        controller._pause_translation()
        mouse_manager.triggered.emit(_auto_event())
        qtbot.wait(50)

        assert selection.calls == 0
        logger.info.assert_any_call("auto_selection_ignored translation_paused")
    finally:
        controller.shutdown()


def test_tray_can_enable_and_disable_auto_selection(qapp) -> None:
    selection = FakeSelectionManager(["text"])
    mouse_manager = FakeMouseSelectionManager(qapp)
    controller, _overlay, tray, _logger = _make_controller(
        qapp,
        selection_manager=selection,
        mouse_manager=mouse_manager,
    )

    try:
        assert controller.auto_selection_enabled
        assert tray.actions["auto_selection"].isChecked()

        tray.actions["auto_selection"].trigger()
        assert not controller.auto_selection_enabled
        assert mouse_manager.stop_calls == 1

        tray.actions["auto_selection"].trigger()
        assert controller.auto_selection_enabled
        assert mouse_manager.start_calls == 1
    finally:
        controller.shutdown()
