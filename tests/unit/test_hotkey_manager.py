"""Unit tests for the mocked global hotkey listener."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

from app.input.hotkey_manager import GlobalHotkeyManager, normalize_pynput_hotkey
from app.models.events import TranslationTriggerEvent


@dataclass
class FakeConfig:
    hotkey: str = "alt+q"
    hotkey_debounce_seconds: float = 0.25


class FakeListener:
    def __init__(self, hotkeys) -> None:
        self.hotkeys = hotkeys
        self.start_count = 0
        self.stop_count = 0
        self.join_count = 0

    def start(self) -> None:
        self.start_count += 1

    def stop(self) -> None:
        self.stop_count += 1

    def join(self, _timeout: float) -> None:
        self.join_count += 1


class RecoverableListener(FakeListener):
    def __init__(self, hotkeys) -> None:
        super().__init__(hotkeys)
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive


def test_hotkey_normalization() -> None:
    assert normalize_pynput_hotkey("Alt + Q") == "<alt>+q"
    assert normalize_pynput_hotkey("ctrl+shift+f1") == "<ctrl>+<shift>+<f1>"


def test_start_stop_are_idempotent_and_callback_emits_once_per_action(qapp) -> None:
    listener = FakeListener({})

    def create_listener(hotkeys):
        listener.hotkeys = hotkeys
        return listener

    factory = MagicMock(side_effect=create_listener)
    times = iter((10.0, 10.1, 10.4))
    manager = GlobalHotkeyManager(
        parent=qapp,
        config_manager=FakeConfig(),
        listener_factory=factory,
        clock=lambda: next(times),
    )
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)

    assert manager.start()
    assert manager.start()
    assert manager.is_running
    assert factory.call_count == 1
    assert set(listener.hotkeys) == {"<alt>+q"}

    listener.hotkeys["<alt>+q"]()
    listener.hotkeys["<alt>+q"]()
    listener.hotkeys["<alt>+q"]()

    assert len(events) == 2
    assert all(isinstance(event, TranslationTriggerEvent) for event in events)
    assert events[0].hotkey == "alt+q"

    manager.stop()
    manager.stop()
    assert not manager.is_running
    assert listener.stop_count == 1
    assert listener.join_count == 1


def test_non_target_hotkey_has_no_registered_callback(qapp) -> None:
    listener = FakeListener({})

    def create_listener(hotkeys):
        listener.hotkeys = hotkeys
        return listener

    manager = GlobalHotkeyManager(
        parent=qapp,
        config_manager=FakeConfig(),
        listener_factory=create_listener,
    )
    manager.start()

    assert "<ctrl>+q" not in listener.hotkeys
    assert "<alt>+q" in listener.hotkeys

    # The fake listener intentionally does not receive a callback for any
    # non-target combination, matching pynput's registered hotkey map.
    manager.stop()


def test_reconfigure_reads_updated_config_and_restarts_listener(qapp) -> None:
    config = FakeConfig()
    listeners: list[FakeListener] = []

    def create_listener(hotkeys):
        listener = FakeListener(hotkeys)
        listeners.append(listener)
        return listener

    manager = GlobalHotkeyManager(
        parent=qapp,
        config_manager=config,
        listener_factory=create_listener,
    )
    manager.start()
    config.hotkey = "ctrl+shift+t"
    config.hotkey_debounce_seconds = 0.5

    assert manager.reconfigure()
    assert manager.hotkey == "ctrl+shift+t"
    assert manager.pynput_hotkey == "<ctrl>+<shift>+t"
    assert manager.is_running
    assert len(listeners) == 2
    assert listeners[-1].start_count == 1
    assert listeners[-1].hotkeys == {"<ctrl>+<shift>+t": manager._on_hotkey}

    manager.stop()


def test_dead_listener_is_restarted_by_health_check(qapp) -> None:
    listeners: list[RecoverableListener] = []

    def create_listener(hotkeys):
        listener = RecoverableListener(hotkeys)
        listeners.append(listener)
        return listener

    manager = GlobalHotkeyManager(
        parent=qapp,
        config_manager=FakeConfig(),
        listener_factory=create_listener,
    )
    manager.start()
    listeners[0].alive = False

    assert manager.ensure_running() is True
    assert len(listeners) == 2
    assert listeners[1].start_count == 1
    manager.stop()
