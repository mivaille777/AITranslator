"""Manual Step8 harness for checking a slow translation does not freeze Qt."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence

from app.controller import AppController
from app.infrastructure.logging import configure_logging
from app.main import create_application
from app.models.selection import SelectedText
from app.models.translation import TranslationRequest, TranslationResult
from app.selection.manager import SelectionManager
from app.translation.base import TranslationProvider
from app.translation.manager import TranslationManager

DELAY_SECONDS = 2.0
MANUAL_TEXT = "This is a manual asynchronous translation test."


class FixedSelectionManager(SelectionManager):
    """Return fixed text so this manual check does not depend on clipboard."""

    def get_selected_text(self) -> SelectedText:
        return SelectedText(MANUAL_TEXT, provider="manual_async_test")


class SlowProvider(TranslationProvider):
    """Offline provider that simulates a 2-second remote API request."""

    def translate(self, request: TranslationRequest) -> TranslationResult:
        time.sleep(DELAY_SECONDS)
        return TranslationResult(
            source_text=request.source_text,
            translated_text=f"[ASYNC TEST] {request.source_text}",
            source_language=request.source_language,
            target_language=request.target_language,
            provider="manual-slow",
        )


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Run the offline Step8 asynchronous translation test."
    )


def main(argv: Sequence[str] | None = None) -> int:
    _build_parser().parse_args(None if argv is None else list(argv))
    application = create_application([sys.argv[0], *sys.argv[1:]])
    logger = configure_logging()
    controller = AppController(
        application,
        selection_manager=FixedSelectionManager(),
        translation_manager=TranslationManager(provider=SlowProvider()),
        logger=logger,
    )
    controller.start()

    print("Step8 async test ready: press Alt+Q to submit a 2-second translation.", flush=True)
    print(
        "During the delay, use the tray menu to show the test subtitle and drag "
        "the unlocked Overlay; the tray and GUI must remain responsive.",
        flush=True,
    )
    print("Exit from the tray menu (退出) or close the process with Ctrl+C.", flush=True)

    try:
        return application.exec()
    finally:
        controller.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
