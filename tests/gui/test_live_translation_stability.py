from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.chat.conversation_manager import ConversationManager
from app.ai.editable_controller import EditableStreamingResizableAIAppController
from app.ai.editable_overlay import (
    MANUAL_TRANSLATION_DEBOUNCE_MILLISECONDS,
    EditableResizableConversationalAIOverlayManager,
)
from app.infrastructure.settings import SettingsManager
from app.input.hotkey_manager import GlobalHotkeyManager
from app.translation.errors import TranslationError
from app.translation.fake_provider import FakeTranslationProvider, TEST_TRANSLATION_PREFIX
from app.translation.manager import TranslationManager
from app.translation.task import TranslationTaskFailure
from app.ui.tray import TrayManager


class HoldingPool:
    """Keep QRunnables queued so tests can drive completion deterministically."""

    def __init__(self) -> None:
        self.tasks: list[object] = []

    def start(self, task) -> None:
        self.tasks.append(task)

    def clear(self) -> None:
        pass

    def waitForDone(self, _milliseconds: int) -> bool:  # noqa: N802 - Qt compatibility
        return True


def _components(qapp, tmp_path):
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    default_path.write_text(
        """
[translation]
source_language = "auto"
target_language = "zh-CN"

[overlay]
show_original = true

[ai]
provider = "deepseek"
model = "deepseek-v4-flash"
base_url = "https://api.deepseek.com"
""",
        encoding="utf-8",
    )
    config = SettingsManager(default_path, user_path)
    overlay = EditableResizableConversationalAIOverlayManager(config_manager=config)
    tray = TrayManager(parent=qapp)
    tray.hide()
    hotkey = GlobalHotkeyManager(parent=qapp, listener_factory=lambda _mapping: None)
    conversations = ConversationManager(storage_path=tmp_path / "history.sqlite3")
    return config, overlay, tray, hotkey, conversations


def _controller(qapp, tmp_path):
    config, overlay, tray, hotkey, conversations = _components(qapp, tmp_path)
    pool = HoldingPool()
    controller = EditableStreamingResizableAIAppController(
        qapp,
        overlay_manager=overlay,
        config_manager=config,
        tray_manager=tray,
        hotkey_manager=hotkey,
        translation_manager=TranslationManager(provider=FakeTranslationProvider()),
        conversation_manager=conversations,
        translation_pool=pool,
        logger=MagicMock(),
    )
    return controller, overlay, pool


def test_live_translation_keeps_one_provider_request_and_only_queues_latest(qapp, tmp_path) -> None:
    controller, _overlay, pool = _controller(qapp, tmp_path)
    try:
        controller._translate_manual_source("first")
        assert len(pool.tasks) == 1
        first_task = pool.tasks[0]
        first_request_id = first_task.request_id

        controller._translate_manual_source("second")
        controller._translate_manual_source("third")

        assert len(pool.tasks) == 1
        assert controller._manual_translation_pending_text == "third"
        assert controller.latest_request_id != first_request_id

        controller._on_translation_task_finished(first_task)

        assert len(pool.tasks) == 2
        assert pool.tasks[-1].source_text == "third"
        assert controller._manual_translation_pending_text is None
    finally:
        controller.shutdown()


def test_manual_provider_failure_stays_inline_instead_of_replacing_workspace(qapp, tmp_path) -> None:
    controller, overlay, pool = _controller(qapp, tmp_path)
    try:
        controller._last_translation_text = "previous translation"
        controller._translate_manual_source("temporary network failure")
        task = pool.tasks[-1]

        controller._on_translation_task_failed(
            TranslationTaskFailure(
                request_id=task.request_id,
                error=TranslationError("temporary failure"),
            )
        )

        assert "暂时失败" in overlay.window.translation_status_label.text()
        assert controller._last_translation_text == "previous translation"
        assert overlay.window.source_editor.toPlainText() != "TranslationError: translation request failed."
    finally:
        controller.shutdown()


def test_source_editor_reaches_result_through_real_qthreadpool(qtbot, qapp, tmp_path) -> None:
    """Exercise the exact manual-input worker path used by the application."""

    config, overlay, tray, hotkey, conversations = _components(qapp, tmp_path)
    controller = EditableStreamingResizableAIAppController(
        qapp,
        overlay_manager=overlay,
        config_manager=config,
        tray_manager=tray,
        hotkey_manager=hotkey,
        translation_manager=TranslationManager(provider=FakeTranslationProvider()),
        conversation_manager=conversations,
        logger=MagicMock(),
    )
    try:
        window = overlay.window
        window.set_original_visible(True)
        window.show()
        window.source_editor.setPlainText("manual end to end")

        qtbot.waitUntil(
            lambda: window.translation_text
            == f"{TEST_TRANSLATION_PREFIX}manual end to end",
            timeout=3000 + MANUAL_TRANSLATION_DEBOUNCE_MILLISECONDS,
        )

        assert controller._last_translation_text == (
            f"{TEST_TRANSLATION_PREFIX}manual end to end"
        )
        assert controller._manual_translation_inflight_request_id is None
    finally:
        controller.shutdown()
