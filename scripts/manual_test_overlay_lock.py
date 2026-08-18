"""Manual Step2 harness for testing overlay lock, click-through, and drag."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from app.infrastructure.logging import configure_logging
from app.main import create_application
from app.overlay.window import DEFAULT_TEST_TEXT, OverlayWindow


class OverlayLockManualWindow(QWidget):
    """Small control panel used to switch the overlay between two states."""

    def __init__(self, overlay: OverlayWindow) -> None:
        super().__init__()
        self._overlay = overlay
        self.setWindowTitle("Overlay Lock Manual Test")
        self.setMinimumWidth(360)

        self._status = QLabel(self)
        self._status.setWordWrap(True)

        lock_button = QPushButton("Lock overlay", self)
        unlock_button = QPushButton("Unlock overlay", self)
        show_button = QPushButton("Show overlay", self)
        hide_button = QPushButton("Hide overlay", self)
        exit_button = QPushButton("Exit", self)

        lock_button.clicked.connect(self._lock_overlay)
        unlock_button.clicked.connect(self._unlock_overlay)
        show_button.clicked.connect(self._show_overlay)
        hide_button.clicked.connect(self._overlay.hide_overlay)
        exit_button.clicked.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Current overlay state:", self))
        layout.addWidget(self._status)
        layout.addWidget(lock_button)
        layout.addWidget(unlock_button)
        layout.addWidget(show_button)
        layout.addWidget(hide_button)
        layout.addWidget(exit_button)

        self._report_state()

    def _report_state(self, message: str | None = None) -> None:
        state = "LOCKED" if self._overlay.is_locked else "UNLOCKED"
        if self._overlay.is_locked:
            detail = "鼠标应穿透 Overlay，下面的 Notepad 应收到点击。"
        else:
            detail = "Overlay 可接收鼠标输入，按住左键可以拖动。"
        text = f"{state}\n{message + chr(10) if message else ''}{detail}"
        self._status.setText(text)
        print(f"STATE: {state} | {message or detail}", flush=True)

    def _lock_overlay(self) -> None:
        if self._overlay.lock_overlay():
            self._report_state()
        else:
            self._report_state("LOCK FAILED: Windows overlay API unavailable")

    def _unlock_overlay(self) -> None:
        if self._overlay.unlock_overlay():
            self._report_state()
        else:
            self._report_state("UNLOCK FAILED: Windows overlay API unavailable")

    def _show_overlay(self) -> None:
        self._overlay.show_overlay()
        self._report_state("Overlay shown")

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name
        self._overlay.close()
        super().closeEvent(event)
        application = QApplication.instance()
        if application is not None:
            application.quit()


def main() -> int:
    application = create_application([sys.argv[0], *sys.argv[1:]])
    logger = configure_logging()
    logger.info("manual_overlay_lock_test_started")

    overlay = OverlayWindow()
    overlay.center_on_screen()
    overlay.show_text(DEFAULT_TEST_TEXT)

    control = OverlayLockManualWindow(overlay)
    control.show()
    print("Manual Step2 test ready: use the control panel buttons.", flush=True)
    print("LOCKED -> click the overlay area; UNLOCKED -> drag with left mouse.", flush=True)

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
