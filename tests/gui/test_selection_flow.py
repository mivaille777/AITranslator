"""Qt-level wiring test for hotkey -> selection -> overlay."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from app.controller import AppController
from app.input.hotkey_manager import GlobalHotkeyManager
from app.models.events import TranslationTriggerEvent
from app.models.selection import SelectedText
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.fake_provider import FakeTranslationProvider
from app.translation.manager import TranslationManager


class FakeOverlayManager:
    def __init__(self) -> None:
        self.is_locked = False
        self.shown_text: list[str] = []
        self.show_thread_ids: list[int] = []
        self.hide_calls = 0

    def show_text(self, text: str) -> None:
        self.shown_text.append(text)
        self.show_thread_ids.append(threading.get_ident())

    def hide_overlay(self) -> None:
        self.hide_calls += 1

    def lock_overlay(self) -> bool:
        self.is_locked = True
        return True

    def unlock_overlay(self) -> bool:
        self.is_locked = False
        return True


class FakeSelectionManager:
    def get_selected_text(self) -> SelectedText:
        return SelectedText("selected text")


class DelayedTranslationProvider(TranslationProvider):
    """Return requests in the Step9 order 3 -> 2 -> 1."""

    _delays = {
        "request-1": 0.5,
        "request-2": 0.3,
        "request-3": 0.05,
    }

    def __init__(self) -> None:
        self.completed_request_ids: list[int] = []

    def translate(self, request: TranslationRequest) -> TranslationResult:
        time.sleep(self._delays[request.source_text])
        self.completed_request_ids.append(request.request_id)
        return TranslationResult(
            source_text=request.source_text,
            translated_text=f"translated:{request.source_text}",
            source_language=request.source_language,
            target_language=request.target_language,
            provider="delayed-fake",
            request_id=request.request_id,
        )


class SequencedSelectionManager:
    def __init__(self) -> None:
        self._texts = ["request-1", "request-2", "request-3"]

    def get_selected_text(self) -> SelectedText:
        return SelectedText(self._texts.pop(0), provider="test")


def test_hotkey_event_is_routed_to_selection_and_overlay(qapp, qtbot) -> None:
    overlay = FakeOverlayManager()
    hotkey = GlobalHotkeyManager(parent=qapp, listener_factory=lambda _mapping: None)
    logger = MagicMock()

    from app.ui.tray import TrayManager

    tray_manager = TrayManager(parent=qapp)
    tray_manager.hide()
    controller = AppController(
        qapp,
        overlay_manager=overlay,
        tray_manager=tray_manager,
        hotkey_manager=hotkey,
        selection_manager=FakeSelectionManager(),
        translation_manager=TranslationManager(provider=FakeTranslationProvider()),
        logger=logger,
    )

    hotkey.triggered.emit(TranslationTriggerEvent())

    qtbot.waitUntil(
        lambda: overlay.shown_text == ["[TEST TRANSLATION] selected text"],
        timeout=2000,
    )
    assert overlay.shown_text == ["[TEST TRANSLATION] selected text"]
    assert overlay.show_thread_ids == [threading.get_ident()]
    logger.info.assert_any_call(
        "translation_displayed text_length=%s",
        len("[TEST TRANSLATION] selected text"),
    )

    # A second trigger must remove the previous always-on-top result before
    # asking the foreground application to publish a new selection.
    hotkey.triggered.emit(TranslationTriggerEvent())
    assert overlay.hide_calls == 1
    qtbot.waitUntil(lambda: len(overlay.shown_text) == 2, timeout=2000)

    controller.shutdown()


def test_latest_request_wins_when_translation_results_return_out_of_order(
    qapp,
    qtbot,
) -> None:
    overlay = FakeOverlayManager()
    hotkey = GlobalHotkeyManager(parent=qapp, listener_factory=lambda _mapping: None)
    logger = MagicMock()

    from app.ui.tray import TrayManager

    tray_manager = TrayManager(parent=qapp)
    tray_manager.hide()
    provider = DelayedTranslationProvider()
    controller = AppController(
        qapp,
        overlay_manager=overlay,
        tray_manager=tray_manager,
        hotkey_manager=hotkey,
        selection_manager=SequencedSelectionManager(),
        translation_manager=TranslationManager(provider=provider),
        logger=logger,
    )

    try:
        for _ in range(3):
            hotkey.triggered.emit(TranslationTriggerEvent())

        qtbot.waitUntil(
            lambda: len(provider.completed_request_ids) == 3,
            timeout=3000,
        )
        qtbot.waitUntil(
            lambda: not controller._translation_tasks,
            timeout=3000,
        )

        assert provider.completed_request_ids == [3, 2, 1]
        assert controller.latest_request_id == 3
        assert overlay.shown_text == ["translated:request-3"]
        discarded_ids = [
            call.args[1]
            for call in logger.debug.call_args_list
            if call.args
            and call.args[0] == "translation_result_discarded request_id=%s latest_request_id=%s"
        ]
        assert discarded_ids == [2, 1]
    finally:
        controller.shutdown()
