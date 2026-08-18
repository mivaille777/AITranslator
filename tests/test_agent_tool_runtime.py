"""Regression tests for LangGraph Tool routing and chat grounding."""

from __future__ import annotations

from app.agent.tool_runtime import AgentToolCoordinator, PICK_DOCUMENT_COMMAND
from app.agent.tools.base import ToolResult
from app.ai.chat.models import ChatContext, ChatRequest
from app.ai.chat.service import build_chat_prompt


class FakeDocumentTools:
    current = None

    def open_file(self, path: str):
        return ToolResult("open_file", True, f"opened:{path}", {"document_name": "demo.txt"})

    def read_document(self, max_chars: int = 12000, offset: int = 0):
        return ToolResult("read_document", True, "document body")

    def extract_document_text(self, max_chars: int = 500000):
        return ToolResult("extract_document_text", True, "full document")

    def search_document(self, query: str, max_results: int = 5):
        return ToolResult("search_document", True, f"match:{query}")

    def summarize_document(self, max_chars: int = 28000):
        return ToolResult(
            "summarize_document",
            True,
            "bounded summary evidence",
            {"requires_llm": True, "instruction": "summarize only from evidence"},
        )


class FakeWebTools:
    def web_search(self, query: str, max_results: int = 5):
        return ToolResult(
            "web_search",
            True,
            f"[1] result for {query}",
            {"requires_llm": True},
        )

    def web_read(self, url: str, max_chars: int = 60000):
        return ToolResult("web_read", True, f"page:{url}", {"requires_llm": True})


def _runtime() -> AgentToolCoordinator:
    return AgentToolCoordinator(document_tools=FakeDocumentTools(), web_tools=FakeWebTools())


def test_open_document_without_path_requests_gui_file_picker() -> None:
    plan = _runtime().plan_message("帮我打开文档")

    assert plan.handled
    assert plan.tool_name == "open_file"
    assert plan.requires_file_picker


def test_open_document_with_selected_file_executes_registry() -> None:
    outcome = _runtime().execute_message("打开文档", selected_file="D:/docs/demo.txt")

    assert outcome.handled
    assert not outcome.requires_llm
    assert outcome.assistant_message == "opened:D:/docs/demo.txt"


def test_document_summary_routes_to_llm_grounded_observation() -> None:
    outcome = _runtime().execute_message("总结这个文档")

    assert outcome.handled
    assert outcome.tool_name == "summarize_document"
    assert outcome.requires_llm
    assert "bounded summary evidence" in outcome.tool_context


def test_web_search_routes_query_to_web_tool() -> None:
    outcome = _runtime().execute_message("联网搜索 LangGraph ToolNode")

    assert outcome.handled
    assert outcome.tool_name == "web_search"
    assert outcome.requires_llm
    assert "LangGraph ToolNode" in outcome.tool_context


def test_chat_prompt_keeps_tool_observation_separate_from_user_message() -> None:
    request = ChatRequest(
        session_id="session-1",
        user_message="总结一下",
        context=ChatContext(),
        tool_name="summarize_document",
        tool_context="tool_observation:\nDocument evidence",
    )

    prompt = build_chat_prompt(request)

    assert '"current_user_message": "总结一下"' in prompt
    assert '"tool_name": "summarize_document"' in prompt
    assert "Document evidence" in prompt
