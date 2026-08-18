"""Step17 stability, transient-error, and 100-request stress coverage."""

from __future__ import annotations

import random
import threading
import time
from unittest.mock import MagicMock

from app.controller import AppController
from app.input.hotkey_manager import GlobalHotkeyManager
from app.input.mouse_selection_manager import MouseSelectionManager
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.cache import TranslationCache
from app.translation.errors import TranslationError
from app.translation.manager import TranslationManager
from app.ui.tray import TrayManager


class FakeOverlayManager:
    def __init__(self) -> None:
        self.is_locked = False
        self.shown_text: list[str] = []
        self.hide_calls = 0

    def show_text(self, text: str) -> None:
        self.shown_text.append(text)

    def hide_overlay(self) -> None:
        self.hide_calls += 1

    def lock_overlay(self) -> bool:
        self.is_locked = True
        return True

    def unlock_overlay(self) -> bool:
        self.is_locked = False
        return True


class FailingProvider(TranslationProvider):
    def translate(self, _request: TranslationRequest) -> TranslationResult:
        raise TranslationError("provider unavailable")


class RandomStressProvider(TranslationProvider):
    """Deterministic randomized latency/failure provider for stress coverage."""

    def __init__(self) -> None:
        self.random = random.Random(17)
        self.completed_request_ids: list[int] = []
        self._lock = threading.Lock()

    def translate(self, request: TranslationRequest) -> TranslationResult:
        # Make the newest request finish last so the latest-result boundary is
        # deterministic while the other requests still exercise reordering.
        delay = 0.04 if request.request_id == 100 else self.random.uniform(0, 0.008)
        time.sleep(delay)
        with self._lock:
            self.completed_request_ids.append(request.request_id)
        if request.request_id != 100 and self.random.random() < 0.2:
            raise TranslationError("random provider failure")
        return TranslationResult(
            source_text=request.source_text,
            translated_text=f"translated:{request.source_text}",
            source_language=request.source_language,
            target_language=request.target_language,
            provider="random-stress",
            request_id=request.request_id,
        )


def _make_controller(qapp, overlay, manager, logger):
    tray = TrayManager(parent=qapp)
    tray.hide()
    hotkey = GlobalHotkeyManager(
        parent=qapp,
        listener_factory=lambda _mapping: None,
    )
    mouse = MouseSelectionManager(
        parent=qapp,
        listener_factory=lambda **_callbacks: None,
    )
    return AppController(
        qapp,
        overlay_manager=overlay,
        tray_manager=tray,
        hotkey_manager=hotkey,
        mouse_selection_manager=mouse,
        translation_manager=manager,
        logger=logger,
    )


def test_translation_error_is_hidden_automatically(qapp, qtbot, monkeypatch) -> None:
    monkeypatch.setattr("app.controller.ERROR_DISPLAY_MILLISECONDS", 30)
    overlay = FakeOverlayManager()
    logger = MagicMock()
    controller = _make_controller(
        qapp,
        overlay,
        TranslationManager(
            provider=FailingProvider(),
            cache=TranslationCache(enabled=False),
        ),
        logger,
    )

    try:
        controller._show_translation_error("safe error", "TranslationError")
        assert controller.overlay_visible is True
        qtbot.waitUntil(lambda: controller.overlay_visible is False, timeout=1000)
        assert overlay.hide_calls == 1
        logger.info.assert_any_call("translation_error_hidden")
    finally:
        controller.shutdown()


def test_one_hundred_randomized_requests_leave_latest_success_and_no_workers(
    qapp,
    qtbot,
) -> None:
    overlay = FakeOverlayManager()
    provider = RandomStressProvider()
    logger = MagicMock()
    controller = _make_controller(
        qapp,
        overlay,
        TranslationManager(
            provider=provider,
            cache=TranslationCache(enabled=False),
        ),
        logger,
    )

    try:
        for index in range(100):
            controller._submit_translation(f"stress-{index:03d}")

        qtbot.waitUntil(
            lambda: len(provider.completed_request_ids) == 100,
            timeout=10000,
        )
        qtbot.waitUntil(
            lambda: not controller._translation_tasks,
            timeout=10000,
        )
        controller.translation_pool.waitForDone(2000)

        assert controller.latest_request_id == 100
        assert overlay.shown_text == ["translated:stress-099"]
        assert controller.translation_pool.activeThreadCount() == 0
    finally:
        controller.shutdown()
