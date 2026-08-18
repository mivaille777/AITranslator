"""Tests for the Step8 Qt translation worker boundary."""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QThreadPool, QTimer

from app.models.translation import TranslationRequest, TranslationResult
from app.translation.base import TranslationProvider
from app.translation.errors import TranslationError
from app.translation.manager import TranslationManager
from app.translation.task import TranslationTask, TranslationTaskFailure


class FakeSlowProvider(TranslationProvider):
    """Provider double that makes a worker request observable."""

    def __init__(self, delay: float = 0.15) -> None:
        self.delay = delay
        self.thread_ids: list[int] = []

    def translate(self, request: TranslationRequest) -> TranslationResult:
        self.thread_ids.append(threading.get_ident())
        time.sleep(self.delay)
        return TranslationResult(
            source_text=request.source_text,
            translated_text=f"slow:{request.source_text}",
            source_language=request.source_language,
            target_language=request.target_language,
            provider="fake-slow",
        )


class ExplodingProvider(TranslationProvider):
    """Provider double used to verify worker exceptions become signals."""

    def translate(self, _request: TranslationRequest) -> TranslationResult:
        raise RuntimeError("provider secret must stay inside the worker")


def test_slow_translation_runs_off_gui_thread_and_event_loop_stays_responsive(
    qapp,
    qtbot,
) -> None:
    provider = FakeSlowProvider()
    manager = TranslationManager(provider=provider)
    pool = QThreadPool()
    task = TranslationTask(manager, "hello")
    results: list[TranslationResult] = []
    completed: list[object] = []
    heartbeat: list[int] = []
    gui_thread_id = threading.get_ident()

    task.signals.succeeded.connect(results.append)
    task.signals.finished.connect(completed.append)
    timer = QTimer()
    timer.timeout.connect(lambda: heartbeat.append(threading.get_ident()))
    timer.start(10)

    try:
        pool.start(task)
        qtbot.waitUntil(lambda: bool(completed), timeout=2000)
    finally:
        timer.stop()
        pool.clear()
        pool.waitForDone(2000)

    assert len(results) == 1
    assert results[0].translated_text == "slow:hello"
    assert provider.thread_ids
    assert provider.thread_ids[0] != gui_thread_id
    assert heartbeat, "the Qt event loop did not process timer events while waiting"


def test_provider_exception_is_returned_as_failure_signal(qapp, qtbot) -> None:
    manager = TranslationManager(provider=ExplodingProvider())
    pool = QThreadPool()
    task = TranslationTask(manager, "hello")
    failures: list[TranslationTaskFailure] = []
    completed: list[object] = []

    task.signals.failed.connect(failures.append)
    task.signals.finished.connect(completed.append)

    try:
        pool.start(task)
        qtbot.waitUntil(lambda: bool(completed), timeout=2000)
    finally:
        pool.clear()
        pool.waitForDone(2000)

    assert len(failures) == 1
    assert failures[0].request_id == 0
    assert type(failures[0].error) is TranslationError


def test_twenty_translation_tasks_complete_without_crashing(qapp, qtbot) -> None:
    manager = TranslationManager(provider=FakeSlowProvider(delay=0.01))
    pool = QThreadPool()
    tasks = [TranslationTask(manager, f"text-{index}") for index in range(20)]
    results: list[TranslationResult] = []
    completed: list[object] = []

    for task in tasks:
        task.signals.succeeded.connect(results.append)
        task.signals.finished.connect(completed.append)

    try:
        for task in tasks:
            pool.start(task)
        qtbot.waitUntil(lambda: len(completed) == 20, timeout=3000)
    finally:
        pool.clear()
        pool.waitForDone(3000)

    assert len(results) == 20
    assert len(completed) == 20
