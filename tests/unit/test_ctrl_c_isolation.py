"""Regression tests ensuring AITranslator never owns the user's Ctrl+C."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.infrastructure.settings import SettingsManager
from app.input.hotkey_manager import (
    DEFAULT_HOTKEY,
    GlobalHotkeyManager,
    is_reserved_copy_hotkey,
    normalize_pynput_hotkey,
)
from app.selection.clipboard_provider import ClipboardSelectionProvider


@dataclass
class FakeConfig:
    hotkey: str = "ctrl+c"
    hotkey_debounce_seconds: float = 0.25


class FakeListener:
    def __init__(self, hotkeys) -> None:
        self.hotkeys = hotkeys

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def join(self, _timeout: float) -> None:
        return None


class FakeClipboard:
    def __init__(self) -> None:
        self.text = "before capture"
        self.token = 1
        self.restore_calls = 0

    def snapshot(self):
        return self.text, self.token

    def read_text(self) -> str:
        return self.text

    def write_text(self, text: str) -> None:
        self.text = text
        self.token += 1

    def get_change_token(self) -> int:
        return self.token

    def restore(self, snapshot) -> None:
        self.restore_calls += 1
        self.text, self.token = snapshot


class FakeCopy:
    def __init__(self, clipboard: FakeClipboard) -> None:
        self.clipboard = clipboard

    def send_copy(self) -> None:
        self.clipboard.text = "selected text"
        self.clipboard.token += 1


def test_ctrl_c_is_reserved_and_cannot_be_normalized_as_translation_hotkey() -> None:
    assert is_reserved_copy_hotkey("ctrl+c") is True
    assert is_reserved_copy_hotkey("Control + C") is True
    assert is_reserved_copy_hotkey("ctrl+shift+c") is False
    with pytest.raises(ValueError, match="reserved"):
        normalize_pynput_hotkey("ctrl+c")


def test_old_ctrl_c_config_falls_back_before_listener_registration(qapp) -> None:
    listeners: list[FakeListener] = []

    def factory(hotkeys):
        listener = FakeListener(hotkeys)
        listeners.append(listener)
        return listener

    manager = GlobalHotkeyManager(
        parent=qapp,
        config_manager=FakeConfig(),
        listener_factory=factory,
    )
    manager.start()

    assert manager.hotkey == DEFAULT_HOTKEY
    assert listeners[0].hotkeys == {"<alt>+q": manager._on_hotkey}
    assert "<ctrl>+c" not in listeners[0].hotkeys
    manager.stop()


def test_settings_manager_does_not_persist_ctrl_c_binding(tmp_path) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    default_path.write_text(
        '[trigger]\nmode = "hotkey"\nhotkey = "alt+q"\ndebounce_ms = 250\n',
        encoding="utf-8",
    )
    manager = SettingsManager(default_path=default_path, user_path=user_path)

    saved = manager.save({"trigger": {"hotkey": "ctrl+c"}})

    assert saved["trigger"]["hotkey"] == "alt+q"
    assert "ctrl+c" not in user_path.read_text(encoding="utf-8").lower()


def test_newer_user_copy_is_never_overwritten_by_cleanup() -> None:
    clipboard = FakeClipboard()

    def sleeper(_duration: float) -> None:
        # The restore guard represents the small cleanup window. Simulate the
        # user pressing Ctrl+C there after AITranslator captured the selection.
        if clipboard.text == "selected text":
            clipboard.text = "user copied this later"
            clipboard.token += 1

    provider = ClipboardSelectionProvider(
        clipboard,
        FakeCopy(clipboard),
        copy_delay_seconds=0,
        restore_guard_seconds=0.03,
        sleeper=sleeper,
    )

    selected = provider.get_selected_text()

    assert selected.text == "selected text"
    assert clipboard.text == "user copied this later"
    assert clipboard.restore_calls == 0
