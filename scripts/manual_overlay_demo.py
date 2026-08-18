"""Launch the Step1 overlay for manual desktop validation."""

from __future__ import annotations

import sys

from app.infrastructure.logging import configure_logging
from app.main import create_application
from app.overlay.window import DEFAULT_TEST_TEXT, OverlayWindow


def main() -> int:
    application = create_application([sys.argv[0], *sys.argv[1:]])
    logger = configure_logging()
    logger.info("manual_overlay_demo_started")

    overlay = OverlayWindow()
    overlay.center_on_screen()
    overlay.show_text(DEFAULT_TEST_TEXT)

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
