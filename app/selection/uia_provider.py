"""Windows UI Automation provider for reading the focused text selection."""

from __future__ import annotations

import importlib
import math
import threading
from collections.abc import Callable
from typing import Any

from app.models.selection import SelectedText
from app.selection.base import SelectionProvider
from app.selection.errors import SelectionError

DEFAULT_UIA_TIMEOUT_SECONDS = 0.25


class UIASelectionProvider(SelectionProvider):
    """Read a focused UI Automation TextPattern with a bounded wait.

    The ``uiautomation`` package is imported only inside the worker. This
    keeps the provider importable in tests and lets an unavailable or broken
    UIA control fall through to the next selection provider. A timed-out UIA
    call cannot be cancelled safely, so the worker is deliberately daemonized
    and the application waits only for the configured interval.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_UIA_TIMEOUT_SECONDS,
        automation_reader: Callable[[], str | SelectedText] | None = None,
    ) -> None:
        try:
            timeout = float(timeout_seconds)
            if not math.isfinite(timeout):
                raise ValueError("timeout must be finite")
        except (TypeError, ValueError):
            timeout = DEFAULT_UIA_TIMEOUT_SECONDS
        self.timeout_seconds = max(0.001, timeout)
        self._automation_reader = (
            automation_reader
            if automation_reader is not None
            else self._read_with_uiautomation
        )

    def get_selected_text(self) -> SelectedText:
        """Return the focused TextPattern selection or a safe SelectionError."""

        result: list[str | SelectedText] = []
        errors: list[Exception] = []
        completed = threading.Event()

        def worker() -> None:
            try:
                result.append(self._automation_reader())
            except Exception as exc:  # UIA and COM exceptions vary by control.
                errors.append(exc)
            finally:
                completed.set()

        thread = threading.Thread(
            target=worker,
            name="uia-selection-reader",
            daemon=True,
        )
        try:
            thread.start()
            if not completed.wait(self.timeout_seconds):
                raise SelectionError("UIA selection timed out")
        except SelectionError:
            raise
        except Exception as exc:
            error = SelectionError("UIA selection failed")
            error.__cause__ = exc
            raise error

        if errors:
            error = errors[0]
            if isinstance(error, SelectionError):
                raise error
            safe_error = SelectionError("UIA selection failed")
            safe_error.__cause__ = error
            raise safe_error

        if not result:
            raise SelectionError("UIA selection unavailable")

        try:
            selected = result[0]
            text = (
                selected.text
                if isinstance(selected, SelectedText)
                else str(selected)
            )
            if not text.strip():
                raise SelectionError("UIA selection is empty")
            return SelectedText(text=text, provider="uia")
        except SelectionError:
            raise
        except Exception as exc:
            error = SelectionError("UIA selection failed")
            error.__cause__ = exc
            raise error

    @staticmethod
    def _read_with_uiautomation() -> str:
        """Read the current selection through the focused UIA TextPattern."""

        automation = importlib.import_module("uiautomation")

        initializer_factory = getattr(
            automation,
            "UIAutomationInitializerInThread",
            None,
        )
        if callable(initializer_factory):
            # uiautomation requires COM/UIA initialization in every thread
            # that creates or uses Controls and TextPatterns. Keep all UIA
            # objects inside this context; none cross back to the GUI thread.
            with initializer_factory():
                return UIASelectionProvider._read_from_automation(automation)
        return UIASelectionProvider._read_from_automation(automation)

    @staticmethod
    def _read_from_automation(automation: Any) -> str:
        """Read a selection from an already initialized UIA context."""

        get_focused_control = getattr(automation, "GetFocusedControl", None)
        if not callable(get_focused_control):
            raise SelectionError("UIA focused control is unavailable")

        control = get_focused_control()
        if control is None:
            raise SelectionError("UIA focused control is unavailable")

        text_pattern = UIASelectionProvider._get_text_pattern(
            automation,
            control,
        )
        if text_pattern is None:
            raise SelectionError("UIA TextPattern is unsupported")

        get_selection = getattr(text_pattern, "GetSelection", None)
        if not callable(get_selection):
            raise SelectionError("UIA TextPattern selection is unsupported")

        ranges = get_selection()
        if ranges is None:
            raise SelectionError("UIA text selection is unavailable")
        try:
            ranges = list(ranges)
        except TypeError:
            ranges = [ranges]
        if not ranges:
            raise SelectionError("UIA text selection is unavailable")

        text_parts: list[str] = []
        for text_range in ranges:
            get_text = getattr(text_range, "GetText", None)
            if not callable(get_text):
                raise SelectionError("UIA text range is unsupported")
            try:
                value = get_text(-1)
            except TypeError:
                # Accommodate UIA wrappers that expose GetText() without the
                # optional max-length argument.
                value = get_text()
            if value is not None:
                text_parts.append(str(value))

        text = "".join(text_parts)
        if not text.strip():
            raise SelectionError("UIA selection is empty")
        return text

    @staticmethod
    def _get_text_pattern(automation: Any, control: Any) -> Any | None:
        """Return TextPattern when the focused control supports it."""

        get_text_pattern = getattr(control, "GetTextPattern", None)
        if callable(get_text_pattern):
            try:
                pattern = get_text_pattern()
            except Exception:
                pattern = None
            if pattern is not None:
                return pattern

        get_pattern = getattr(control, "GetPattern", None)
        pattern_id_container = getattr(automation, "PatternId", None)
        pattern_id = getattr(pattern_id_container, "TextPattern", 10014)
        if callable(get_pattern):
            try:
                return get_pattern(pattern_id)
            except Exception:
                return None
        return None


__all__ = ["DEFAULT_UIA_TIMEOUT_SECONDS", "UIASelectionProvider"]
