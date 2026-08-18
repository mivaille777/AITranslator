"""Mocked UI Automation provider and fallback-chain tests for Step13."""

from __future__ import annotations

import sys
import threading
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.selection import SelectedText
from app.selection.base import SelectionProvider
from app.selection.errors import SelectionError
from app.selection.manager import SelectionManager
from app.selection.uia_provider import UIASelectionProvider


def test_uia_provider_returns_injected_selection() -> None:
    provider = UIASelectionProvider(
        timeout_seconds=0.1,
        automation_reader=lambda: "selected by UI Automation",
    )

    assert provider.get_selected_text() == SelectedText(
        "selected by UI Automation",
        provider="uia",
    )


def test_uia_provider_reads_focused_text_pattern(monkeypatch) -> None:
    class FakeTextRange:
        def GetText(self, _max_length: int = -1) -> str:  # noqa: N802
            return "selected from a focused control"

    class FakeTextPattern:
        def GetSelection(self):  # noqa: N802
            return [FakeTextRange()]

    class FakeControl:
        def GetTextPattern(self):  # noqa: N802
            return FakeTextPattern()

    automation = ModuleType("uiautomation")
    automation.GetFocusedControl = lambda: FakeControl()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uiautomation", automation)

    selected = UIASelectionProvider(timeout_seconds=0.1).get_selected_text()

    assert selected.text == "selected from a focused control"
    assert selected.provider == "uia"


def test_uia_provider_converts_reader_errors_without_exposing_details() -> None:
    provider = UIASelectionProvider(
        automation_reader=lambda: (_ for _ in ()).throw(
            RuntimeError("private UIA/COM details")
        ),
    )

    with pytest.raises(SelectionError, match="UIA selection failed") as caught:
        provider.get_selected_text()

    assert "private UIA/COM details" not in str(caught.value)


def test_uia_provider_timeout_is_bounded_and_worker_is_daemon() -> None:
    started = threading.Event()
    release = threading.Event()

    def slow_reader() -> str:
        started.set()
        release.wait(1.0)
        return "late result"

    provider = UIASelectionProvider(
        timeout_seconds=0.02,
        automation_reader=slow_reader,
    )

    start = time.monotonic()
    with pytest.raises(SelectionError, match="timed out"):
        provider.get_selected_text()
    elapsed = time.monotonic() - start
    release.set()

    assert started.wait(0.2)
    assert elapsed < 0.2


class FailingProvider(SelectionProvider):
    def __init__(self, message: str = "provider unavailable") -> None:
        self.message = message

    def get_selected_text(self) -> SelectedText:
        raise SelectionError(self.message)


class FixedProvider(SelectionProvider):
    def __init__(self, selected: SelectedText) -> None:
        self.selected = selected
        self.calls = 0

    def get_selected_text(self) -> SelectedText:
        self.calls += 1
        return self.selected


def test_selection_manager_uses_word_uia_clipboard_order() -> None:
    clipboard = FixedProvider(SelectedText("clipboard result"))
    uia = FixedProvider(SelectedText("uia result", provider="uia"))

    selected = SelectionManager(
        word_provider=FailingProvider("not Word"),
        uia_provider=uia,
        clipboard_provider=clipboard,
    ).get_selected_text()

    assert selected == SelectedText("uia result", provider="uia")
    assert uia.calls == 1
    assert clipboard.calls == 0


def test_selection_manager_falls_back_to_clipboard_after_uia_failure() -> None:
    logger = MagicMock()
    clipboard = FixedProvider(SelectedText("clipboard fallback"))

    selected = SelectionManager(
        word_provider=FailingProvider("not Word"),
        uia_provider=FailingProvider("TextPattern unsupported"),
        clipboard_provider=clipboard,
        logger=logger,
    ).get_selected_text()

    assert selected == SelectedText("clipboard fallback")
    logger.info.assert_any_call(
        "selection_provider_used provider=%s",
        "clipboard",
    )


def test_selection_manager_uses_configured_uia_timeout() -> None:
    class Config:
        selection_uia_timeout_seconds = 0.123

    manager = SelectionManager(
        word_provider=FailingProvider(),
        clipboard_provider=FixedProvider(SelectedText("fallback")),
        config_manager=Config(),
    )

    assert isinstance(manager.providers[1], UIASelectionProvider)
    assert manager.providers[1].timeout_seconds == pytest.approx(0.123)


def test_uia_provider_falls_back_from_missing_text_pattern(monkeypatch) -> None:
    class FakeControl:
        def GetTextPattern(self):  # noqa: N802
            return None

    automation = ModuleType("uiautomation")
    automation.GetFocusedControl = lambda: FakeControl()  # type: ignore[attr-defined]
    automation.PatternId = SimpleNamespace(TextPattern=10014)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uiautomation", automation)

    with pytest.raises(SelectionError, match="TextPattern"):
        UIASelectionProvider(timeout_seconds=0.1).get_selected_text()
