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
# Keep a small grace period after a trigger/selection release. Besides the
# legacy hotkey path, this gives applications a moment to finish publishing a
# selection and gives a user's immediate Ctrl+C a chance to win before we
# synthesize any keyboard input.
DEFAULT_COPY_DELAY_SECONDS = 0.15
DEFAULT_COPY_ATTEMPTS = 2
DEFAULT_RESTORE_GUARD_SECONDS = 0.03


def _new_clipboard_sentinel() -> str:
    """Return a value that cannot be confused with the selected text."""

    return f"__AI_TRANSLATOR_CLIPBOARD_SENTINEL_{uuid4().hex}__"


class ClipboardSelectionProvider(SelectionProvider):
    """Read a foreground selection without stealing the user's copy shortcut.

    Clipboard selection is the final fallback after Word/UIA providers. It may
    temporarily send Ctrl+C, but only after the real keyboard chord is idle.
    If the user performs Ctrl+C while capture is waiting, that newer clipboard
    value is accepted directly and no synthetic Ctrl+C is injected.

    Cleanup restores the old clipboard only while AITranslator can still prove
    it owns the temporary clipboard value. User/application writes always win.
    """

    def __init__(
        self,
        clipboard_adapter: ClipboardAdapter | Any | None = None,
        copy_command_adapter: CopyCommandAdapter | Any | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        copy_delay_seconds: float = DEFAULT_COPY_DELAY_SECONDS,
        copy_attempts: int = DEFAULT_COPY_ATTEMPTS,
        restore_guard_seconds: float = DEFAULT_RESTORE_GUARD_SECONDS,
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
        self.restore_guard_seconds = max(0.0, float(restore_guard_seconds))
        self._clock = clock or monotonic
        self._sleeper = sleeper or sleep

    def get_selected_text(self) -> SelectedText:
        """Return selected text or raise SelectionError after bounded cleanup."""

        snapshot: Any = None
        snapshot_captured = False
        operation_error: SelectionError | None = None
        selected: SelectedText | None = None
        owned_token: object | None = None
        owned_text: str | None = None
        preserve_current_clipboard = False

        try:
            # Record the clipboard before the settle/grace window. If the user
            # presses Ctrl+C in that window, use that fresh value directly.
            baseline_token = self._safe_change_token()
            baseline_text = self._safe_read_text()
            if self.copy_delay_seconds:
                self._sleeper(self.copy_delay_seconds)

            snapshot = self.clipboard_adapter.snapshot()
            snapshot_captured = True
            current_token = self._safe_change_token()
            current_text = self._safe_read_text()

            if self._external_text_changed(
                baseline_token,
                baseline_text,
                current_token,
                current_text,
            ):
                selected = SelectedText(text=current_text, provider="clipboard")
                preserve_current_clipboard = True
            else:
                # CopyCommandAdapter uses GetAsyncKeyState on Windows. Waiting
                # here *before* writing the sentinel means a real Ctrl+C can
                # publish normally without competing with our clipboard write.
                before_wait_token = current_token
                before_wait_text = current_text
                if not self._wait_for_safe_copy_chord():
                    raise SelectionError("physical copy shortcut is busy")

                after_wait_token = self._safe_change_token()
                after_wait_text = self._safe_read_text()
                if self._external_text_changed(
                    before_wait_token,
                    before_wait_text,
                    after_wait_token,
                    after_wait_text,
                ):
                    selected = SelectedText(
                        text=after_wait_text,
                        provider="clipboard",
                    )
                    preserve_current_clipboard = True
                elif self._clipboard_changed(
                    before_wait_token,
                    before_wait_text,
                    after_wait_token,
                    after_wait_text,
                ):
                    # A newer non-text/empty user clipboard write is still
                    # authoritative; never overwrite it with our sentinel.
                    preserve_current_clipboard = True
                    raise SelectionError("clipboard changed during user copy")

            if selected is None:
                sentinel = _new_clipboard_sentinel()
                self.clipboard_adapter.write_text(sentinel)
                sentinel_token = self.clipboard_adapter.get_change_token()
                owned_token = sentinel_token
                owned_text = sentinel

                copy_succeeded = False
                attempt_timeout = self.timeout_seconds / self.copy_attempts
                for attempt in range(self.copy_attempts):
                    # Check the real keys for every retry. A user may start a
                    # Ctrl+C between attempts; if so we wait and then consume
                    # the user's clipboard result instead of injecting again.
                    before_wait_token = self._safe_change_token()
                    before_wait_text = self._safe_read_text()
                    if not self._wait_for_safe_copy_chord():
                        raise SelectionError("physical copy shortcut is busy")
                    after_wait_token = self._safe_change_token()
                    after_wait_text = self._safe_read_text()

                    if self._external_text_changed(
                        before_wait_token,
                        before_wait_text,
                        after_wait_token,
                        after_wait_text,
                    ):
                        selected = SelectedText(
                            text=after_wait_text,
                            provider="clipboard",
                        )
                        preserve_current_clipboard = True
                        copy_succeeded = True
                        break

                    # If the sentinel disappeared for any other reason, another
                    # clipboard owner won the race. Abort instead of replacing
                    # the user's/application's newer clipboard state.
                    if (
                        after_wait_token != sentinel_token
                        or after_wait_text != sentinel
                    ):
                        preserve_current_clipboard = True
                        raise SelectionError("clipboard changed before synthetic copy")

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

                if selected is None:
                    text = self.clipboard_adapter.read_text()
                    owned_token = self.clipboard_adapter.get_change_token()
                    owned_text = str(text)
                    if not owned_text.strip():
                        raise SelectionError("selected text is empty")
                    selected = SelectedText(text=owned_text, provider="clipboard")
        except SelectionError as exc:
            operation_error = exc
        except Exception as exc:
            operation_error = SelectionError("clipboard selection failed")
            operation_error.__cause__ = exc

        if snapshot_captured and not preserve_current_clipboard:
            try:
                if self.restore_guard_seconds:
                    # Give a physical user Ctrl+C immediately following the
                    # selection gesture a chance to publish before cleanup.
                    self._sleeper(self.restore_guard_seconds)
                if self._clipboard_still_owned(owned_token, owned_text):
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

    def _wait_for_safe_copy_chord(self) -> bool:
        waiter = getattr(self.copy_command_adapter, "wait_until_safe", None)
        if not callable(waiter):
            return True
        try:
            return bool(waiter())
        except Exception as exc:
            error = SelectionError("keyboard state check failed")
            error.__cause__ = exc
            raise error

    def _safe_change_token(self) -> object | None:
        try:
            return self.clipboard_adapter.get_change_token()
        except Exception:
            return None

    def _safe_read_text(self) -> str:
        try:
            value = self.clipboard_adapter.read_text()
        except Exception:
            return ""
        return "" if value is None else str(value)

    @staticmethod
    def _clipboard_changed(
        before_token: object | None,
        before_text: str,
        after_token: object | None,
        after_text: str,
    ) -> bool:
        if before_token is not None and after_token is not None:
            if before_token != after_token:
                return True
        return before_text != after_text

    @classmethod
    def _external_text_changed(
        cls,
        before_token: object | None,
        before_text: str,
        after_token: object | None,
        after_text: str,
    ) -> bool:
        return (
            bool(after_text.strip())
            and cls._clipboard_changed(
                before_token,
                before_text,
                after_token,
                after_text,
            )
        )

    def _clipboard_still_owned(
        self,
        expected_token: object | None,
        expected_text: str | None,
    ) -> bool:
        """Restore only if no newer clipboard write has occurred."""

        if expected_token is None or expected_text is None:
            return False
        try:
            current_token = self.clipboard_adapter.get_change_token()
            current_text = str(self.clipboard_adapter.read_text())
        except Exception:
            # If ownership cannot be proven, preserving the current clipboard
            # is safer than overwriting a possible user copy.
            return False
        return current_token == expected_token and current_text == expected_text

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


__all__ = [
    "ClipboardSelectionProvider",
    "DEFAULT_COPY_ATTEMPTS",
    "DEFAULT_COPY_DELAY_SECONDS",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "DEFAULT_RESTORE_GUARD_SECONDS",
    "DEFAULT_TIMEOUT_SECONDS",
]
