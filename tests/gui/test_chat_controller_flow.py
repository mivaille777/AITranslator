from __future__ import annotations

import threading
from unittest.mock import MagicMock

from app.ai.chat.models import ChatRequest, ChatResult
from app.ai.chat_controller import ConversationalAIAppController
from app.input.hotkey_manager import GlobalHotkeyManager
from app.translation.fake_provider import FakeTranslationProvider
from app.translation.manager import TranslationManager


class FakeConversationalOverlayManager:
    def __init__(self) -> None:
        self.is_locked = False
        self.opened: list[dict[str, object]] = []
        self.chat_messages: list[tuple[object, str]] = []
        self.busy_states: list[bool] = []
        self.errors: list[str] = []
        self.identities: list[tuple[str, str]] = []
        self.cleared = 0
        self.closed = 0

    def open_chat(self, **kwargs) -> None:
        self.opened.append(kwargs)

    def close_chat(self) -> None:
        self.closed += 1

    def clear_chat(self) -> None:
        self.cleared += 1

    def append_chat_message(self, role, text: str) -> None:
        self.chat_messages.append((role, text))

    def set_chat_busy(self, busy: bool) -> None:
        self.busy_states.append(bool(busy))

    def set_chat_error(self, message: str) -> None:
        self.errors.append(message)

    def set_chat_identity(self, provider: str, model: str) -> None:
        self.identities.append((provider, model))

    def show_translation(self, *_args) -> None:
        pass

    def show_text(self, *_args) -> None:
        pass

    def hide_overlay(self) -> None:
        pass

    def unlock_overlay(self) -> bool:
        self.is_locked = False
        return True


class FakeChatService:
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []
        self.thread_ids: list[int] = []

    def execute(self, request: ChatRequest) -> ChatResult:
        self.requests.append(request)
        self.thread_ids.append(threading.get_ident())
        return ChatResult(
            session_id=request.session_id,
            user_message=request.user_message,
            output_text=f"answer:{request.user_message}",
            provider="fake-chat",
            model="fake-model",
            request_id=request.request_id,
        )


def _build_controller(qapp):
    from app.ui.tray import TrayManager

    overlay = FakeConversationalOverlayManager()
    chat_service = FakeChatService()
    tray = TrayManager(parent=qapp)
    tray.hide()
    hotkey = GlobalHotkeyManager(parent=qapp, listener_factory=lambda _mapping: None)
    controller = ConversationalAIAppController(
        qapp,
        overlay_manager=overlay,
        tray_manager=tray,
        hotkey_manager=hotkey,
        translation_manager=TranslationManager(provider=FakeTranslationProvider()),
        chat_service=chat_service,
        logger=MagicMock(),
    )
    controller._last_source_text = "GP anchor"
    controller._last_translation_text = "GP 锚点"
    return controller, overlay, chat_service


def test_chat_controller_opens_with_current_translation_context(qapp) -> None:
    controller, overlay, _service = _build_controller(qapp)
    try:
        controller._on_overlay_context_action("ai_chat", None)

        assert len(overlay.opened) == 1
        opened = overlay.opened[0]
        assert opened["source_text"] == "GP anchor"
        assert opened["translated_text"] == "GP 锚点"
        assert opened["messages"] == ()
    finally:
        controller.shutdown()


def test_chat_controller_keeps_multi_turn_history_and_independent_request_version(
    qapp,
    qtbot,
) -> None:
    controller, overlay, service = _build_controller(qapp)
    gui_thread = threading.get_ident()
    try:
        # Normal translation request versions are intentionally independent.
        assert controller._request_versions.next_request_id() == 1

        controller._on_overlay_context_action("ai_chat", None)
        controller._on_overlay_context_action("ai_chat_send", "为什么使用 GP？")
        qtbot.waitUntil(lambda: not controller._chat_tasks, timeout=2000)

        assert controller.latest_chat_request_id == 1
        assert service.requests[0].history == ()
        assert service.thread_ids[0] != gui_thread
        assert len(controller.chat_session.messages) == 2
        assert overlay.busy_states[-1] is False
        assert overlay.chat_messages[-1][1] == "answer:为什么使用 GP？"

        controller._on_overlay_context_action("ai_chat_send", "那 LLM 的作用呢？")
        qtbot.waitUntil(lambda: not controller._chat_tasks, timeout=2000)

        assert controller.latest_chat_request_id == 2
        assert len(service.requests[1].history) == 2
        assert len(controller.chat_session.messages) == 4
    finally:
        controller.shutdown()


def test_new_selected_context_resets_previous_chat_history(qapp, qtbot) -> None:
    controller, _overlay, _service = _build_controller(qapp)
    try:
        controller._on_overlay_context_action("ai_chat", None)
        controller._on_overlay_context_action("ai_chat_send", "first")
        qtbot.waitUntil(lambda: not controller._chat_tasks, timeout=2000)
        assert len(controller.chat_session.messages) == 2

        controller._last_source_text = "new selected paragraph"
        controller._last_translation_text = "新的译文"
        controller._on_overlay_context_action("ai_chat", None)

        assert controller.chat_session.messages == ()
    finally:
        controller.shutdown()
