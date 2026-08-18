"""Microsoft Word COM selection provider with safe clipboard fallback support."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from app.models.selection import SelectedText
from app.selection.base import SelectionProvider
from app.selection.errors import SelectionError
from app.selection.foreground import ForegroundApplicationDetector


class WordSelectionProvider(SelectionProvider):
    """Read Word's active Selection.Text without touching the clipboard."""

    def __init__(
        self,
        *,
        foreground_detector: Callable[[], bool] | Any | None = None,
        com_factory: Callable[[], Any] | None = None,
        pythoncom_module: Any | None = None,
    ) -> None:
        detector = foreground_detector or ForegroundApplicationDetector()
        self._foreground_detector = detector
        self._com_factory = com_factory or self._get_active_word_application
        self._pythoncom_module = pythoncom_module

    def get_selected_text(self) -> SelectedText:
        """Return Word selection or raise a safe, recoverable SelectionError."""

        if not self._is_word_foreground():
            raise SelectionError("Word is not the foreground application")

        pythoncom: Any | None = None
        com_initialized = False
        try:
            pythoncom = self._load_pythoncom()
            pythoncom.CoInitialize()
            com_initialized = True

            word_application = self._com_factory()
            selected_text = word_application.Selection.Text
            text = str(selected_text)
            if not text.strip():
                raise SelectionError("Word selection is empty")
            return SelectedText(text=text, provider="word")
        except SelectionError:
            raise
        except Exception as exc:
            error = SelectionError("Word COM selection failed")
            error.__cause__ = exc
            raise error
        finally:
            if com_initialized and pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    # Cleanup must not replace a successful selection or the
                    # original safe SelectionError.
                    pass

    def _is_word_foreground(self) -> bool:
        """Evaluate an injected predicate or detector object safely."""

        try:
            if callable(self._foreground_detector):
                return bool(self._foreground_detector())
            return bool(self._foreground_detector.is_word_foreground())
        except Exception as exc:
            error = SelectionError("Word foreground detection failed")
            error.__cause__ = exc
            raise error

    def _load_pythoncom(self) -> Any:
        if self._pythoncom_module is not None:
            return self._pythoncom_module
        return importlib.import_module("pythoncom")

    @staticmethod
    def _get_active_word_application() -> Any:
        """Get the running Word instance without launching a new one."""

        win32_client = importlib.import_module("win32com.client")
        return win32_client.GetActiveObject("Word.Application")


__all__ = ["WordSelectionProvider"]
