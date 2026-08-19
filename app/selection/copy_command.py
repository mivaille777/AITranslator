"""Keyboard Ctrl+C access isolated behind a mockable adapter."""

from __future__ import annotations

import sys
from collections.abc import Callable
from time import monotonic, sleep
from typing import Any

from pynput import keyboard

DEFAULT_KEY_RELEASE_TIMEOUT_SECONDS = 0.4
DEFAULT_KEY_STATE_POLL_SECONDS = 0.01
# Synthetic Ctrl+C must never be injected while a real modifier/chord is held.
# Otherwise releasing our injected Ctrl can transiently alter the user's real
# keyboard state (most visibly when the user presses Ctrl+C at the same time).
_CONFLICTING_VIRTUAL_KEYS = (
    0x10,  # VK_SHIFT
    0x11,  # VK_CONTROL
    0x12,  # VK_MENU / Alt
    0x43,  # VK_C
    0x5B,  # VK_LWIN
    0x5C,  # VK_RWIN
)


class CopyCommandAdapter:
    """Send Ctrl+C to the current foreground application without stealing it.

    The global hotkey is installed with ``pynput``, but using the same
    high-level controller to synthesize the follow-up copy can be unreliable
    on Windows (especially in Chromium). Prefer the Win32 input primitive for
    the real application and keep the pynput path as a portable fallback.

    On Windows the adapter also observes the physical keyboard state before
    injecting anything. This prevents AITranslator's synthetic Ctrl key-up
    from racing a real user Ctrl+C/Alt/Shift/Win chord.
    """

    def __init__(
        self,
        controller: Any | None = None,
        *,
        keybd_event: Callable[[int, int, int, int], None] | None = None,
        key_state_reader: Callable[[int], int] | None = None,
        platform_name: str | None = None,
        key_release_timeout_seconds: float = DEFAULT_KEY_RELEASE_TIMEOUT_SECONDS,
        key_state_poll_seconds: float = DEFAULT_KEY_STATE_POLL_SECONDS,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._controller = controller
        self._keybd_event = keybd_event
        self._key_state_reader = key_state_reader
        self._clock = clock or monotonic
        self._sleeper = sleeper or sleep
        self._key_release_timeout_seconds = max(
            0.0,
            float(key_release_timeout_seconds),
        )
        self._key_state_poll_seconds = max(0.001, float(key_state_poll_seconds))
        self._last_wait_had_conflict = False

        current_platform = platform_name or sys.platform
        # Only auto-resolve Win32 primitives on the production construction
        # path. Tests/custom adapters that explicitly inject keybd_event keep
        # full control of their environment unless they also inject a reader.
        if (
            self._controller is None
            and self._keybd_event is None
            and current_platform == "win32"
        ):
            try:
                from win32api import GetAsyncKeyState, keybd_event as win32_keybd_event
            except (ImportError, AttributeError, OSError):
                # The project declares pywin32 as a runtime dependency, but
                # retaining a fallback keeps non-standard installs usable.
                pass
            else:
                self._keybd_event = win32_keybd_event
                if self._key_state_reader is None:
                    self._key_state_reader = GetAsyncKeyState

        if self._controller is None and self._keybd_event is None:
            self._controller = keyboard.Controller()

    @property
    def last_wait_had_conflict(self) -> bool:
        """Return whether the most recent safety wait observed a real key."""

        return self._last_wait_had_conflict

    def wait_until_safe(self, timeout_seconds: float | None = None) -> bool:
        """Wait until real modifier/C keys are released before injection.

        ``GetAsyncKeyState`` exposes the physical high bit. We intentionally
        ignore its low "pressed since last query" bit, because only a key that
        is currently down can collide with our balanced synthetic key events.
        Non-Windows/fallback adapters have no native key-state reader and are
        therefore treated as immediately safe.
        """

        reader = self._key_state_reader
        self._last_wait_had_conflict = False
        if reader is None:
            return True

        timeout = (
            self._key_release_timeout_seconds
            if timeout_seconds is None
            else max(0.0, float(timeout_seconds))
        )
        deadline = self._clock() + timeout

        while True:
            try:
                busy = any(
                    int(reader(virtual_key)) & 0x8000
                    for virtual_key in _CONFLICTING_VIRTUAL_KEYS
                )
            except Exception:
                # If native state cannot be read, do not manufacture a false
                # busy state that permanently disables the fallback.
                return True

            if not busy:
                return True

            self._last_wait_had_conflict = True
            now = self._clock()
            if now >= deadline:
                return False
            self._sleeper(
                min(self._key_state_poll_seconds, max(0.0, deadline - now))
            )

    def send_copy(self) -> None:
        """Press and release Ctrl+C only when the physical chord is idle."""

        if not self.wait_until_safe():
            raise RuntimeError("physical copy shortcut is busy")

        if self._keybd_event is not None:
            self._send_copy_win32()
            return

        if self._controller is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("copy input controller is not initialized")

        control_key = keyboard.Key.ctrl
        self._controller.press(control_key)
        try:
            self._controller.press("c")
        finally:
            try:
                self._controller.release("c")
            finally:
                self._controller.release(control_key)

    def _send_copy_win32(self) -> None:
        """Send Ctrl+C through the Windows input queue."""

        if self._keybd_event is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("Win32 keyboard event function is not initialized")

        virtual_control = 0x11  # VK_CONTROL
        virtual_c = 0x43  # VK_C
        key_up = 0x0002  # KEYEVENTF_KEYUP

        try:
            self._keybd_event(virtual_control, 0, 0, 0)
            try:
                self._keybd_event(virtual_c, 0, 0, 0)
            finally:
                self._keybd_event(virtual_c, 0, key_up, 0)
        finally:
            self._keybd_event(virtual_control, 0, key_up, 0)

    copy = send_copy
    send_ctrl_c = send_copy


__all__ = [
    "CopyCommandAdapter",
    "DEFAULT_KEY_RELEASE_TIMEOUT_SECONDS",
    "DEFAULT_KEY_STATE_POLL_SECONDS",
]
