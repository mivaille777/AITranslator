"""Windows UI Automation provider for native selected-text capture."""

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
MAX_ANCESTOR_DEPTH = 8
MAX_CONTEXT_SUBTREE_CONTROLS = 64
MAX_CONTEXT_SUBTREE_DEPTH = 6
CONTEXT_RICH_PROCESS_NAMES = frozenset(
    {
        "chrome.exe",
        "msedge.exe",
        "msedgewebview2.exe",
        "brave.exe",
        "firefox.exe",
        "opera.exe",
        "vivaldi.exe",
        "acrord32.exe",
        "acrobat.exe",
        "sumatrapdf.exe",
    }
)


class UIASelectionProvider(SelectionProvider):
    """Read a UI Automation text selection with a bounded wait.

    Automatic mouse selection can supply a :class:`SelectionContext`. The
    provider then searches the exact point/foreground window captured at
    mouse-up, plus nearby UIA ancestors. Browser and PDF processes receive one
    additional bounded subtree search because Chromium/Edge/PDF viewers often
    expose TextPattern on a document ancestor/descendant rather than the leaf
    element beneath the pointer.

    No path in this provider writes to the clipboard or synthesizes keyboard
    input.
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
        """Return selection using the frozen mouse/window context first."""

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
        """Read a selection from ordered controls in an initialized UIA context."""

        controls = UIASelectionProvider._candidate_controls(automation, context)
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
    def _candidate_controls(
        automation: Any,
        context: SelectionContext | None,
    ) -> list[Any]:
        """Build a bounded, deterministic control search order."""

        controls: list[Any] = []
        seen: set[int] = set()
        subtree_roots: list[Any] = []

        point_control = UIASelectionProvider._control_from_point(automation, context)
        if point_control is not None:
            UIASelectionProvider._append_control_chain(
                controls,
                seen,
                point_control,
            )

        focused_control = UIASelectionProvider._focused_control(automation)
        if focused_control is not None:
            UIASelectionProvider._append_control_chain(
                controls,
                seen,
                focused_control,
            )

        handle_control = UIASelectionProvider._control_from_handle(automation, context)
        if handle_control is not None:
            UIASelectionProvider._append_control_chain(
                controls,
                seen,
                handle_control,
            )
            subtree_roots.append(handle_control)

        process_name = ""
        if context is not None and context.process_name:
            process_name = str(context.process_name).replace("\\", "/").rsplit("/", 1)[-1].casefold()

        if process_name in CONTEXT_RICH_PROCESS_NAMES:
            # Browser/PDF accessibility trees commonly place TextPattern on a
            # Document control below the top-level HWND rather than directly
            # under the mouse. Search only a bounded number of descendants so
            # a malformed/huge accessibility tree cannot stall the UIA worker.
            for root in subtree_roots:
                for control in UIASelectionProvider._bounded_descendants(root):
                    UIASelectionProvider._append_unique(controls, seen, control)

        return controls

    @staticmethod
    def _control_from_point(
        automation: Any,
        context: SelectionContext | None,
    ) -> Any | None:
        if context is None or context.release_point is None:
            return None
        control_from_point = getattr(automation, "ControlFromPoint", None)
        if not callable(control_from_point):
            return None
        point = context.release_point
        try:
            return control_from_point(*point)
        except TypeError:
            try:
                return control_from_point(point)
            except Exception:
                return None
        except Exception:
            return None

    @staticmethod
    def _control_from_handle(
        automation: Any,
        context: SelectionContext | None,
    ) -> Any | None:
        if context is None or not context.foreground_hwnd:
            return None
        control_from_handle = getattr(automation, "ControlFromHandle", None)
        if not callable(control_from_handle):
            return None
        try:
            return control_from_handle(int(context.foreground_hwnd))
        except Exception:
            return None

    @staticmethod
    def _focused_control(automation: Any) -> Any | None:
        get_focused_control = getattr(automation, "GetFocusedControl", None)
        if not callable(get_focused_control):
            return None
        try:
            return get_focused_control()
        except Exception:
            return None

    @staticmethod
    def _append_unique(controls: list[Any], seen: set[int], control: Any) -> bool:
        if control is None:
            return False
        marker = id(control)
        if marker in seen:
            return False
        seen.add(marker)
        controls.append(control)
        return True

    @staticmethod
    def _append_control_chain(
        controls: list[Any],
        seen: set[int],
        control: Any,
    ) -> None:
        """Append a control followed by a bounded chain of its ancestors."""

        current = control
        depth = 0
        local_seen: set[int] = set()
        while current is not None and depth <= MAX_ANCESTOR_DEPTH:
            marker = id(current)
            if marker in local_seen:
                break
            local_seen.add(marker)
            UIASelectionProvider._append_unique(controls, seen, current)
            current = UIASelectionProvider._parent_control(current)
            depth += 1

    @staticmethod
    def _parent_control(control: Any) -> Any | None:
        for name in ("GetParentControl", "GetParent"):
            callback = getattr(control, name, None)
            if callable(callback):
                try:
                    parent = callback()
                except Exception:
                    parent = None
                if parent is not None:
                    return parent
        for name in ("ParentControl", "Parent"):
            try:
                parent = getattr(control, name, None)
            except Exception:
                parent = None
            if parent is not None:
                return parent
        return None

    @staticmethod
    def _bounded_descendants(root: Any) -> list[Any]:
        """Return a breadth-first, size/depth-bounded descendant list."""

        descendants: list[Any] = []
        queue: list[tuple[Any, int]] = [(root, 0)]
        visited: set[int] = {id(root)}

        while queue and len(descendants) < MAX_CONTEXT_SUBTREE_CONTROLS:
            current, depth = queue.pop(0)
            if depth >= MAX_CONTEXT_SUBTREE_DEPTH:
                continue
            children = UIASelectionProvider._children(current)
            children.sort(key=UIASelectionProvider._control_priority)
            for child in children:
                if child is None:
                    continue
                marker = id(child)
                if marker in visited:
                    continue
                visited.add(marker)
                descendants.append(child)
                if len(descendants) >= MAX_CONTEXT_SUBTREE_CONTROLS:
                    break
                queue.append((child, depth + 1))

        return descendants

    @staticmethod
    def _children(control: Any) -> list[Any]:
        get_children = getattr(control, "GetChildren", None)
        if callable(get_children):
            try:
                children = list(get_children() or [])
            except Exception:
                children = []
            if children:
                return children

        first_child = getattr(control, "GetFirstChildControl", None)
        if not callable(first_child):
            return []
        try:
            child = first_child()
        except Exception:
            return []

        children: list[Any] = []
        local_seen: set[int] = set()
        while child is not None and len(children) < MAX_CONTEXT_SUBTREE_CONTROLS:
            marker = id(child)
            if marker in local_seen:
                break
            local_seen.add(marker)
            children.append(child)
            next_sibling = getattr(child, "GetNextSiblingControl", None)
            if not callable(next_sibling):
                break
            try:
                child = next_sibling()
            except Exception:
                break
        return children

    @staticmethod
    def _control_priority(control: Any) -> int:
        """Prefer document/text controls during browser/PDF subtree traversal."""

        labels: list[str] = []
        for attribute in ("ControlTypeName", "Name", "ClassName"):
            try:
                value = getattr(control, attribute, "")
            except Exception:
                value = ""
            if value:
                labels.append(str(value).casefold())
        joined = " ".join(labels)
        if "document" in joined or "pdf" in joined:
            return 0
        if "text" in joined or "edit" in joined:
            return 1
        return 2

    @staticmethod
    def _read_control_selection(automation: Any, control: Any) -> str:
        """Read selected text from TextPattern/TextPattern2 on one control."""

        patterns = UIASelectionProvider._get_text_patterns(automation, control)
        if not patterns:
            raise SelectionError("UIA TextPattern is unsupported")

        last_error: SelectionError | None = None
        for text_pattern in patterns:
            try:
                return UIASelectionProvider._read_pattern_selection(text_pattern)
            except SelectionError as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        raise SelectionError("UIA text selection is unavailable")

    @staticmethod
    def _read_pattern_selection(text_pattern: Any) -> str:
        get_selection = getattr(text_pattern, "GetSelection", None)
        if not callable(get_selection):
            raise SelectionError("UIA TextPattern selection is unsupported")

        try:
            ranges = get_selection()
        except Exception as exc:
            error = SelectionError("UIA text selection is unavailable")
            error.__cause__ = exc
            raise error
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
                value = get_text()
            except Exception as exc:
                error = SelectionError("UIA text range is unavailable")
                error.__cause__ = exc
                raise error
            if value is not None:
                text_parts.append(str(value))

        text = "".join(text_parts)
        if not text.strip():
            raise SelectionError("UIA selection is empty")
        return text

    @staticmethod
    def _get_text_patterns(automation: Any, control: Any) -> list[Any]:
        """Return unique TextPattern/TextPattern2 objects supported by a control."""

        patterns: list[Any] = []
        seen: set[int] = set()

        def add(pattern: Any) -> None:
            if pattern is None:
                return
            marker = id(pattern)
            if marker in seen:
                return
            seen.add(marker)
            patterns.append(pattern)

        for method_name in ("GetTextPattern", "GetTextPattern2"):
            callback = getattr(control, method_name, None)
            if not callable(callback):
                continue
            try:
                add(callback())
            except Exception:
                continue

        get_pattern = getattr(control, "GetPattern", None)
        if callable(get_pattern):
            pattern_ids = getattr(automation, "PatternId", None)
            for attribute, fallback in (
                ("TextPattern", 10014),
                ("TextPattern2", 10024),
            ):
                pattern_id = getattr(pattern_ids, attribute, fallback)
                try:
                    add(get_pattern(pattern_id))
                except Exception:
                    continue

        return patterns

    @staticmethod
    def _get_text_pattern(automation: Any, control: Any) -> Any | None:
        """Compatibility helper returning the first supported text pattern."""

        patterns = UIASelectionProvider._get_text_patterns(automation, control)
        return patterns[0] if patterns else None


__all__ = [
    "CONTEXT_RICH_PROCESS_NAMES",
    "DEFAULT_UIA_TIMEOUT_SECONDS",
    "MAX_ANCESTOR_DEPTH",
    "MAX_CONTEXT_SUBTREE_CONTROLS",
    "MAX_CONTEXT_SUBTREE_DEPTH",
    "UIASelectionProvider",
]
