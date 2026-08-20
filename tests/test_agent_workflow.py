"""Regression tests for AITranslator's LangGraph orchestration layer."""

from __future__ import annotations

from threading import Event

from app.agent.workflow import AITranslatorAgentGraph
from app.ai.chat.models import ChatContext, ChatRequest, ChatResult
from app.models.translation import TranslationResult


class FakeTranslationManager:
    def translate(
        self,
        source_text: str,
        source_language: str | None = None,
        target_language: str | None = None,
    ) -> TranslationResult:
        return TranslationResult(
            source_text=source_text,
            translated_text=f"translated:{source_text}",
            source_language=source_language or "auto",
            target_language=target_language or "zh-CN",
            provider="fake",
        )


class FakeStreamingChatService:
    provider_name = "fake-provider"
    model = "fake-model"

    def stream(self, request: ChatRequest):
        assert request.user_message == "hello"
        yield "Hello"
        yield " world"


def _request() -> ChatRequest:
    return ChatRequest(
        session_id="session-1",
        user_message="hello",
        context=ChatContext(source_text="source", translated_text="译文"),
        history=(),
        request_id=7,
    )


def test_translation_branch_runs_through_state_graph() -> None:
    workflow = AITranslatorAgentGraph()

    result = workflow.run_translation(
        FakeTranslationManager(),
        "hello",
        source_language="en",
        target_language="zh-CN",
        request_id=9,
    )

    assert result.translated_text == "translated:hello"
    assert result.source_language == "en"
    assert result.target_language == "zh-CN"
    assert result.request_id == 9


def test_chat_branch_streams_custom_chunks_and_final_result() -> None:
    workflow = AITranslatorAgentGraph()
    parts = list(workflow.stream_chat(FakeStreamingChatService(), _request()))

    custom = [part["data"] for part in parts if part.get("type") == "custom"]
    assert [item["delta"] for item in custom] == ["Hello", " world"]
    assert custom[-1]["accumulated_text"] == "Hello world"

    final: ChatResult | None = None
    for part in parts:
        if part.get("type") != "updates":
            continue
        for update in part.get("data", {}).values():
            candidate = update.get("chat_result") if isinstance(update, dict) else None
            if isinstance(candidate, ChatResult):
                final = candidate

    assert final is not None
    assert final.output_text == "Hello world"
    assert final.provider == "fake-provider"
    assert final.model == "fake-model"
    assert final.request_id == 7


def test_chat_branch_honors_pre_cancelled_run() -> None:
    workflow = AITranslatorAgentGraph()
    cancelled = Event()
    cancelled.set()

    parts = list(
        workflow.stream_chat(
            FakeStreamingChatService(),
            _request(),
            cancel_event=cancelled,
        )
    )

    assert not [part for part in parts if part.get("type") == "custom"]
    chat_updates = []
    for part in parts:
        if part.get("type") != "updates":
            continue
        chat_updates.extend(
            update
            for update in part.get("data", {}).values()
            if isinstance(update, dict) and "cancelled" in update
        )
    assert chat_updates
    assert chat_updates[-1]["cancelled"] is True
    assert chat_updates[-1]["status"] == "cancelled"
