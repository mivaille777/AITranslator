"""Offline Step17 stress harness: 100 randomized translation workers.

Run from the project root with ``python scripts/stability_stress_test.py``.
It never contacts Google and is safe to use while the normal application is
closed or running.
"""

from __future__ import annotations

import random
import sys
import time
from collections.abc import Sequence

from PySide6.QtCore import QThreadPool, QTimer

from app.infrastructure.logging import configure_logging
from app.main import create_application
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.cache import TranslationCache
from app.translation.errors import TranslationError
from app.translation.manager import TranslationManager
from app.translation.task import TranslationTask

REQUEST_COUNT = 100
TIMEOUT_MILLISECONDS = 15000


class RandomStressProvider(TranslationProvider):
    """Simulate variable latency and intermittent provider failures."""

    def __init__(self) -> None:
        self.random = random.Random(17)

    def translate(self, request: TranslationRequest) -> TranslationResult:
        delay = 0.04 if request.request_id == REQUEST_COUNT else self.random.uniform(0, 0.008)
        time.sleep(delay)
        if request.request_id != REQUEST_COUNT and self.random.random() < 0.2:
            raise TranslationError("simulated provider failure")
        return TranslationResult(
            source_text=request.source_text,
            translated_text=f"translated:{request.source_text}",
            source_language=request.source_language,
            target_language=request.target_language,
            provider="stress",
            request_id=request.request_id,
        )


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    application = create_application([sys.argv[0]])
    # Worker failures intentionally exercise the logger; keep this manual
    # command's result summary readable while retaining normal app logging.
    logger = configure_logging(level="CRITICAL")
    manager = TranslationManager(
        provider=RandomStressProvider(),
        cache=TranslationCache(enabled=False),
        logger=logger,
    )
    pool = QThreadPool()
    tasks: list[TranslationTask] = []
    completed: list[object] = []
    latest_result: list[TranslationResult] = []

    for request_id in range(1, REQUEST_COUNT + 1):
        task = TranslationTask(
            manager,
            f"stress-{request_id - 1:03d}",
            request_id=request_id,
            logger=logger,
        )
        task.signals.succeeded.connect(
            lambda result: (
                latest_result.append(result)
                if isinstance(result, TranslationResult)
                and result.request_id == REQUEST_COUNT
                else None
            )
        )
        task.signals.finished.connect(completed.append)
        tasks.append(task)

    timed_out = [False]
    deadline_timer = QTimer()
    deadline_timer.setSingleShot(True)
    deadline_timer.timeout.connect(lambda: (timed_out.__setitem__(0, True), application.quit()))
    completion_timer = QTimer()
    completion_timer.setInterval(10)
    completion_timer.timeout.connect(
        lambda: application.quit() if len(completed) == REQUEST_COUNT else None
    )

    try:
        for task in tasks:
            pool.start(task)
        deadline_timer.start(TIMEOUT_MILLISECONDS)
        completion_timer.start()
        application.exec()
    finally:
        deadline_timer.stop()
        completion_timer.stop()
        pool.waitForDone(5000)
        manager.close()

    workers_stopped = pool.activeThreadCount() == 0
    passed = (
        not timed_out[0]
        and len(completed) == REQUEST_COUNT
        and workers_stopped
        and len(latest_result) == 1
        and latest_result[0].translated_text == "translated:stress-099"
    )
    if passed:
        print(
            "stability_stress_passed "
            f"requests={len(completed)} latest_request_id={latest_result[0].request_id} "
            f"workers_stopped={workers_stopped}"
        )
        return 0

    print(
        "stability_stress_failed "
        f"completed={len(completed)} latest_results={len(latest_result)} "
        f"workers_stopped={workers_stopped} timed_out={timed_out[0]}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
