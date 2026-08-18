"""Keyboard Ctrl+C access isolated behind a mockable adapter."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from pynput import keyboard


class CopyCommandAdapter:
    """Send Ctrl+C to the current foreground application.

    The global hotkey is installed with ``pynput``, but using the same
    high-level controller to synthesize the follow-up copy can be unreliable
    on Windows (especially in Chromium).  Prefer the Win32 input primitive
    for the real application and keep the pynput path as a portable fallback.
    """

    def __init__(
        self,
        controller: Any | None = None,
        *,
        keybd_event: Callable[[int, int, int, int], None] | None = None,
        platform_name: str | None = None,
    ) -> None:
        self._controller = controller
        self._keybd_event = keybd_event

        if self._controller is None and self._keybd_event is None:
            current_platform = platform_name or sys.platform
            if current_platform == "win32":
                try:
                    from win32api import keybd_event as win32_keybd_event
                except (ImportError, AttributeError, OSError):
                    # The project declares pywin32 as a runtime dependency,
                    # but retaining a fallback makes the adapter testable and
                    # usable on non-standard Python installations.
                    pass
                else:
                    self._keybd_event = win32_keybd_event

        if self._controller is None and self._keybd_event is None:
            self._controller = keyboard.Controller()

    def send_copy(self) -> None:
        """Press and release Ctrl+C with balanced key events."""

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
