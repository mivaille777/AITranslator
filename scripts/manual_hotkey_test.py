"""Manual Step4 harness for validating the global Alt+Q trigger."""

from __future__ import annotations

import sys

from app.infrastructure.logging import configure_logging
from app.input.hotkey_manager import GlobalHotkeyManager
from app.main import create_application


def main() -> int:
    application = create_application([sys.argv[0], *sys.argv[1:]])
    logger = configure_logging()
    manager = GlobalHotkeyManager()

    def on_trigger(event) -> None:
        logger.info("HOTKEY_TRIGGERED hotkey=%s source=%s", event.hotkey, event.source)
        print("HOTKEY_TRIGGERED", flush=True)

    manager.triggered.connect(on_trigger)
    application.aboutToQuit.connect(manager.stop)
    try:
        manager.start()
    except Exception as exc:
        print(f"HOTKEY_START_FAILED: {exc}", flush=True)
        return 1

    print("Global hotkey test ready: press Alt+Q in Word, Chrome, or Notepad.", flush=True)
    print("Each accepted key action prints HOTKEY_TRIGGERED; close with Ctrl+C.", flush=True)
    try:
        return application.exec()
    finally:
        manager.stop()


if __name__ == "__main__":
    raise SystemExit(main())
