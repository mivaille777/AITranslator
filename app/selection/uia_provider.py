"""Windows UI Automation provider for reading the focused text selection."""

from __future__ import annotations

import importlib
import math
import threading
from collections.abc import Callable
from typing import Any

from app.models.selection import SelectedText, SelectionContext
from app.selection.base import SelectionProvider
from app.selection.errors import SelectionError

DEFAULT_UIA_TIMEOUT_SECONDS = 0.25


class UIASelectionProvider(SelectionProvider):
    """Read a UI Automation TextPattern selection with a bounded wait.

    Automatic mouse selection can supply a :class:`SelectionContext`. In that
    mode the provider first resolves the control at the captured screen point
    or foreground HWND, then falls back to the focused control. This is more
    deterministic than relying on focus alone and never synthesizes Ctrl+C.

    The ``uiautomation`` package is imported only inside the worker. This
    keeps the provider importable in tests and lets an unavailable or broken
    UIA control fall through to the next native provider. A timed-out UIA call
    cannot be cancelled safely, so the worker is deliberately daemonized and
    the application waits only for the configured interval.
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
        self._uses_default_reader = automation_reader is None
        self._automation_reader = (
            automation_reader
            if automation_reader is not None
            else self._read_with_uiautomation
        )

    def get_selected_text(self) -> SelectedText:
        """Return the focused TextPattern selection or a safe SelectionError."""

        return self._get_selected_text(context=None)

    def get_selected_text_with_context(
        self,
        context: SelectionContext | None,
    ) -> SelectedText:
        """Return selection using the captured external-window context first."""

        return self._get_selected_text(context=context)

    def _get_selected_text(
        self,
        *,
        context: SelectionContext | None,
    ) -> SelectedText:
        result: list[str | SelectedText] = []
        errors: list[Exception] = []
        completed = threading.Event()

        def worker() -> None:
            try:
                if self._uses_default_reader:
                    result.append(self._read_with_uiautomation(context))
                else:
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
            text = selected.text if isinstance(selected, SelectedText) else str(selected)
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
    def _read_with_uiautomation(context: SelectionContext | None = None) -> str:
        """Read the current selection through UI Automation TextPattern."""

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
                return UIASelectionProvider._read_from_automation(
                    automation,
                    context=context,
                )
        return UIASelectionProvider._read_from_automation(
            automation,
            context=context,
        )

    @staticmethod
    def _read_from_automation(
        automation: Any,
        context: SelectionContext | None = None,
    ) -> str:
        """Read a selection from the best control in an initialized UIA context."""

        controls: list[Any] = []
        context_control = UIASelectionProvider._control_from_context(
            automation,
            context,
        )
        if context_control is not None:
            controls.append(context_control)

        get_focused_control = getattr(automation, "GetFocusedControl", None)
        if callable(get_focused_control):
            try:
                focused_control = get_focused_control()
            except Exception:
                focused_control = None
            if focused_control is not None and all(
                focused_control is not control for control in controls
            ):
                controls.append(focused_control)

        if not controls:
            raise SelectionError("UIA focused control is unavailable")

        last_error: SelectionError | None = None
        for control in controls:
            try:
                return UIASelectionProvider._read_control_selection(
                    automation,
                    control,
                )
            except SelectionError as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        raise SelectionError("UIA text selection is unavailable")

    @staticmethod
    def _control_from_context(
        automation: Any,
        context: SelectionContext | None,
    ) -> Any | None:
        """Resolve the UIA control tied to the captured gesture without focus changes."""

        if context is None:
            return None

        point = context.release_point
        if point is not None:
            control_from_point = getattr(automation, "ControlFromPoint", None)
            if callable(control_from_point):
                try:
                    control = control_from_point(*point)
                except TypeError:
                    try:
                        control = control_from_point(point)
                    except Exception:
                        control = None
                except Exception:
                    control = None
                if control is not None:
                    return control

        if context.foreground_hwnd:
            control_from_handle = getattr(automation, "ControlFromHandle", None)
            if callable(control_from_handle):
                try:
                    control = control_from_handle(int(context.foreground_hwnd))
                except Exception:
                    control = None
                if control is not None:
                    return control

        return None

    @staticmethod
    def _read_control_selection(automation: Any, control: Any) -> str:
        """Read selected text from one control supporting TextPattern."""

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
