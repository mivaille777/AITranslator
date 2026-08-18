"""Tests for the Qt AI text worker boundary."""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QThreadPool, QTimer

from app.ai.models import AITextAction, AITextRequest, AITextResult
from app.ai.service import AITextService
from app.ai.task import AITextTask, AITextTaskFailure


class FakeSlowProvider:
    name = "fake-slow-ai"
    model = "fake-model"

    def __init__(self, delay: float = 0.15) -> None:
        self.delay = delay
        self.thread_ids: list[int] = []

    def execute(self, request: AITextRequest) -> AITextResult:
        self.thread_ids.append(threading.get_ident())
        time.sleep(self.delay)
        return AITextResult(
            source_text=request.source_text,
            output_text=f"ai:{request.source_text}",
            action=request.action,
            provider=self.name,
            model=self.model,
            source_language=request.source_language,
            target_language=request.target_language,
            style=request.style,
            request_id=request.request_id,
        )


class ExplodingService:
    def execute(self, _request: AITextRequest) -> AITextResult:
        raise RuntimeError("provider secret must stay inside the worker")


class MismatchedRequestService:
    def execute(self, request: AITextRequest) -> AITextResult:
        return AITextResult(
            source_text=request.source_text,
            output_text="ok",
            action=request.action,
            provider="fake",
            model="fake-model",
            request_id=-99,
        )


def _request(text: str, request_id: int = 0) -> AITextRequest:
    return AITextRequest(
        source_text=text,
        action=AITextAction.TRANSLATE,
        source_language="en",
        target_language="zh-CN",
        request_id=request_id,
    )


def test_slow_ai_request_runs_off_gui_thread_and_event_loop_stays_responsive(
    qapp,
    qtbot,
) -> None:
    provider = FakeSlowProvider()
    service = AITextService(provider=provider)
    pool = QThreadPool()
    task = AITextTask(service, _request("hello", request_id=7))
    results: list[AITextResult] = []
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
    assert results[0].output_text == "ai:hello"
    assert results[0].request_id == 7
    assert provider.thread_ids
    assert provider.thread_ids[0] != gui_thread_id
    assert heartbeat, "the Qt event loop did not process timer events while waiting"


def test_unexpected_exception_is_returned_as_safe_failure_signal(qapp, qtbot) -> None:
    pool = QThreadPool()
    task = AITextTask(ExplodingService(), _request("hello", request_id=11))
    failures: list[AITextTaskFailure] = []
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
    assert failures[0].request_id == 11
    assert failures[0].action is AITextAction.TRANSLATE
    assert str(failures[0].error) == "AI text task failed."
    assert "provider secret" not in str(failures[0].error)


def test_task_normalizes_request_id_from_compatible_service(qapp, qtbot) -> None:
    pool = QThreadPool()
    task = AITextTask(MismatchedRequestService(), _request("hello", request_id=23))
    results: list[AITextResult] = []
    completed: list[object] = []

    task.signals.succeeded.connect(results.append)
    task.signals.finished.connect(completed.append)

    try:
        pool.start(task)
        qtbot.waitUntil(lambda: bool(completed), timeout=2000)
    finally:
        pool.clear()
        pool.waitForDone(2000)

    assert len(results) == 1
    assert results[0].request_id == 23


def test_twenty_ai_tasks_complete_without_crashing(qapp, qtbot) -> None:
    service = AITextService(provider=FakeSlowProvider(delay=0.01))
    pool = QThreadPool()
    tasks = [AITextTask(service, _request(f"text-{index}", index)) for index in range(20)]
    results: list[AITextResult] = []
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
