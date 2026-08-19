"""pytest-qt coverage for the system tray and controller wiring."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from app.controller import AppController
from app.ui.tray import TrayManager


class FakeOverlayManager:
    """Small service double so tray tests never depend on a real window."""

    def __init__(self) -> None:
        self.is_locked = False
        self.show_text_calls = 0
        self.show_overlay_calls = 0
        self.hide_calls = 0

    def lock_overlay(self) -> bool:
        self.is_locked = True
        return True

    def unlock_overlay(self) -> bool:
        self.is_locked = False
        return True

    def show_text(self, _text: str) -> None:
        self.show_text_calls += 1

    def show_overlay(self) -> None:
        self.show_overlay_calls += 1

    def hide_overlay(self) -> None:
        self.hide_calls += 1


def _make_tray(qapp: QApplication) -> TrayManager:
    manager = TrayManager(parent=qapp)
    manager.hide()
    return manager


def test_tray_manager_creates_required_actions(qapp: QApplication) -> None:
    manager = _make_tray(qapp)

    assert manager.tray_icon is not None
    assert manager.menu is not None
    action_texts = {
        action.text()
        for action in manager.menu.actions()
        if not action.isSeparator()
    }
    assert action_texts == {
        "启用翻译",
        "暂停翻译",
        "自动划词翻译",
        "锁定 Overlay",
        "解锁 Overlay",
        "显示浮窗",
        "隐藏浮窗",
        "设置",
        "退出",
    }


def test_show_overlay_action_emits_real_visibility_intent(qapp: QApplication) -> None:
    manager = _make_tray(qapp)
    events: list[str] = []
    manager.show_overlay_requested.connect(lambda: events.append("show"))

    manager.actions["show_overlay"].trigger()

    assert events == ["show"]


def test_double_clicking_tray_icon_emits_show_overlay_intent(qapp: QApplication) -> None:
    manager = _make_tray(qapp)
    events: list[str] = []
    manager.show_overlay_requested.connect(lambda: events.append("show"))

    # A normal click must not restore the Overlay; only the OS double-click
    # activation should emit the visibility intent.
    manager.tray_icon.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
    assert events == []

    manager.tray_icon.activated.emit(QSystemTrayIcon.ActivationReason.DoubleClick)
    assert events == ["show"]


def test_lock_and_unlock_actions_emit_intents(qapp: QApplication) -> None:
    manager = _make_tray(qapp)
    events: list[str] = []
    manager.lock_overlay_requested.connect(lambda: events.append("lock"))
    manager.unlock_overlay_requested.connect(lambda: events.append("unlock"))

    manager.set_overlay_locked(False)
    manager.actions["lock_overlay"].trigger()
    manager.set_overlay_locked(True)
    manager.actions["unlock_overlay"].trigger()

    assert events == ["lock", "unlock"]


def test_exit_action_calls_application_exit_logic(qapp: QApplication) -> None:
    tray = _make_tray(qapp)
    overlay = FakeOverlayManager()
    controller = AppController(
        qapp,
        overlay_manager=overlay,
        tray_manager=tray,
    )

    with patch.object(QApplication, "quit", autospec=True) as quit_method:
        tray.actions["exit"].trigger()

    quit_method.assert_called_once_with()
    controller.shutdown()
