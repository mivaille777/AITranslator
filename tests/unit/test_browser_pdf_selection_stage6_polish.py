from __future__ import annotations

import pytest

from app.models.selection import SelectedText, SelectionContext
from app.selection.browser_pdf_provider import BrowserPdfSelectionProvider
from app.selection.errors import SelectionError
from app.selection.manager import SelectionManager


class SequencedUIA:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def get_selected_text_with_context(self, _context):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def get_selected_text(self):
        return self.get_selected_text_with_context(None)


class FailingProvider:
    def __init__(self):
        self.calls = 0

    def get_selected_text(self):
        self.calls += 1
        raise SelectionError("unavailable")

    def get_selected_text_with_context(self, _context):
        return self.get_selected_text()


class ClipboardProbe:
    def __init__(self):
        self.calls = 0

    def get_selected_text(self):
        self.calls += 1
        return SelectedText("clipboard text", provider="clipboard")


def chrome_context() -> SelectionContext:
    return SelectionContext(
        press_x=100,
        press_y=100,
        release_x=180,
        release_y=120,
        foreground_hwnd=123,
        process_name="chrome.exe",
    )


def test_browser_pdf_provider_retries_late_accessibility_selection() -> None:
    uia = SequencedUIA(
        [
            SelectionError("not settled"),
            SelectionError("still settling"),
            SelectedText("PDF selected text", provider="uia"),
        ]
    )
    sleeps: list[float] = []
    provider = BrowserPdfSelectionProvider(
        uia_provider=uia,
        retry_delays_seconds=(0.0, 0.05, 0.12),
        sleeper=sleeps.append,
    )

    selected = provider.get_selected_text_with_context(chrome_context())

    assert selected.text == "PDF selected text"
    assert selected.provider == "browser_pdf_uia"
    assert uia.calls == 3
    assert sleeps == [0.05, 0.12]


def test_browser_pdf_provider_rejects_non_browser_without_touching_uia() -> None:
    uia = SequencedUIA([SelectedText("should not run", provider="uia")])
    provider = BrowserPdfSelectionProvider(uia_provider=uia, sleeper=lambda _delay: None)

    with pytest.raises(SelectionError):
        provider.get_selected_text_with_context(
            SelectionContext(process_name="notepad.exe", release_x=10, release_y=20)
        )

    assert uia.calls == 0


def test_native_manager_uses_pdf_tier_without_clipboard_fallback() -> None:
    word = FailingProvider()
    generic_uia = FailingProvider()
    clipboard = ClipboardProbe()
    pdf_uia = SequencedUIA([SelectedText("local PDF selection", provider="uia")])
    pdf = BrowserPdfSelectionProvider(
        uia_provider=pdf_uia,
        retry_delays_seconds=(0.0,),
        sleeper=lambda _delay: None,
    )
    manager = SelectionManager(
        word_provider=word,
        browser_pdf_provider=pdf,
        uia_provider=generic_uia,
        clipboard_provider=clipboard,
    )

    selected = manager.get_selected_text_native(context=chrome_context())

    assert selected.text == "local PDF selection"
    assert selected.provider == "browser_pdf_uia"
    assert clipboard.calls == 0
    assert generic_uia.calls == 0


def test_explicit_uia_injection_keeps_legacy_native_order() -> None:
    word = FailingProvider()
    uia = SequencedUIA([SelectedText("legacy injected UIA", provider="uia")])
    manager = SelectionManager(
        word_provider=word,
        uia_provider=uia,
        clipboard_provider=ClipboardProbe(),
    )

    selected = manager.get_selected_text_native(context=chrome_context())

    assert selected.provider == "uia"
    assert selected.text == "legacy injected UIA"
    assert uia.calls == 1
