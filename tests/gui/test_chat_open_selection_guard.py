from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.ai.streaming_controller import StreamingResizableAIAppController
from app.input.hotkey_manager import GlobalHotkeyManager
from app.input.mouse_selection_manager import MOUSE_SELECTION_SOURCE
from app.models.events import TranslationTriggerEvent
from app.models.selection import SelectedText
from app.translation.fake_provider import FakeTranslationProvider
from app.translation.manager import TranslationManager
from app.ui.tray import TrayManager


class FakeSelectionManager:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def get_selected_text(self) -> SelectedText:
        self.calls += 1
        return SelectedText(self.text, provider="fake-selection")


class FakeOpenChatOverlayManager:
    def __init__(self, *, capture_armed: bool) -> None:
        self.is_locked = False
        self.window = SimpleNamespace(chat_open=True)
        self.capture_armed = capture_armed
        self.inserted: list[str] = []
        self.hidden = 0

    def is_chat_selection_capture_armed(self) -> bool:
        return self.capture_armed

    def insert_chat_selection(self, text: object) -> bool:
        self.inserted.append(str(text))
        return True

    def hide_overlay(self) -> None:
        self.hidden += 1

    def show_translation(self, *_args) -> None:
        raise AssertionError("open Chat must not be replaced by translation")

    def show_text(self, *_args) -> None:
        pass

    def unlock_overlay(self) -> bool:
        self.is_locked = False
        return True


def _make_controller(qapp, overlay, selection):
    tray = TrayManager(parent=qapp)
    tray.hide()
    hotkey = GlobalHotkeyManager(parent=qapp, listener_factory=lambda _mapping: None)
    controller = StreamingResizableAIAppController(
        qapp,
        overlay_manager=overlay,
        tray_manager=tray,
        hotkey_manager=hotkey,
        selection_manager=selection,
        translation_manager=TranslationManager(provider=FakeTranslationProvider()),
        logger=MagicMock(),
    )
    return controller


def test_open_chat_ignores_mouse_selection_when_capture_is_disabled(qapp) -> None:
    overlay = FakeOpenChatOverlayManager(capture_armed=False)
    selection = FakeSelectionManager("must not become a translation")
    controller = _make_controller(qapp, overlay, selection)
    submit_translation = MagicMock()
    controller._submit_translation = submit_translation

    try:
        controller._on_translation_triggered(
            TranslationTriggerEvent(source=MOUSE_SELECTION_SOURCE)
        )

        assert selection.calls == 0
        assert overlay.inserted == []
        assert overlay.hidden == 0
        submit_translation.assert_not_called()
        assert overlay.window.chat_open
    finally:
        controller.shutdown()


def test_open_chat_routes_mouse_selection_to_chat_when_capture_is_armed(qapp) -> None:
    overlay = FakeOpenChatOverlayManager(capture_armed=True)
    selection = FakeSelectionManager("selected evidence")
    controller = _make_controller(qapp, overlay, selection)
    submit_translation = MagicMock()
    controller._submit_translation = submit_translation

    try:
        controller._on_translation_triggered(
            TranslationTriggerEvent(source=MOUSE_SELECTION_SOURCE)
        )

        assert selection.calls == 1
        assert overlay.inserted == ["selected evidence"]
        assert overlay.hidden == 0
        submit_translation.assert_not_called()
        assert overlay.window.chat_open
    finally:
        controller.shutdown()
