"""Unit tests for the mocked Windows overlay adapter."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.overlay.win32_adapter import Win32OverlayAdapter


class FakeWindow:
    def winId(self) -> int:  # noqa: N802 - Qt-compatible test double
        return 123


def test_win32_adapter_applies_and_restores_locked_state() -> None:
    user32 = MagicMock()
    user32.GetWindowLongPtrW.return_value = 0x100
    user32.SetWindowLongPtrW.return_value = 0x200
    user32.SetWindowPos.return_value = 1
    adapter = Win32OverlayAdapter(user32, platform_name="win32")
    window = FakeWindow()

    assert adapter.is_available
    assert adapter.set_locked(window, locked=True)
    assert adapter.set_locked(window, locked=True)
    assert user32.SetWindowLongPtrW.call_count == 2
    assert user32.SetWindowPos.called

    assert adapter.set_locked(window, locked=False)
    assert user32.SetWindowLongPtrW.call_count == 4
    assert user32.SetWindowPos.call_count == 2


def test_win32_adapter_is_a_noop_off_windows() -> None:
    user32 = MagicMock()
    adapter = Win32OverlayAdapter(user32, platform_name="linux")
    window = FakeWindow()

    assert not adapter.is_available
    assert not adapter.set_topmost(window)
    assert not adapter.set_locked(window, locked=True)
    user32.SetWindowPos.assert_not_called()
    user32.SetWindowLongPtrW.assert_not_called()
