from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor

from app.ai.chat_selection_controller import (
    SelectionCaptureConversationalAIAppController,
)
from app.ai.chat_selection_overlay import (
    SelectionCaptureConversationalAIOverlayWindow,
)
from app.ai.chat_selection_ui import SelectionCaptureChatPanel
from app.input.hotkey_manager import GlobalHotkeyManager
from app.input.mouse_selection_manager import MOUSE_SELECTION_SOURCE
from app.models.events import TranslationTriggerEvent
from app.models.selection import SelectedText
from app.translation.fake_provider import FakeTranslationProvider
from app.translation.manager import TranslationManager


class FakeSelectionManager:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def get_selected_text(self) -> SelectedText:
        self.calls += 1
        return SelectedText(self.text, provider="fake-selection")


class FakeCaptureOverlayManager:
    def __init__(self) -> None:
        self.is_locked = False
        self.capture_armed = True
        self.inserted: list[str] = []
        self.errors: list[str] = []
        self.hidden = 0

    def is_chat_selection_capture_armed(self) -> bool:
        return self.capture_armed

    def insert_chat_selection(self, text: object) -> bool:
        self.inserted.append(str(text))
        return True

    def set_chat_error(self, message: str) -> None:
        self.errors.append(message)

    def hide_overlay(self) -> None:
        self.hidden += 1

    def unlock_overlay(self) -> bool:
        self.is_locked = False
        return True

    def show_translation(self, *_args) -> None:
        pass

    def show_text(self, *_args) -> None:
        pass


class FakeChatConfig:
    def __init__(self, capture_enabled: bool) -> None:
        self.capture_enabled = capture_enabled

    def get(self, section: str, key: str, default=None):
        if section == "ai" and key == "chat_selection_capture_enabled":
            return self.capture_enabled
        return default


def test_chat_input_auto_inserts_selection_and_undo_restores_previous_text(
    qtbot,
) -> None:
    panel = SelectionCaptureChatPanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.focus_input()

    panel.input_edit.setPlainText("请解释：")
    cursor = panel.input_edit.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    panel.input_edit.setTextCursor(cursor)
    panel.focus_input()

    assert panel.selection_capture_armed
    assert panel.insert_selected_text("Gaussian-process anchor")
    assert panel.input_edit.toPlainText() == "请解释：\nGaussian-process anchor"
    assert panel.undo_selection_button.isEnabled()

    qtbot.mouseClick(panel.undo_selection_button, Qt.MouseButton.LeftButton)

    assert panel.input_edit.toPlainText() == "请解释："
    assert not panel.undo_selection_button.isEnabled()
    assert panel.selection_capture_armed


def test_manual_edit_after_auto_insert_disables_destructive_undo(qtbot) -> None:
    panel = SelectionCaptureChatPanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.focus_input()

    assert panel.insert_selected_text("selected text")
    assert panel.undo_selection_button.isEnabled()

    panel.input_edit.insertPlainText(" plus manual edit")

    assert not panel.undo_selection_button.isEnabled()
    assert not panel.undo_last_selection_input()
    assert "plus manual edit" in panel.input_edit.toPlainText()


def test_conversational_overlay_exposes_capture_state_and_insertion(qtbot) -> None:
    window = SelectionCaptureConversationalAIOverlayWindow(
        win32_adapter=MagicMock(),
    )
    qtbot.addWidget(window)
    window.open_chat(
        source_text="paper context",
        translated_text="论文上下文",
        provider="DeepSeek",
        model="deepseek-v4-flash",
    )
    window.chat_panel.focus_input()

    assert window.is_chat_selection_capture_armed()
    assert window.insert_chat_selection("new selected phrase")
    assert "new selected phrase" in window.chat_panel.input_edit.toPlainText()
    assert window.chat_panel.undo_selection_button.isEnabled()

    window.close_chat()
    assert not window.is_chat_selection_capture_armed()


def test_chat_selection_capture_can_be_disabled_from_settings(qtbot) -> None:
    config = FakeChatConfig(capture_enabled=False)
    window = SelectionCaptureConversationalAIOverlayWindow(
        win32_adapter=MagicMock(),
        config_manager=config,
    )
    qtbot.addWidget(window)
    window.open_chat(provider="DeepSeek", model="deepseek-v4-flash")
    window.chat_panel.focus_input()

    # The UI may still have a caret, but the runtime setting vetoes routing
    # external mouse selections into the Chat input.
    assert window.chat_panel.selection_capture_armed
    assert not window.is_chat_selection_capture_armed()
    assert not window.insert_chat_selection("must not be inserted")
    assert "must not be inserted" not in window.chat_panel.input_edit.toPlainText()


def test_mouse_selection_is_routed_to_armed_chat_instead_of_translation(qapp) -> None:
    from app.ui.tray import TrayManager

    overlay = FakeCaptureOverlayManager()
    selection = FakeSelectionManager("selected paper sentence")
    tray = TrayManager(parent=qapp)
    tray.hide()
    hotkey = GlobalHotkeyManager(parent=qapp, listener_factory=lambda _mapping: None)
    controller = SelectionCaptureConversationalAIAppController(
        qapp,
        overlay_manager=overlay,
        tray_manager=tray,
        hotkey_manager=hotkey,
        selection_manager=selection,
        translation_manager=TranslationManager(provider=FakeTranslationProvider()),
        logger=MagicMock(),
    )
    submit_translation = MagicMock()
    controller._submit_translation = submit_translation
    controller._last_source_text = "existing chat context"

    try:
        controller._on_translation_triggered(
            TranslationTriggerEvent(source=MOUSE_SELECTION_SOURCE)
        )

        assert selection.calls == 1
        assert overlay.inserted == ["selected paper sentence"]
        assert overlay.hidden == 0
        assert controller._last_source_text == "existing chat context"
        submit_translation.assert_not_called()
    finally:
        controller.shutdown()


def test_mouse_selection_keeps_normal_translation_when_chat_capture_not_armed(qapp) -> None:
    from app.ui.tray import TrayManager

    overlay = FakeCaptureOverlayManager()
    overlay.capture_armed = False
    selection = FakeSelectionManager("normal selected sentence")
    tray = TrayManager(parent=qapp)
    tray.hide()
    hotkey = GlobalHotkeyManager(parent=qapp, listener_factory=lambda _mapping: None)
    controller = SelectionCaptureConversationalAIAppController(
        qapp,
        overlay_manager=overlay,
        tray_manager=tray,
        hotkey_manager=hotkey,
        selection_manager=selection,
        translation_manager=TranslationManager(provider=FakeTranslationProvider()),
        logger=MagicMock(),
    )
    submit_translation = MagicMock()
    controller._submit_translation = submit_translation

    try:
        controller._on_translation_triggered(
            TranslationTriggerEvent(source=MOUSE_SELECTION_SOURCE)
        )

        assert selection.calls == 1
        assert overlay.inserted == []
        assert controller._last_source_text == "normal selected sentence"
        submit_translation.assert_called_once_with("normal selected sentence")
    finally:
        controller.shutdown()
