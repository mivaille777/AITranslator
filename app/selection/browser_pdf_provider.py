"""Zero-keyboard accessibility fallback for Chromium/desktop PDF selections."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from time import sleep

from app.models.selection import (
    DocumentIdentity,
    ReadingSelection,
    SelectedText,
    SelectionContext,
)
from app.selection.base import SelectionProvider
from app.selection.errors import SelectionError
from app.selection.reading_context import normalize_application_name
from app.selection.uia_provider import UIASelectionProvider

BROWSER_PDF_PROCESS_NAMES = frozenset(
    {
        "chrome.exe",
        "msedge.exe",
        "brave.exe",
        "vivaldi.exe",
        "opera.exe",
        "firefox.exe",
    }
)
DEFAULT_BROWSER_PDF_RETRY_DELAYS_SECONDS = (0.0, 0.055, 0.12)
DEFAULT_BROWSER_PDF_UIA_TIMEOUT_SECONDS = 0.18


class BrowserPdfSelectionProvider(SelectionProvider):
    """Retry native UIA briefly after browser PDF mouse-up.

    Chromium's built-in PDF viewer does not expose its selection through a
    normal webpage content script. Its accessibility selection also tends to
    settle later than ordinary DOM text. This provider therefore runs only for
    browser foreground processes and performs a very small, bounded sequence
    of UIA reads. It never writes the clipboard and never synthesizes keys.

    The provider intentionally also accepts ordinary browser accessibility
    selections. In production it is used only after the DOM Selection Bridge
    misses, making it a safe browser/PDF accessibility tier rather than a
    competitor to the richer DOM context path.
    """

    def __init__(
        self,
        *,
        uia_provider: UIASelectionProvider | SelectionProvider | None = None,
        retry_delays_seconds: Sequence[float] = DEFAULT_BROWSER_PDF_RETRY_DELAYS_SECONDS,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self._uia_provider = uia_provider or UIASelectionProvider(
            timeout_seconds=DEFAULT_BROWSER_PDF_UIA_TIMEOUT_SECONDS
        )
        self._retry_delays = tuple(max(0.0, float(value)) for value in retry_delays_seconds)
        self._sleeper = sleeper

    @staticmethod
    def supports_context(context: SelectionContext | None) -> bool:
        if context is None or not context.process_name:
            return False
        process_name = (
            str(context.process_name)
            .replace("\\", "/")
            .rsplit("/", 1)[-1]
            .casefold()
        )
        return process_name in BROWSER_PDF_PROCESS_NAMES

    def get_selected_text(self) -> SelectedText:
        raise SelectionError("browser/PDF selection requires frozen context")

    def get_selected_text_with_context(
        self,
        context: SelectionContext | None,
    ) -> SelectedText:
        if not self.supports_context(context):
            raise SelectionError("browser/PDF accessibility provider not applicable")

        last_error: SelectionError | None = None
        delays = self._retry_delays or (0.0,)
        for delay in delays:
            if delay > 0:
                self._sleeper(delay)
            try:
                capture = getattr(self._uia_provider, "get_selected_text_with_context", None)
                if callable(capture):
                    selected = capture(context)
                else:
                    selected = self._uia_provider.get_selected_text()
            except SelectionError as exc:
                last_error = exc
                continue
            except Exception as exc:
                error = SelectionError("browser/PDF accessibility selection failed")
                error.__cause__ = exc
                last_error = error
                continue

            text = str(getattr(selected, "text", "") or "")
            if text.strip():
                return SelectedText(text=text, provider="browser_pdf_uia")
            last_error = SelectionError("browser/PDF accessibility selection is empty")

        if last_error is not None:
            raise last_error
        raise SelectionError("browser/PDF accessibility selection unavailable")

    def get_reading_selection(self) -> ReadingSelection:
        raise SelectionError("browser/PDF reading selection requires frozen context")

    def get_reading_selection_with_context(
        self,
        context: SelectionContext | None,
    ) -> ReadingSelection:
        """Return weak browser identity without inventing a URL or document title.

        This tier can represent either a built-in PDF viewer or an ordinary
        browser accessibility fallback.  Without DOM/extension evidence there
        is no reliable URL/PDF discriminator, so Stage 6C deliberately records
        only the browser source family and executable name.
        """

        selected = self.get_selected_text_with_context(context)
        return ReadingSelection(
            text=selected.text,
            provider=selected.provider,
            document=DocumentIdentity(
                source_kind="browser",
                application=normalize_application_name(
                    context.process_name if context is not None else ""
                ),
            ),
        )


__all__ = [
    "BROWSER_PDF_PROCESS_NAMES",
    "BrowserPdfSelectionProvider",
    "DEFAULT_BROWSER_PDF_RETRY_DELAYS_SECONDS",
    "DEFAULT_BROWSER_PDF_UIA_TIMEOUT_SECONDS",
]
