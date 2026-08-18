from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.agent_workspace_controller import AgentWorkspaceAppController
from app.ai.chat.conversation_manager import ConversationManager
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
            },
            "translation": {
                "source_language": "auto",
                "target_language": "zh-CN",
            },
        }

    def get(self, section: str, key: str, default=None):
        return self.data.get(section, {}).get(key, default)

    def save(self, values):
        for section, section_values in values.items():
            self.data.setdefault(section, {}).update(section_values)
        return self.data


class FakeAgentOverlay:
    def __init__(self) -> None:
        self.is_locked = False
        self.chat_open = False
        self.agent_mode = False
        self.opened: list[dict[str, object]] = []
        self.appended: list[tuple[object, str]] = []
        self.agent_replies: list[str] = []
        self.translation_views: list[tuple[object, ...]] = []

    def is_chat_open(self) -> bool:
        return self.chat_open

    def open_chat(self, **kwargs) -> None:
        self.chat_open = True
        self.opened.append(kwargs)

    def close_chat(self) -> None:
        self.chat_open = False

    def show_translation(self, *args) -> None:
        self.chat_open = False
        self.translation_views.append(args)

    def enter_agent_translation_mode(self, assistant_message="") -> None:
        self.agent_mode = True
        self.chat_open = False
        self.agent_replies.append(str(assistant_message))

    def leave_agent_translation_mode(self) -> None:
        self.agent_mode = False

    def set_agent_workspace_reply(self, text, *, streaming=False) -> None:
        self.agent_replies.append(str(text))

    def set_agent_workspace_busy(self, _busy: bool) -> None:
        pass

    def set_agent_workspace_error(self, message) -> None:
        self.agent_replies.append(str(message))

    def append_chat_message(self, role, text: str) -> None:
        self.appended.append((role, str(text)))

    def set_chat_conversations(self, *_args) -> None:
        pass

    def set_chat_model_options(self, *_args, **_kwargs) -> None:
        pass

    def set_chat_identity(self, *_args) -> None:
        pass

    def set_chat_busy(self, *_args) -> None:
        pass

    def cancel_chat_stream(self, *_args) -> None:
        pass

    def clear_chat(self) -> None:
        pass

    def set_languages(self, *_args) -> None:
        pass

    def unlock_overlay(self) -> bool:
        self.is_locked = False
        return True

    def show_text(self, *_args) -> None:
        pass

    def hide_overlay(self) -> None:
        pass


def _controller(qapp, tmp_path):
    from app.ui.tray import TrayManager

    config = FakeConfig()
    overlay = FakeAgentOverlay()
    tray = TrayManager(parent=qapp)
    tray.hide()
    hotkey = GlobalHotkeyManager(parent=qapp, listener_factory=lambda _mapping: None)
    conversations = ConversationManager(storage_path=tmp_path / "agent_history.sqlite3")
    controller = AgentWorkspaceAppController(
        qapp,
        overlay_manager=overlay,
        config_manager=config,
        tray_manager=tray,
        hotkey_manager=hotkey,
        translation_manager=TranslationManager(provider=FakeTranslationProvider()),
        conversation_manager=conversations,
        logger=MagicMock(),
    )
    return controller, overlay, conversations


def test_agent_confirms_translation_workspace_and_returns_to_same_chat(qapp, tmp_path) -> None:
    controller, overlay, conversations = _controller(qapp, tmp_path)
    try:
        controller._on_overlay_context_action("ai_chat", None)
        assert overlay.chat_open is True

        controller._submit_chat_message("我要你帮我翻译东西")
        assert controller.agent_translation_active is False
        assert overlay.agent_mode is False
        assert "切换到翻译界面" in conversations.active.messages[-1].content

        controller._submit_chat_message("确定")
        assert controller.agent_translation_active is True
        assert overlay.agent_mode is True
        assert overlay.chat_open is False
        assert overlay.translation_views
        assert "已切换到翻译界面" in overlay.agent_replies[-1]

        controller._on_overlay_context_action("agent_workspace_send", "翻译完了")
        assert controller.agent_translation_active is False
        assert overlay.agent_mode is False
        assert overlay.chat_open is True
        assert "翻译任务已结束" in conversations.active.messages[-1].content
        assert overlay.opened[-1]["messages"] == tuple(conversations.active.messages)
    finally:
        controller.shutdown()
