"""Step12 mocked Word COM and provider-chain tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models.selection import SelectedText
from app.selection.base import SelectionProvider
from app.selection.errors import SelectionError
from app.selection.foreground import ForegroundApplicationDetector
from app.selection.manager import SelectionManager
from app.selection.word_provider import WordSelectionProvider


class FakePythonCom:
    def __init__(self) -> None:
        self.initialize_calls = 0
        self.uninitialize_calls = 0

    def CoInitialize(self) -> None:  # noqa: N802 - pythoncom API name
        self.initialize_calls += 1

    def CoUninitialize(self) -> None:  # noqa: N802 - pythoncom API name
        self.uninitialize_calls += 1


class FakeWordApplication:
    class SelectionObject:
        Text = "selected directly from Word"  # noqa: N815 - Word COM property

    Selection = SelectionObject()  # noqa: N815 - Word COM property


class ClipboardSpy(SelectionProvider):
    def __init__(self, result: SelectedText | None = None) -> None:
        self.calls = 0
        self.result = result

    def get_selected_text(self) -> SelectedText:
        self.calls += 1
        if self.result is None:
            raise AssertionError("clipboard fallback should not have been called")
        return self.result


def test_word_provider_reads_selection_without_using_clipboard() -> None:
    pythoncom = FakePythonCom()
    clipboard = ClipboardSpy()
    word = WordSelectionProvider(
        foreground_detector=lambda: True,
        com_factory=lambda: FakeWordApplication(),
        pythoncom_module=pythoncom,
    )
    manager = SelectionManager(
        word_provider=word,
        clipboard_provider=clipboard,
    )

    selected = manager.get_selected_text()

    assert selected == SelectedText(
        "selected directly from Word",
        provider="word",
    )
    assert clipboard.calls == 0
    assert pythoncom.initialize_calls == 1
    assert pythoncom.uninitialize_calls == 1


def test_non_word_foreground_skips_com_and_falls_back_to_clipboard() -> None:
    pythoncom = FakePythonCom()
    com_factory = MagicMock()
    clipboard = ClipboardSpy(SelectedText("clipboard fallback"))
    word = WordSelectionProvider(
        foreground_detector=lambda: False,
        com_factory=com_factory,
        pythoncom_module=pythoncom,
    )
    manager = SelectionManager(
        word_provider=word,
        clipboard_provider=clipboard,
    )

    selected = manager.get_selected_text()

    assert selected == SelectedText("clipboard fallback")
    com_factory.assert_not_called()
    assert clipboard.calls == 1
    assert pythoncom.initialize_calls == 0


def test_word_com_failure_is_converted_and_falls_back() -> None:
    pythoncom = FakePythonCom()
    clipboard = ClipboardSpy(SelectedText("fallback after COM failure"))

    def failing_factory():
        raise RuntimeError("COM details must stay behind the boundary")

    word = WordSelectionProvider(
        foreground_detector=lambda: True,
        com_factory=failing_factory,
        pythoncom_module=pythoncom,
    )
    manager = SelectionManager(
        word_provider=word,
        clipboard_provider=clipboard,
    )

    selected = manager.get_selected_text()

    assert selected == SelectedText("fallback after COM failure")
    assert clipboard.calls == 1
    assert pythoncom.initialize_calls == 1
    assert pythoncom.uninitialize_calls == 1


def test_word_provider_exposes_safe_com_error() -> None:
    pythoncom = FakePythonCom()

    word = WordSelectionProvider(
        foreground_detector=lambda: True,
        com_factory=lambda: (_ for _ in ()).throw(RuntimeError("secret")),
        pythoncom_module=pythoncom,
    )

    with pytest.raises(SelectionError, match="Word COM selection failed") as caught:
        word.get_selected_text()

    assert "secret" not in str(caught.value)


def test_foreground_detector_matches_word_case_insensitively() -> None:
    detector = ForegroundApplicationDetector(
        platform_name="win32",
        executable_name_reader=lambda: "WINWORD.EXE",
    )

    assert detector.executable_name() == "WINWORD.EXE"
    assert detector.is_word_foreground()
