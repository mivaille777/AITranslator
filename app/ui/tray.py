"""System tray user interface for the desktop translator."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

TRAY_TOOLTIP = "Desktop Translator"


def _create_default_icon() -> QIcon:
    """Create a small self-contained tray icon without external assets."""

    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor("#2563EB"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor("#FFFFFF"), 2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(5, 5, 22, 22)
    painter.drawLine(16, 9, 16, 23)
    painter.end()

    return QIcon(pixmap)


class TrayManager(QObject):
    """Own the tray icon and emit intent signals for the application layer."""

    enable_translation_requested = Signal()
    pause_translation_requested = Signal()
    auto_selection_requested = Signal(bool)
    lock_overlay_requested = Signal()
    unlock_overlay_requested = Signal()
    show_overlay_requested = Signal()
    # Retained as a compatibility signal for older injected controllers. The
    # production tray action no longer emits a synthetic test-subtitle intent.
    show_test_text_requested = Signal()
    hide_overlay_requested = Signal()
    settings_requested = Signal()
    exit_requested = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        tray_icon: QSystemTrayIcon | None = None,
        icon: QIcon | None = None,
    ) -> None:
        super().__init__(parent)

        self._tray_icon = tray_icon or QSystemTrayIcon(
            icon or _create_default_icon(),
            self,
        )
        self._tray_icon.setToolTip(TRAY_TOOLTIP)
        self._menu = QMenu()
        self._menu.setObjectName("TrayMenu")

        self._enable_translation_action = self._create_action(
            "启用翻译",
            "EnableTranslationAction",
            checkable=True,
        )
        self._pause_translation_action = self._create_action(
            "暂停翻译",
            "PauseTranslationAction",
            checkable=True,
        )
        self._translation_mode_group = QActionGroup(self)
        self._translation_mode_group.setExclusive(True)
        self._translation_mode_group.addAction(self._enable_translation_action)
        self._translation_mode_group.addAction(self._pause_translation_action)
        self._enable_translation_action.setChecked(True)

        self._auto_selection_action = self._create_action(
            "自动划词翻译",
            "AutoSelectionAction",
            checkable=True,
        )

        self._lock_overlay_action = self._create_action(
            "锁定 Overlay",
            "LockOverlayAction",
        )
        self._unlock_overlay_action = self._create_action(
            "解锁 Overlay",
            "UnlockOverlayAction",
        )
        self._unlock_overlay_action.setEnabled(False)

        self._show_overlay_action = self._create_action(
            "显示浮窗",
            "ShowOverlayAction",
        )
        self._hide_overlay_action = self._create_action(
            "隐藏浮窗",
            "HideOverlayAction",
        )
        self._hide_overlay_action.setEnabled(False)

        self._settings_action = self._create_action("设置", "SettingsAction")
        self._exit_action = self._create_action("退出", "ExitAction")

        self._menu.addAction(self._enable_translation_action)
        self._menu.addAction(self._pause_translation_action)
        self._menu.addAction(self._auto_selection_action)
        self._menu.addSeparator()
        self._menu.addAction(self._lock_overlay_action)
        self._menu.addAction(self._unlock_overlay_action)
        self._menu.addSeparator()
        self._menu.addAction(self._show_overlay_action)
        self._menu.addAction(self._hide_overlay_action)
        self._menu.addSeparator()
        self._menu.addAction(self._settings_action)
        self._menu.addAction(self._exit_action)
        self._tray_icon.setContextMenu(self._menu)

        self._enable_translation_action.triggered.connect(
            self._emit_enable_translation,
        )
        self._pause_translation_action.triggered.connect(
            self._emit_pause_translation,
        )
        self._auto_selection_action.toggled.connect(
            self._emit_auto_selection,
        )
        self._lock_overlay_action.triggered.connect(self._emit_lock_overlay)
        self._unlock_overlay_action.triggered.connect(self._emit_unlock_overlay)
        self._show_overlay_action.triggered.connect(self._emit_show_overlay)
        self._hide_overlay_action.triggered.connect(self._emit_hide_overlay)
        self._settings_action.triggered.connect(self._emit_settings)
        self._exit_action.triggered.connect(self._emit_exit)

    @staticmethod
    def _create_action(
        text: str,
        object_name: str,
        *,
        checkable: bool = False,
    ) -> QAction:
        action = QAction(text)
        action.setObjectName(object_name)
        action.setCheckable(checkable)
        return action

    @property
    def tray_icon(self) -> QSystemTrayIcon:
        return self._tray_icon

    @property
    def menu(self) -> QMenu:
        return self._menu

    @property
    def actions(self) -> dict[str, QAction]:
        actions = {
            "enable_translation": self._enable_translation_action,
            "pause_translation": self._pause_translation_action,
            "auto_selection": self._auto_selection_action,
            "lock_overlay": self._lock_overlay_action,
            "unlock_overlay": self._unlock_overlay_action,
            "show_overlay": self._show_overlay_action,
            "hide_overlay": self._hide_overlay_action,
            "settings": self._settings_action,
            "exit": self._exit_action,
        }
        # Preserve test/integration lookup compatibility while showing the new
        # user-facing semantic name and behavior.
        actions["show_test_text"] = self._show_overlay_action
        return actions

    def show(self) -> None:
        self._tray_icon.show()

    def hide(self) -> None:
        self._tray_icon.hide()

    def set_translation_enabled(self, enabled: bool) -> None:
        enable_was_blocked = self._enable_translation_action.blockSignals(True)
        pause_was_blocked = self._pause_translation_action.blockSignals(True)
        try:
            self._enable_translation_action.setChecked(enabled)
            self._pause_translation_action.setChecked(not enabled)
        finally:
            self._enable_translation_action.blockSignals(enable_was_blocked)
            self._pause_translation_action.blockSignals(pause_was_blocked)

    def set_auto_selection_enabled(self, enabled: bool) -> None:
        was_blocked = self._auto_selection_action.blockSignals(True)
        try:
            self._auto_selection_action.setChecked(bool(enabled))
        finally:
            self._auto_selection_action.blockSignals(was_blocked)

    def set_overlay_locked(self, locked: bool) -> None:
        self._lock_overlay_action.setEnabled(not locked)
        self._unlock_overlay_action.setEnabled(locked)

    def set_overlay_visible(self, visible: bool) -> None:
        self._show_overlay_action.setEnabled(not visible)
        self._hide_overlay_action.setEnabled(visible)

    def _emit_enable_translation(self, _checked: bool = False) -> None:
        self.enable_translation_requested.emit()

    def _emit_pause_translation(self, _checked: bool = False) -> None:
        self.pause_translation_requested.emit()

    def _emit_auto_selection(self, checked: bool) -> None:
        self.auto_selection_requested.emit(bool(checked))

    def _emit_lock_overlay(self, _checked: bool = False) -> None:
        self.lock_overlay_requested.emit()

    def _emit_unlock_overlay(self, _checked: bool = False) -> None:
        self.unlock_overlay_requested.emit()

    def _emit_show_overlay(self, _checked: bool = False) -> None:
        self.show_overlay_requested.emit()

    def _emit_hide_overlay(self, _checked: bool = False) -> None:
        self.hide_overlay_requested.emit()

    def _emit_settings(self, _checked: bool = False) -> None:
        self.settings_requested.emit()

    def _emit_exit(self, _checked: bool = False) -> None:
        self.exit_requested.emit()
