"""Regression coverage for automatic selection without synthetic Ctrl+C."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.selection import SelectedText, SelectionContext
from app.selection.errors import SelectionError
from app.selection.manager import SelectionManager
from app.selection.uia_provider import UIASelectionProvider


class FailingProvider:
    def __init__(self, message: str = "unavailable") -> None:
        self.calls = 0
        self.message = message

    def get_selected_text(self) -> SelectedText:
        self.calls += 1
        raise SelectionError(self.message)


class ContextNativeProvider:
    def __init__(self, text: str = "native selection") -> None:
        self.calls = 0
        self.contexts: list[SelectionContext | None] = []
        self.text = text

    def get_selected_text(self) -> SelectedText:
        self.calls += 1
        return SelectedText(self.text, provider="uia")

    def get_selected_text_with_context(
        self,
        context: SelectionContext | None,
    ) -> SelectedText:
        self.calls += 1
        self.contexts.append(context)
        return SelectedText(self.text, provider="uia")


class ForbiddenClipboardProvider:
    def __init__(self) -> None:
        self.calls = 0

    def get_selected_text(self) -> SelectedText:
        self.calls += 1
        raise AssertionError("automatic native selection must never reach clipboard")


def test_native_selection_never_enters_clipboard_fallback() -> None:
    word = FailingProvider("not Word")
    uia = ContextNativeProvider()
    clipboard = ForbiddenClipboardProvider()
    manager = SelectionManager(
        word_provider=word,
        uia_provider=uia,
        clipboard_provider=clipboard,
    )
    context = SelectionContext(
        release_x=320,
        release_y=240,
        foreground_hwnd=1234,
        process_name="chrome.exe",
    )

    selected = manager.get_selected_text_native(context=context)

    assert selected == SelectedText("native selection", provider="uia")
    assert word.calls == 1
    assert uia.calls == 1
    assert uia.contexts == [context]
    assert clipboard.calls == 0


def test_native_selection_failure_still_never_calls_clipboard() -> None:
    word = FailingProvider("not Word")
    uia = FailingProvider("UIA unsupported")
    clipboard = ForbiddenClipboardProvider()
    manager = SelectionManager(
        word_provider=word,
        uia_provider=uia,
        clipboard_provider=clipboard,
    )

    with pytest.raises(SelectionError, match="UIA unsupported"):
        manager.get_selected_text_native(
            context=SelectionContext(release_x=10, release_y=20)
        )

    assert clipboard.calls == 0


def test_full_selection_path_keeps_legacy_clipboard_compatibility() -> None:
    word = FailingProvider("not Word")
    uia = FailingProvider("UIA unsupported")

    class ClipboardProvider:
        def __init__(self) -> None:
            self.calls = 0

        def get_selected_text(self) -> SelectedText:
            self.calls += 1
            return SelectedText("legacy fallback", provider="clipboard")

    clipboard = ClipboardProvider()
    manager = SelectionManager(
        word_provider=word,
        uia_provider=uia,
        clipboard_provider=clipboard,
    )

    assert manager.get_selected_text() == SelectedText(
        "legacy fallback",
        provider="clipboard",
    )
    assert clipboard.calls == 1


def test_uia_prefers_control_at_captured_release_point() -> None:
    class TextRange:
        def GetText(self, _max_length: int) -> str:  # noqa: N802
            return "selected from point"

    class TextPattern:
        def GetSelection(self):  # noqa: N802
            return [TextRange()]

    class Control:
        def GetTextPattern(self):  # noqa: N802
            return TextPattern()

    point_control = Control()
    focused_control = SimpleNamespace()
    calls: list[tuple[int, int]] = []
    automation = SimpleNamespace(
        ControlFromPoint=lambda x, y: calls.append((x, y)) or point_control,
        GetFocusedControl=lambda: focused_control,
        PatternId=SimpleNamespace(TextPattern=10014),
    )
    context = SelectionContext(release_x=77, release_y=88)

    text = UIASelectionProvider._read_from_automation(
        automation,
        context=context,
    )

    assert text == "selected from point"
    assert calls == [(77, 88)]


def test_uia_falls_back_to_focused_control_when_point_has_no_text_pattern() -> None:
    class TextRange:
        def GetText(self, _max_length: int) -> str:  # noqa: N802
            return "focused selection"

    class TextPattern:
        def GetSelection(self):  # noqa: N802
            return [TextRange()]

    class FocusedControl:
        def GetTextPattern(self):  # noqa: N802
            return TextPattern()

    automation = SimpleNamespace(
        ControlFromPoint=lambda _x, _y: SimpleNamespace(),
        GetFocusedControl=lambda: FocusedControl(),
        PatternId=SimpleNamespace(TextPattern=10014),
    )

    assert UIASelectionProvider._read_from_automation(
        automation,
        context=SelectionContext(release_x=10, release_y=20),
    ) == "focused selection"
