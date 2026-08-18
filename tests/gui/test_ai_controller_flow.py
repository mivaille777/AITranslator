"""Qt-level coverage for AppController AI action integration."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from app.ai.controller import AIAppController
from app.ai.models import AITextAction, AITextRequest, AITextResult
from app.input.hotkey_manager import GlobalHotkeyManager
from app.translation.fake_provider import FakeTranslationProvider
from app.translation.manager import TranslationManager


class FakeOverlayManager:
    def __init__(self) -> None:
        self.is_locked = False
        self.shown: list[tuple[str, str, str, str]] = []
        self.shown_text: list[str] = []

    def show_translation(
        self,
        source_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
    ) -> None:
        self.shown.append(
            (source_text, translated_text, source_language, target_language)
        )

    def show_text(self, text: str) -> None:
        self.shown_text.append(text)

    def hide_overlay(self) -> None:
        pass

    def lock_overlay(self) -> bool:
        self.is_locked = True
        return True

    def unlock_overlay(self) -> bool:
        self.is_locked = False
        return True


class FakeAIService:
    def __init__(self) -> None:
        self.requests: list[AITextRequest] = []
        self.thread_ids: list[int] = []
        self.closed = False

    def execute(self, request: AITextRequest) -> AITextResult:
        self.requests.append(request)
        self.thread_ids.append(threading.get_ident())
        prefix = "translated" if request.action is AITextAction.TRANSLATE else "polished"
        return AITextResult(
            source_text=request.source_text,
            output_text=f"{prefix}:{request.source_text}",
            action=request.action,
            provider="fake-ai",
            model="fake-model",
            source_language=request.source_language,
            target_language=request.target_language,
            style=request.style,
            request_id=request.request_id,
        )

    def close(self) -> None:
        self.closed = True


def _build_controller(qapp):
    from app.ui.tray import TrayManager

    overlay = FakeOverlayManager()
    service = FakeAIService()
    tray = TrayManager(parent=qapp)
    tray.hide()
    hotkey = GlobalHotkeyManager(parent=qapp, listener_factory=lambda _mapping: None)
    controller = AIAppController(
        qapp,
        overlay_manager=overlay,
        tray_manager=tray,
        hotkey_manager=hotkey,
        translation_manager=TranslationManager(provider=FakeTranslationProvider()),
        ai_service=service,
        logger=MagicMock(),
    )
    controller._last_source_text = "hello world"
    return controller, overlay, service


def test_ai_translate_action_runs_through_worker_and_displays_result(qapp, qtbot) -> None:
    controller, overlay, service = _build_controller(qapp)
    gui_thread = threading.get_ident()

    try:
        controller._on_overlay_context_action("ai_translate", None)
        qtbot.waitUntil(lambda: not controller._ai_tasks, timeout=2000)

        assert len(service.requests) == 1
        request = service.requests[0]
        assert request.action is AITextAction.TRANSLATE
        assert request.request_id == controller.latest_request_id == 1
        assert service.thread_ids[0] != gui_thread
        assert overlay.shown[-1][1] == "translated:hello world"
        assert controller._last_translation_text == "translated:hello world"
    finally:
        controller.shutdown()


def test_ai_polish_uses_same_language_metadata_and_shared_request_version(qapp, qtbot) -> None:
    controller, overlay, service = _build_controller(qapp)
    controller.translation_manager.configure_languages("en", "zh-CN")

    try:
        # Advance the same version sequence once to model a preceding normal
        # translation request, then launch the AI action.
        assert controller._request_versions.next_request_id() == 1
        controller._on_overlay_context_action("ai_polish", None)
        qtbot.waitUntil(lambda: not controller._ai_tasks, timeout=2000)

        request = service.requests[0]
        assert request.request_id == controller.latest_request_id == 2
        assert request.action is AITextAction.POLISH
        assert request.source_language == "en"
        assert request.target_language == "en"
        assert overlay.shown[-1] == (
            "hello world",
            "polished:hello world",
            "en",
            "润色",
        )
    finally:
        controller.shutdown()


def test_missing_source_does_not_submit_ai_work(qapp) -> None:
    controller, _overlay, service = _build_controller(qapp)
    controller._last_source_text = ""

    try:
        controller._on_overlay_context_action("ai_translate", None)
        assert service.requests == []
        assert not controller._ai_tasks
    finally:
        controller.shutdown()
