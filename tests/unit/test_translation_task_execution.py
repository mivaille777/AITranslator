"""Regression tests for the production translation worker boundary."""

from __future__ import annotations

from app.agent.workflow import DEFAULT_AGENT_GRAPH
from app.models.translation import TranslationRequest, TranslationResult
from app.translation.manager import TranslationManager
from app.translation.task import TranslationTask


class DirectFakeProvider:
    name = "direct-fake"

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return TranslationResult(
            source_text=request.source_text,
            translated_text=f"译文:{request.source_text}",
            source_language=request.source_language,
            target_language=request.target_language,
            provider=self.name,
            request_id=request.request_id,
        )


def test_translation_task_bypasses_agent_graph(monkeypatch) -> None:
    """Manual/selection translation must not depend on LangGraph execution."""

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("deterministic translation must not route through LangGraph")

    monkeypatch.setattr(DEFAULT_AGENT_GRAPH, "run_translation", fail_if_called)
    manager = TranslationManager(
        provider=DirectFakeProvider(),
        sqlite_enabled=False,
    )
    task = TranslationTask(
        manager,
        "hello",
        source_language="en",
        target_language="zh-CN",
        request_id=17,
    )

    result = task._translate()

    assert result.translated_text == "译文:hello"
    assert result.request_id == 17
    assert result.provider == "direct-fake"


def test_translation_task_keeps_request_version_on_direct_provider() -> None:
    manager = TranslationManager(
        provider=DirectFakeProvider(),
        sqlite_enabled=False,
    )
    task = TranslationTask(manager, "hello", request_id=23)

    results: list[TranslationResult] = []
    failures: list[object] = []
    task.signals.succeeded.connect(results.append)
    task.signals.failed.connect(failures.append)
    task.run()

    assert failures == []
    assert results
    assert results[-1].request_id == 23
