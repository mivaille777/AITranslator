"""Mocked automatic mouse-selection trigger tests for Step14."""

from __future__ import annotations

from dataclasses import dataclass

from pynput.mouse import Button

from app.input.mouse_selection_manager import (
    MOUSE_SELECTION_SOURCE,
    MouseSelectionManager,
    MouseSelectionState,
)
from app.models.events import TranslationTriggerEvent


@dataclass
class FakeClock:
    value: float = 0.0

    def __call__(self) -> float:
        return self.value


class FakeMouseListener:
    def __init__(self, **callbacks) -> None:
        self.callbacks = callbacks
        self.start_count = 0
        self.stop_count = 0
        self.join_count = 0

    def start(self) -> None:
        self.start_count += 1

    def stop(self) -> None:
        self.stop_count += 1

    def join(self, _timeout: float) -> None:
        self.join_count += 1


class RecoverableMouseListener(FakeMouseListener):
    def __init__(self, **callbacks) -> None:
        super().__init__(**callbacks)
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive


def _make_manager(
    qapp,
    *,
    clock: FakeClock | None = None,
    debounce_seconds: float = 0.25,
    settle_seconds: float = 0.0,
    overlay_hit_test=None,
    foreground_executable_reader=lambda: None,
):
    listener = FakeMouseListener()

    def factory(**callbacks):
        listener.callbacks = callbacks
        return listener

    manager = MouseSelectionManager(
        parent=qapp,
        listener_factory=factory,
        clock=clock or FakeClock(),
        debounce_seconds=debounce_seconds,
        settle_seconds=settle_seconds,
        overlay_hit_test=overlay_hit_test,
        foreground_executable_reader=foreground_executable_reader,
    )
    return manager, listener


def _drag(listener: FakeMouseListener, start=(10, 10), end=(30, 10)) -> None:
    listener.callbacks["on_click"](*start, Button.left, True)
    listener.callbacks["on_move"](*end)
    listener.callbacks["on_click"](*end, Button.left, False)


def test_click_only_does_not_emit_trigger(qapp) -> None:
    manager, listener = _make_manager(qapp)
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)
    manager.start()

    listener.callbacks["on_click"](10, 10, Button.left, True)
    listener.callbacks["on_click"](10, 10, Button.left, False)

    assert events == []
    assert manager.state == MouseSelectionState.IDLE


def test_left_drag_and_release_emits_one_mouse_selection_trigger(qapp) -> None:
    manager, listener = _make_manager(qapp)
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)
    manager.start()

    _drag(listener)

    assert len(events) == 1
    assert events[0].source == MOUSE_SELECTION_SOURCE
    assert events[0].hotkey == MOUSE_SELECTION_SOURCE
    assert manager.state == MouseSelectionState.IDLE


def test_drag_from_system_screen_capture_is_ignored(qapp) -> None:
    manager, listener = _make_manager(
        qapp,
        foreground_executable_reader=lambda: r"C:\Windows\System32\SnippingTool.exe",
    )
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)
    manager.start()

    _drag(listener)

    assert events == []
    assert manager.state == MouseSelectionState.IDLE


def test_non_left_button_is_ignored(qapp) -> None:
    manager, listener = _make_manager(qapp)
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)
    manager.start()

    listener.callbacks["on_click"](10, 10, Button.right, True)
    listener.callbacks["on_move"](30, 10)
    listener.callbacks["on_click"](30, 10, Button.right, False)

    assert events == []


def test_identical_duplicate_drag_within_debounce_is_suppressed(qapp) -> None:
    clock = FakeClock(value=10.0)
    manager, listener = _make_manager(qapp, clock=clock)
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)
    manager.start()

    _drag(listener, start=(10, 10), end=(30, 10))
    clock.value = 10.1
    _drag(listener, start=(10, 10), end=(30, 10))
    clock.value = 10.3
    _drag(listener, start=(10, 10), end=(30, 10))

    assert len(events) == 2


