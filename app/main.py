"""Application bootstrap for the desktop translator."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.ai.adaptive_research_controller import AdaptiveResearchAgentAppController
from app.infrastructure.logging import configure_logging, sanitized_exception_info
from app.infrastructure.instance_lock import SingleInstanceLock
from app.infrastructure.paths import ensure_runtime_directories

APPLICATION_NAME = "Desktop Translator"
ORGANIZATION_NAME = "AITranslator"


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Create or reuse the process-wide Qt application instance."""

    application = QApplication.instance()
    if application is None:
        qt_argv = list(sys.argv if argv is None else argv)
        application = QApplication(qt_argv)

    application.setApplicationName(APPLICATION_NAME)
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setQuitOnLastWindowClosed(False)
    return application


def schedule_smoke_exit(application: QApplication) -> None:
    """Schedule a clean event-loop exit for command-line smoke validation."""

    QTimer.singleShot(0, application.quit)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=APPLICATION_NAME)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="start QApplication, enter the event loop, and exit immediately",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the Qt event loop and return its exit code."""

    parser = _build_argument_parser()
    parsed = parser.parse_args(None if argv is None else list(argv))

    qt_argv = sys.argv if argv is None else [sys.argv[0], *list(argv)]
    application = create_application(qt_argv)
    ensure_runtime_directories()
    logger = configure_logging()
    logger.info("application_started smoke_test=%s", parsed.smoke_test)

    instance_lock: SingleInstanceLock | None = None
    if not parsed.smoke_test:
        instance_lock = SingleInstanceLock()
        if not instance_lock.acquire():
            logger.error("application_already_running")
            return 1

    controller: AdaptiveResearchAgentAppController | None = None
    exit_code = 0
    try:
        controller = AdaptiveResearchAgentAppController(
            application,
            logger=logger,
        )
        controller.start(start_hotkey=not parsed.smoke_test)

        if parsed.smoke_test:
            schedule_smoke_exit(application)

        exit_code = application.exec()
    except Exception as exc:
        logger.error(
            "application_runtime_failed error_type=%s",
            type(exc).__name__,
            exc_info=sanitized_exception_info(exc),
        )
        exit_code = 1
    finally:
        if controller is not None:
            try:
                controller.shutdown()
            except Exception as exc:
                logger.error(
                    "application_shutdown_failed error_type=%s",
                    type(exc).__name__,
                    exc_info=sanitized_exception_info(exc),
                )
                exit_code = 1
        if instance_lock is not None:
            try:
                instance_lock.release()
            except Exception as exc:
                logger.error(
                    "instance_lock_release_failed error_type=%s",
                    type(exc).__name__,
                    exc_info=sanitized_exception_info(exc),
                )
                exit_code = 1

    logger.info("application_stopped exit_code=%s", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
