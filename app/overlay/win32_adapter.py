"""Windows-specific window operations for the overlay layer."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QWidget

_HWND_TOPMOST = ctypes.c_void_p(-1)
_HWND_NOTOPMOST = ctypes.c_void_p(-2)
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010
_SWP_SHOWWINDOW = 0x0040
_SWP_FRAMECHANGED = 0x0020

_GWL_EXSTYLE = -20
_GWLP_WNDPROC = -4
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_NOACTIVATE = 0x08000000
_WM_NCHITTEST = 0x0084
_HTTRANSPARENT = -1

if hasattr(ctypes, "WINFUNCTYPE"):
    _WNDPROC = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
else:  # pragma: no cover - only used on non-Windows import environments
    _WNDPROC = ctypes.CFUNCTYPE(
        ctypes.c_ssize_t,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )


@dataclass
class _LockedWindowState:
    hwnd: int
    original_ex_style: int
    original_wnd_proc: int
    callback: Any
    user32: Any


class Win32OverlayAdapter:
    """Apply Win32 behavior without leaking ctypes into GUI code."""

    def __init__(
        self,
        user32: Any | None = None,
        *,
        platform_name: str | None = None,
    ) -> None:
        self._user32 = user32
        self._platform_name = platform_name or sys.platform
        self._locked_windows: dict[int, _LockedWindowState] = {}

    @property
    def is_available(self) -> bool:
        return self._platform_name == "win32"

    def _load_user32(self) -> Any:
        return self._user32 or ctypes.WinDLL("user32", use_last_error=True)

    @staticmethod
    def _get_long_ptr_function(user32: Any, name: str, fallback: str) -> Any:
        function = getattr(user32, name, None)
        if function is None:
            function = getattr(user32, fallback)
        function.argtypes = [wintypes.HWND, wintypes.INT]
        function.restype = ctypes.c_ssize_t
        return function

    @classmethod
    def _get_window_long_ptr(cls, user32: Any, hwnd: int, index: int) -> int:
        getter = cls._get_long_ptr_function(
            user32,
            "GetWindowLongPtrW",
            "GetWindowLongW",
        )
        return int(getter(hwnd, index))

    @classmethod
    def _set_window_long_ptr(
        cls,
        user32: Any,
        hwnd: int,
        index: int,
        value: int | ctypes.c_void_p,
    ) -> int:
        setter = cls._get_long_ptr_function(
            user32,
            "SetWindowLongPtrW",
            "SetWindowLongW",
        )
        setter.argtypes = [wintypes.HWND, wintypes.INT, ctypes.c_void_p]
        pointer_value = value if isinstance(value, ctypes.c_void_p) else ctypes.c_void_p(value)
        return int(setter(hwnd, index, pointer_value))

    @staticmethod
    def _window_handle(window: QWidget) -> int:
        return int(window.winId())

    def set_topmost(self, window: QWidget, enabled: bool = True) -> bool:
        """Set or clear the Win32 topmost state without activating the window."""

        if not self.is_available:
            return False

        try:
            hwnd = int(window.winId())
            if hwnd == 0:
                return False

            user32 = self._load_user32()
            set_window_pos = user32.SetWindowPos
            set_window_pos.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                wintypes.INT,
                wintypes.INT,
                wintypes.INT,
                wintypes.INT,
                wintypes.UINT,
            ]
            set_window_pos.restype = wintypes.BOOL
            insert_after = _HWND_TOPMOST if enabled else _HWND_NOTOPMOST
            flags = _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE | _SWP_FRAMECHANGED
            if enabled:
                flags |= _SWP_SHOWWINDOW

            return bool(set_window_pos(hwnd, insert_after, 0, 0, 0, 0, flags))
        except (AttributeError, OSError, OverflowError, TypeError, ValueError):
            # Qt's platform plugin and headless tests may not expose a native
            # HWND. Qt's WindowStaysOnTopHint remains the portable fallback.
            return False

    def _install_click_through_proc(
        self,
        user32: Any,
        hwnd: int,
    ) -> tuple[int, Any]:
        original_wnd_proc = self._get_window_long_ptr(user32, hwnd, _GWLP_WNDPROC)

        def window_proc(
            callback_hwnd: int,
            message: int,
            w_param: int,
            l_param: int,
        ) -> int:
            if message == _WM_NCHITTEST:
                return _HTTRANSPARENT
            if original_wnd_proc:
                call_window_proc = user32.CallWindowProcW
                call_window_proc.argtypes = [
                    ctypes.c_void_p,
                    wintypes.HWND,
                    wintypes.UINT,
                    wintypes.WPARAM,
                    wintypes.LPARAM,
                ]
                call_window_proc.restype = ctypes.c_ssize_t
                return int(
                    call_window_proc(
                        original_wnd_proc,
                        callback_hwnd,
                        message,
                        w_param,
                        l_param,
                    )
                )
            return 0

        callback = _WNDPROC(window_proc)
        self._set_window_long_ptr(
            user32,
            hwnd,
            _GWLP_WNDPROC,
            ctypes.cast(callback, ctypes.c_void_p),
        )
        return original_wnd_proc, callback

    def set_locked(self, window: QWidget, locked: bool) -> bool:
        """Apply or restore click-through and no-activate Win32 styles."""

        if not self.is_available:
            return False

        try:
            hwnd = self._window_handle(window)
            if hwnd == 0:
                return False

            if locked:
                if hwnd in self._locked_windows:
                    return True

                user32 = self._load_user32()
                original_ex_style = self._get_window_long_ptr(
                    user32,
                    hwnd,
                    _GWL_EXSTYLE,
                )
                locked_ex_style = (
                    original_ex_style
                    | _WS_EX_LAYERED
                    | _WS_EX_TRANSPARENT
                    | _WS_EX_NOACTIVATE
                )
                self._set_window_long_ptr(
                    user32,
                    hwnd,
                    _GWL_EXSTYLE,
                    locked_ex_style,
                )
                try:
                    original_wnd_proc, callback = self._install_click_through_proc(
                        user32,
                        hwnd,
                    )
                except Exception:
                    self._set_window_long_ptr(
                        user32,
                        hwnd,
                        _GWL_EXSTYLE,
                        original_ex_style,
                    )
                    raise

                self._locked_windows[hwnd] = _LockedWindowState(
                    hwnd=hwnd,
                    original_ex_style=original_ex_style,
                    original_wnd_proc=original_wnd_proc,
                    callback=callback,
                    user32=user32,
                )
                self.set_topmost(window, enabled=True)
                return True

            state = self._locked_windows.get(hwnd)
            if state is None:
                return True

            try:
                self._set_window_long_ptr(
                    state.user32,
                    state.hwnd,
                    _GWLP_WNDPROC,
                    state.original_wnd_proc,
                )
                self._set_window_long_ptr(
                    state.user32,
                    state.hwnd,
                    _GWL_EXSTYLE,
                    state.original_ex_style,
                )
            finally:
                # Releasing the callback reference after restoring WNDPROC is
                # essential: otherwise Windows may call freed Python memory.
                self._locked_windows.pop(hwnd, None)
            self.set_topmost(window, enabled=True)
            return True
        except (AttributeError, OSError, OverflowError, TypeError, ValueError):
            return False
