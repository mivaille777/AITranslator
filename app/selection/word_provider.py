"""Microsoft Word COM selection provider with safe clipboard fallback support."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from app.models.selection import (
    DocumentIdentity,
    ReadingSelection,
    SelectedText,
    SelectionContext,
)
from app.selection.base import SelectionProvider
from app.selection.errors import SelectionError
from app.selection.foreground import ForegroundApplicationDetector

# Word WdInformation.wdActiveEndAdjustedPageNumber.  Keep the numeric constant
# local so importing this module never requires the Word type library.
WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER = 1


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

        result = self._capture(reading=False)
        if isinstance(result, SelectedText):
            return result
        return result.selected_text

    def get_reading_selection(self) -> ReadingSelection:
        """Return Word text plus reliable local document identity metadata."""

        result = self._capture(reading=True)
        if isinstance(result, ReadingSelection):
            return result
        return ReadingSelection(text=result.text, provider=result.provider)

    def get_reading_selection_with_context(
        self,
        _context: SelectionContext | None,
    ) -> ReadingSelection:
        """Word identity comes from COM; mouse routing context adds no metadata."""

        return self.get_reading_selection()

    def _capture(self, *, reading: bool) -> SelectedText | ReadingSelection:
        if not self._is_word_foreground():
            raise SelectionError("Word is not the foreground application")

        pythoncom: Any | None = None
        com_initialized = False
        try:
            pythoncom = self._load_pythoncom()
            pythoncom.CoInitialize()
            com_initialized = True

            word_application = self._com_factory()
            selection = word_application.Selection
            text = str(selection.Text)
            if not text.strip():
                raise SelectionError("Word selection is empty")

            if not reading:
                return SelectedText(text=text, provider="word")

            return ReadingSelection(
                text=text,
                provider="word",
                document=self._document_identity(word_application, selection),
            )
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

    @classmethod
    def _document_identity(cls, word_application: Any, selection: Any) -> DocumentIdentity:
        document = cls._safe_attribute(word_application, "ActiveDocument")
        title = cls._safe_text(cls._safe_attribute(document, "Name"))
        full_name = cls._safe_text(cls._safe_attribute(document, "FullName"))
        resource_path = full_name if cls._looks_like_local_path(full_name, title) else ""
        return DocumentIdentity(
            source_kind="word",
            resource_title=title,
            resource_path=resource_path,
            application="winword.exe",
            page_number=cls._page_number(selection),
        )

    @staticmethod
    def _safe_attribute(value: Any, name: str) -> Any | None:
        if value is None:
            return None
        try:
            return getattr(value, name, None)
        except Exception:
            return None

    @staticmethod
    def _safe_text(value: object) -> str:
        try:
            return str(value or "").replace("\x00", "").strip()
        except Exception:
            return ""

    @staticmethod
    def _looks_like_local_path(value: str, title: str) -> bool:
        if not value or value == title:
            return False
        normalized = value.replace("/", "\\")
        return "\\" in normalized or (
            len(normalized) >= 3
            and normalized[1] == ":"
            and normalized[2] == "\\"
        )

    @staticmethod
    def _page_number(selection: Any) -> int | None:
        try:
            information = getattr(selection, "Information")
        except Exception:
            return None

        value: Any | None = None
        if callable(information):
            try:
                value = information(WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER)
            except Exception:
                value = None
        if value is None:
            try:
                value = information[WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER]
            except Exception:
                return None
        try:
            page = int(value)
        except (TypeError, ValueError):
            return None
        return page if page > 0 else None

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


__all__ = ["WD_ACTIVE_END_ADJUSTED_PAGE_NUMBER", "WordSelectionProvider"]