def test_distinct_rapid_drags_are_not_lost_to_generic_debounce(qapp) -> None:
    clock = FakeClock(value=20.0)
    manager, listener = _make_manager(qapp, clock=clock)
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)
    manager.start()

    _drag(listener, start=(10, 10), end=(30, 10))
    clock.value = 20.05
    _drag(listener, start=(40, 40), end=(65, 40))
    clock.value = 20.10
    _drag(listener, start=(70, 70), end=(95, 70))

    assert len(events) == 3


def test_selection_capture_waits_for_mouse_up_settle_window(qapp, qtbot) -> None:
    manager, listener = _make_manager(qapp, settle_seconds=0.05)
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)
    manager.start()

    _drag(listener)

    assert events == []
    assert manager.state == MouseSelectionState.WAITING_DEBOUNCE
    qtbot.waitUntil(lambda: len(events) == 1, timeout=500)
    assert manager.state == MouseSelectionState.IDLE


def test_new_drag_invalidates_selection_still_waiting_to_settle(qapp, qtbot) -> None:
    manager, listener = _make_manager(qapp, settle_seconds=0.06)
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)
    manager.start()

    _drag(listener, start=(10, 10), end=(30, 10))
    # Start and finish another selection before the first settle timer fires.
    _drag(listener, start=(50, 50), end=(80, 50))

    qtbot.waitUntil(lambda: len(events) == 1, timeout=500)
    qtbot.wait(80)
    assert len(events) == 1
    assert manager.state == MouseSelectionState.IDLE


def test_drag_started_on_overlay_does_not_emit_trigger(qapp) -> None:
    manager, listener = _make_manager(
        qapp,
        overlay_hit_test=lambda x, y: x >= 0 and y >= 0,
    )
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)
    manager.start()

    _drag(listener)

    assert events == []


def test_drag_released_over_overlay_does_not_emit_trigger(qapp) -> None:
    # Model the Qt/pynput ordering race: the press hit test misses the
    # Overlay, but the moved window is under the cursor when it is released.
    manager, listener = _make_manager(
        qapp,
        overlay_hit_test=lambda x, _y: x >= 30,
    )
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)
    manager.start()

    _drag(listener, start=(10, 10), end=(30, 10))

    assert events == []


def test_start_and_stop_are_idempotent(qapp) -> None:
    manager, listener = _make_manager(qapp)

    assert manager.start()
    assert manager.start()
    manager.stop()
    manager.stop()

    assert listener.start_count == 1
    assert listener.stop_count == 1
    assert listener.join_count == 1
    assert not manager.is_running


def test_mouse_manager_reads_configured_debounce(qapp) -> None:
    class Config:
        auto_selection_debounce_seconds = 0.4

    manager = MouseSelectionManager(
        parent=qapp,
        config_manager=Config(),
        listener_factory=lambda **_callbacks: FakeMouseListener(),
    )

    assert manager.debounce_seconds == 0.4


def test_mouse_manager_defaults_to_nonzero_settle_window(qapp) -> None:
    class Config:
        auto_selection_debounce_seconds = 0.25

    manager = MouseSelectionManager(
        parent=qapp,
        config_manager=Config(),
        listener_factory=lambda **_callbacks: FakeMouseListener(),
    )

    assert manager.settle_seconds > 0


def test_dead_mouse_listener_is_restarted_by_health_check(qapp) -> None:
    listeners: list[RecoverableMouseListener] = []

    def factory(**callbacks):
        listener = RecoverableMouseListener(**callbacks)
        listeners.append(listener)
        return listener

    manager = MouseSelectionManager(
        parent=qapp,
        listener_factory=factory,
    )
    manager.start()
    listeners[0].alive = False

    assert manager.ensure_running() is True
    assert len(listeners) == 2
    assert listeners[1].start_count == 1
    manager.stop()
