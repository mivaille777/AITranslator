"""Clipboard-based selected-text provider."""

from __future__ import annotations

import math
from collections.abc import Callable
from time import monotonic, sleep
from typing import Any
from uuid import uuid4

from app.models.selection import SelectedText
from app.selection.base import SelectionProvider
from app.selection.clipboard_adapter import ClipboardAdapter
from app.selection.copy_command import CopyCommandAdapter
from app.selection.errors import SelectionError

DEFAULT_TIMEOUT_SECONDS = 1.5
DEFAULT_POLL_INTERVAL_SECONDS = 0.02
# GlobalHotKeys can invoke the callback before Windows has fully released the
# Alt key. A slightly longer guard prevents the synthetic Ctrl+C from being
# interpreted as Alt+C by the foreground application.
DEFAULT_COPY_DELAY_SECONDS = 0.15
DEFAULT_COPY_ATTEMPTS = 2


def _new_clipboard_sentinel() -> str:
    """Return a value that cannot be confused with the selected text."""

    return f"__AI_TRANSLATOR_CLIPBOARD_SENTINEL_{uuid4().hex}__"


class ClipboardSelectionProvider(SelectionProvider):
    """Read a foreground selection by copying it and restoring the clipboard."""

    def __init__(
        self,
        clipboard_adapter: ClipboardAdapter | Any | None = None,
        copy_command_adapter: CopyCommandAdapter | Any | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        copy_delay_seconds: float = DEFAULT_COPY_DELAY_SECONDS,
        copy_attempts: int = DEFAULT_COPY_ATTEMPTS,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.clipboard_adapter = (
            clipboard_adapter if clipboard_adapter is not None else ClipboardAdapter()
        )
        self.copy_command_adapter = (
            copy_command_adapter
            if copy_command_adapter is not None
            else CopyCommandAdapter()
        )
        self.timeout_seconds = max(0.0, float(timeout_seconds))
        self.poll_interval_seconds = max(0.001, float(poll_interval_seconds))
        self.copy_delay_seconds = max(0.0, float(copy_delay_seconds))
        self.copy_attempts = max(1, int(copy_attempts))
        self._clock = clock or monotonic
        self._sleeper = sleeper or sleep

    def get_selected_text(self) -> SelectedText:
        """Return selected text or raise SelectionError after bounded cleanup."""

        snapshot: Any = None
        snapshot_captured = False
        operation_error: SelectionError | None = None
        selected: SelectedText | None = None

        try:
            # GlobalHotKeys invokes the callback while Alt is still physically
            # down. Give the modifier time to be released before sending Ctrl+C
            # to the foreground application. Do this before taking the
            # snapshot so Windows screen-capture tools have time to publish an
            # image to the clipboard before the temporary selection workflow
            # starts.
            if self.copy_delay_seconds:
                self._sleeper(self.copy_delay_seconds)

            snapshot = self.clipboard_adapter.snapshot()
            snapshot_captured = True

            # Comparing against the old clipboard is ambiguous when the user
            # selects exactly the text that was already on the clipboard. Put
            # a random sentinel in place first, then wait for Ctrl+C to replace
            # that sentinel with the foreground selection.
            sentinel = _new_clipboard_sentinel()
            self.clipboard_adapter.write_text(sentinel)
            sentinel_token = self.clipboard_adapter.get_change_token()

            copy_succeeded = False
            attempt_timeout = self.timeout_seconds / self.copy_attempts
            for attempt in range(self.copy_attempts):
                self.copy_command_adapter.send_copy()
                if self._wait_for_clipboard_change(
                    sentinel_token,
                    sentinel,
                    timeout_seconds=attempt_timeout,
                ):
                    copy_succeeded = True
                    break
                if attempt + 1 < self.copy_attempts:
                    self._sleeper(self.poll_interval_seconds)

            if not copy_succeeded:
                raise SelectionError("clipboard did not change before timeout")

            text = self.clipboard_adapter.read_text()
            if not str(text).strip():
                raise SelectionError("selected text is empty")
            selected = SelectedText(text=str(text), provider="clipboard")
        except SelectionError as exc:
            operation_error = exc
        except Exception as exc:
            operation_error = SelectionError("clipboard selection failed")
            operation_error.__cause__ = exc

        if snapshot_captured:
            try:
                self.clipboard_adapter.restore(snapshot)
            except Exception as exc:
                restore_error = SelectionError("clipboard restoration failed")
                restore_error.__cause__ = exc
                if operation_error is None:
                    operation_error = restore_error
                else:
                    combined_error = SelectionError(
                        f"{operation_error}; clipboard restoration failed"
                    )
                    combined_error.__cause__ = exc
                    operation_error = combined_error

        if operation_error is not None:
            raise operation_error
        if selected is None:  # pragma: no cover - defensive invariant
            raise SelectionError("selected text was not produced")
        return selected

    def _wait_for_clipboard_change(
        self,
        original_token: object,
        original_text: str,
        *,
        timeout_seconds: float | None = None,
    ) -> bool:
        timeout = (
            self.timeout_seconds
            if timeout_seconds is None
            else max(0.0, float(timeout_seconds))
        )
        deadline = self._clock() + timeout
        max_polls = max(
            1,
            math.ceil(timeout / self.poll_interval_seconds) + 1,
        )

        for _ in range(max_polls):
            try:
                current_token = self.clipboard_adapter.get_change_token()
                current_text = self.clipboard_adapter.read_text()
                if (
                    current_token != original_token
                    or current_text != original_text
                ):
                    return True
            except Exception:
                # Clipboard ownership can briefly be unavailable while a
                # browser publishes its formats. Keep polling within bounds.
                pass

            now = self._clock()
            if now >= deadline:
                break
            self._sleeper(min(self.poll_interval_seconds, deadline - now))

        return False
