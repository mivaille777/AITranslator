from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.chat.conversation_manager import ConversationManager
from app.ai.chat_selection_controller import SelectionCaptureConversationalAIAppController
from app.input.hotkey_manager import GlobalHotkeyManager
from app.translation.fake_provider import FakeTranslationProvider
from app.translation.manager import TranslationManager


class FakeConfig:
    def __init__(self) -> None:
        self.data = {
            "ai": {
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "base_url": "https://api.deepseek.com",
            }
        }

    def get(self, section: str, key: str, default=None):
        return self.data.get(section, {}).get(key, default)

    def save(self, values):
        for section, section_values in values.items():
            self.data.setdefault(section, {}).update(section_values)
        return self.data


class FakeManagedOverlay:
    def __init__(self) -> None:
        self.is_locked = False
        self.opened: list[dict[str, object]] = []
        self.conversation_states: list[tuple[object, str]] = []
        self.model_states: list[tuple[object, str, str]] = []
        self.identities: list[tuple[str, str]] = []

    def open_chat(self, **kwargs) -> None:
        self.opened.append(kwargs)

    def set_chat_conversations(self, items, active_id: str) -> None:
        self.conversation_states.append((items, active_id))

    def set_chat_model_options(self, options, **kwargs) -> None:
        self.model_states.append(
            (options, kwargs.get("current_provider", ""), kwargs.get("current_model", ""))
        )

    def set_chat_identity(self, provider: str, model: str) -> None:
        self.identities.append((provider, model))

    def unlock_overlay(self) -> bool:
        self.is_locked = False
        return True

    def show_translation(self, *_args) -> None:
        pass

    def show_text(self, *_args) -> None:
        pass

    def hide_overlay(self) -> None:
        pass



def _controller(qapp, tmp_path):
    from app.ui.tray import TrayManager

    config = FakeConfig()
    overlay = FakeManagedOverlay()
    tray = TrayManager(parent=qapp)
    tray.hide()
    hotkey = GlobalHotkeyManager(parent=qapp, listener_factory=lambda _mapping: None)
    conversations = ConversationManager(storage_path=tmp_path / "chat_history.json")
    controller = SelectionCaptureConversationalAIAppController(
        qapp,
        overlay_manager=overlay,
        config_manager=config,
        tray_manager=tray,
        hotkey_manager=hotkey,
        translation_manager=TranslationManager(provider=FakeTranslationProvider()),
        conversation_manager=conversations,
        logger=MagicMock(),
    )
    controller._last_source_text = "selected paragraph"
    controller._last_translation_text = "选中的段落"
    return controller, overlay, config, conversations


def test_new_and_switch_conversation_updates_active_history(qapp, tmp_path) -> None:
    controller, overlay, _config, conversations = _controller(qapp, tmp_path)
    try:
        controller._on_overlay_context_action("ai_chat", None)
        first_id = conversations.active.conversation_id
        controller._on_overlay_context_action("ai_chat_new", None)
        second_id = conversations.active.conversation_id

        assert first_id != second_id
        assert len(conversations.conversations) == 2

        controller._on_overlay_context_action("ai_chat_switch", first_id)

        assert conversations.active.conversation_id == first_id
        assert overlay.conversation_states[-1][1] == first_id
    finally:
        controller.shutdown()


def test_model_selection_updates_config_and_active_conversation(qapp, tmp_path) -> None:
    controller, overlay, config, conversations = _controller(qapp, tmp_path)
    try:
        controller._on_overlay_context_action("ai_chat", None)
        controller._on_overlay_context_action(
            "ai_chat_model",
            {
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "base_url": "https://api.deepseek.com",
            },
        )

        assert config.get("ai", "model") == "deepseek-v4-pro"
        assert conversations.active.model == "deepseek-v4-pro"
        assert overlay.identities[-1] == ("DeepSeek", "deepseek-v4-pro")
    finally:
        controller.shutdown()
