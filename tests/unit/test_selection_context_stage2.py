"""Stage 2 regressions for frozen mouse-up context and rich native UIA capture."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pynput.mouse import Button

from app.input.mouse_selection_manager import MouseSelectionManager
from app.models.events import TranslationTriggerEvent
from app.models.selection import SelectionContext
from app.selection.errors import SelectionError
from app.selection.uia_provider import UIASelectionProvider


@dataclass
class FakeClock:
    value: float = 12.5

    def __call__(self) -> float:
        return self.value


class FakeMouseListener:
    def __init__(self, **callbacks) -> None:
        self.callbacks = callbacks

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def join(self, _timeout: float) -> None:
        return None


def _manager(qapp, *, snapshot_reader, settle_seconds: float = 0.0):
    listener = FakeMouseListener()

    def factory(**callbacks):
        listener.callbacks = callbacks
        return listener

    manager = MouseSelectionManager(
        parent=qapp,
        listener_factory=factory,
        clock=FakeClock(),
        settle_seconds=settle_seconds,
        foreground_snapshot_reader=snapshot_reader,
        foreground_executable_reader=lambda: None,
    )
    manager.start()
    return manager, listener


def _drag(listener: FakeMouseListener) -> None:
    listener.callbacks["on_click"](11, 22, Button.left, True)
    listener.callbacks["on_move"](77, 88)
    listener.callbacks["on_click"](77, 88, Button.left, False)


def test_mouse_trigger_carries_context_frozen_at_physical_release(qapp) -> None:
    manager, listener = _manager(
        qapp,
        snapshot_reader=lambda: (4321, "chrome.exe"),
    )
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)

    _drag(listener)

    assert len(events) == 1
    context = events[0].selection_context
    assert context is not None
    assert context.press_point == (11, 22)
    assert context.release_point == (77, 88)
    assert context.drag_bounds == (11, 22, 77, 88)
    assert context.foreground_hwnd == 4321
    assert context.process_name == "chrome.exe"
    assert context.captured_at == 12.5
    manager.stop()


def test_settle_window_does_not_recapture_foreground_context(qapp, qtbot) -> None:
    snapshot = [9001, "chrome.exe"]
    manager, listener = _manager(
        qapp,
        snapshot_reader=lambda: (snapshot[0], snapshot[1]),
        settle_seconds=0.05,
    )
    events: list[TranslationTriggerEvent] = []
    manager.triggered.connect(events.append)

    _drag(listener)
    snapshot[:] = [9002, "AITranslator.exe"]

    qtbot.waitUntil(lambda: len(events) == 1, timeout=500)
    context = events[0].selection_context
    assert context is not None
    assert context.foreground_hwnd == 9001
    assert context.process_name == "chrome.exe"
    manager.stop()


def test_uia_walks_from_leaf_to_document_ancestor() -> None:
    class TextRange:
        def GetText(self, _limit: int) -> str:  # noqa: N802
            return "ancestor selection"

    class TextPattern:
        def GetSelection(self):  # noqa: N802
            return [TextRange()]

    class Document:
        ControlTypeName = "DocumentControl"

        def GetTextPattern(self):  # noqa: N802
            return TextPattern()

        def GetParentControl(self):  # noqa: N802
            return None

    document = Document()

    class Leaf:
        ControlTypeName = "TextControl"

        def GetParentControl(self):  # noqa: N802
            return document

    automation = type(
        "Automation",
        (),
        {
            "ControlFromPoint": staticmethod(lambda _x, _y: Leaf()),
            "GetFocusedControl": staticmethod(lambda: None),
            "PatternId": type("PatternId", (), {"TextPattern": 10014, "TextPattern2": 10024}),
        },
    )()

    assert UIASelectionProvider._read_from_automation(
        automation,
        context=SelectionContext(release_x=20, release_y=30, process_name="chrome.exe"),
    ) == "ancestor selection"


def test_browser_context_searches_bounded_hwnd_subtree_for_document_selection() -> None:
    class TextRange:
        def GetText(self, _limit: int) -> str:  # noqa: N802
            return "browser document selection"

    class TextPattern:
        def GetSelection(self):  # noqa: N802
            return [TextRange()]

    class Toolbar:
        ControlTypeName = "ToolBarControl"

        def GetChildren(self):  # noqa: N802
            return []

    class Document:
        ControlTypeName = "DocumentControl"

        def GetTextPattern(self):  # noqa: N802
            return TextPattern()

        def GetChildren(self):  # noqa: N802
            return []

    class BrowserRoot:
        ControlTypeName = "WindowControl"

        def GetChildren(self):  # noqa: N802
            return [Toolbar(), Document()]

        def GetParentControl(self):  # noqa: N802
            return None

    root = BrowserRoot()
    automation = type(
        "Automation",
        (),
        {
            "ControlFromHandle": staticmethod(lambda hwnd: root if hwnd == 99 else None),
            "GetFocusedControl": staticmethod(lambda: None),
            "PatternId": type("PatternId", (), {"TextPattern": 10014, "TextPattern2": 10024}),
        },
    )()

    assert UIASelectionProvider._read_from_automation(
        automation,
        context=SelectionContext(
            foreground_hwnd=99,
            process_name="msedge.exe",
        ),
    ) == "browser document selection"


def test_non_browser_context_does_not_scan_unrelated_hwnd_subtree() -> None:
    class Document:
        ControlTypeName = "DocumentControl"

        def GetTextPattern(self):  # noqa: N802
            raise AssertionError("non-rich process should not scan descendants")

    class Root:
        def GetChildren(self):  # noqa: N802
            return [Document()]

        def GetParentControl(self):  # noqa: N802
            return None

    root = Root()
    automation = type(
        "Automation",
        (),
        {
            "ControlFromHandle": staticmethod(lambda _hwnd: root),
            "GetFocusedControl": staticmethod(lambda: None),
            "PatternId": type("PatternId", (), {"TextPattern": 10014, "TextPattern2": 10024}),
        },
    )()

    with pytest.raises(SelectionError):
        UIASelectionProvider._read_from_automation(
            automation,
            context=SelectionContext(
                foreground_hwnd=101,
                process_name="notepad.exe",
            ),
        )


def test_textpattern2_is_used_when_legacy_textpattern_has_no_selection() -> None:
    class EmptyPattern:
        def GetSelection(self):  # noqa: N802
            return []

    class TextRange:
        def GetText(self, _limit: int) -> str:  # noqa: N802
            return "pattern2 selection"

    class Pattern2:
        def GetSelection(self):  # noqa: N802
            return [TextRange()]

    class Control:
        def GetTextPattern(self):  # noqa: N802
            return EmptyPattern()

        def GetTextPattern2(self):  # noqa: N802
            return Pattern2()

    automation = type(
        "Automation",
        (),
        {
            "GetFocusedControl": staticmethod(lambda: Control()),
            "PatternId": type("PatternId", (), {"TextPattern": 10014, "TextPattern2": 10024}),
        },
    )()

    assert UIASelectionProvider._read_from_automation(automation) == "pattern2 selection"
