"""Small Windows foreground-process detector used by selection providers."""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Callable
from ctypes import wintypes
from typing import Any

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class ForegroundApplicationDetector:
    """Return foreground-window metadata without activating another process."""

    def __init__(
        self,
        user32: Any | None = None,
        kernel32: Any | None = None,
        *,
        platform_name: str | None = None,
        executable_name_reader: Callable[[], str | None] | None = None,
    ) -> None:
        self._user32 = user32
        self._kernel32 = kernel32
        self._platform_name = platform_name or sys.platform
        self._executable_name_reader = executable_name_reader

    def window_handle(self) -> int | None:
        """Return the current foreground HWND as an integer when available."""

        if self._platform_name != "win32":
            return None
        try:
            user32 = self._load_user32()
            get_foreground_window = user32.GetForegroundWindow
            try:
                get_foreground_window.restype = wintypes.HWND
            except (AttributeError, TypeError):
                pass
            hwnd = get_foreground_window()
            if not hwnd:
                return None
            return int(hwnd)
        except (AttributeError, OSError, OverflowError, TypeError, ValueError):
            return None

    def snapshot(self) -> tuple[int | None, str | None]:
        """Capture foreground HWND and executable from the same window sample.

        Selection capture is timing-sensitive. Reading the HWND first and then
        asking ``executable_name()`` separately can accidentally describe two
        different windows if focus changes in between. This method freezes one
        HWND and resolves its process name from that handle.
        """

        hwnd = self.window_handle()
        if self._executable_name_reader is not None:
            try:
                value = self._executable_name_reader()
            except Exception:
                value = None
            return hwnd, str(value) if value else None
        if hwnd is None or self._platform_name != "win32":
            return hwnd, None
        return hwnd, self._executable_name_for_hwnd(hwnd)

    def executable_name(self) -> str | None:
        """Return a basename such as ``WINWORD.EXE`` or ``None`` on failure."""

        if self._executable_name_reader is not None:
            try:
                value = self._executable_name_reader()
            except Exception:
                return None
            return str(value) if value else None

        if self._platform_name != "win32":
            return None

        hwnd = self.window_handle()
        if hwnd is None:
            return None
        return self._executable_name_for_hwnd(hwnd)

    def _executable_name_for_hwnd(self, hwnd: int) -> str | None:
        """Resolve a process basename for one already-captured HWND."""

        process_handle: Any | None = None
        try:
            user32 = self._load_user32()
            kernel32 = self._load_kernel32()
            self._configure_api(user32, kernel32)

            process_id = wintypes.DWORD(0)
            # ``argtypes`` on the real ctypes function performs HWND coercion;
            # passing the plain integer also keeps injected/fake Win32 APIs
            # simple and backwards compatible in tests.
            user32.GetWindowThreadProcessId(
                int(hwnd),
                ctypes.byref(process_id),
            )
            if not process_id.value:
                return None

            process_handle = kernel32.OpenProcess(
                _PROCESS_QUERY_LIMITED_INFORMATION,
                False,
                process_id.value,
            )
            if not process_handle:
                return None

            buffer = ctypes.create_unicode_buffer(1024)
            buffer_size = wintypes.DWORD(len(buffer))
            if not kernel32.QueryFullProcessImageNameW(
                process_handle,
                0,
                buffer,
                ctypes.byref(buffer_size),
            ):
                return None
            return os.path.basename(buffer.value)
        except (AttributeError, OSError, OverflowError, TypeError, ValueError):
            return None
        finally:
            if process_handle:
                try:
                    self._load_kernel32().CloseHandle(process_handle)
                except (AttributeError, OSError, TypeError, ValueError):
                    pass

    def is_word_foreground(self) -> bool:
        """Return whether the current foreground process is Microsoft Word."""

        name = self.executable_name()
        return bool(name and name.casefold() == "winword.exe")

    def _load_user32(self) -> Any:
        return self._user32 or ctypes.WinDLL("user32", use_last_error=True)

    def _load_kernel32(self) -> Any:
        return self._kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)

    @staticmethod
    def _configure_api(user32: Any, kernel32: Any) -> None:
        """Set pointer-safe signatures for the real ctypes functions."""

        get_foreground_window = user32.GetForegroundWindow
        get_foreground_window.restype = wintypes.HWND

        get_window_thread_process_id = user32.GetWindowThreadProcessId
        get_window_thread_process_id.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_window_thread_process_id.restype = wintypes.DWORD

        open_process = kernel32.OpenProcess
        open_process.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        open_process.restype = wintypes.HANDLE

        query_process_name = kernel32.QueryFullProcessImageNameW
        query_process_name.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        query_process_name.restype = wintypes.BOOL

        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL


__all__ = ["ForegroundApplicationDetector"]
