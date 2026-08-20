"""LangGraph routing and execution for document/web Agent tools."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent.tools import AgentToolRegistry, DocumentTools, ToolResult, WebTools


ToolIntent = Literal[
    "none",
    "open_file",
    "read_document",
    "extract_document_text",
    "search_document",
    "summarize_document",
    "web_search",
    "web_read",
]

PICK_DOCUMENT_COMMAND = "pick_document"
MAX_TOOL_OBSERVATION_CHARS = 60_000


@dataclass(frozen=True, slots=True)
class AgentToolPlan:
    handled: bool
    intent: ToolIntent = "none"
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    requires_file_picker: bool = False
    user_message: str = ""


@dataclass(frozen=True, slots=True)
class AgentToolOutcome:
    handled: bool
    tool_name: str = ""
    result: ToolResult | None = None
    assistant_message: str = ""
    tool_context: str = ""
    requires_llm: bool = False
    ui_command: str = ""


class AgentToolState(TypedDict, total=False):
    user_message: str
    selected_file: str
    intent: ToolIntent
    tool_name: str
    tool_args: dict[str, Any]
    handled: bool
    ui_command: str
    tool_result: ToolResult


_OPEN_FILE_PHRASES = (
    "打开文件",
    "打开一个文件",
    "打开文档",
    "打开一个文档",
    "选择文件",
    "选择文档",
    "读取这个文件",
    "open file",
    "open document",
)
_READ_DOCUMENT_PHRASES = (
    "读取文档",
    "读一下文档",
    "阅读文档",
    "看看文档",
    "读这个文档",
    "read document",
)
_EXTRACT_DOCUMENT_PHRASES = (
    "提取文档文本",
    "提取全文",
    "导出文档文本",
    "extract document text",
)
_SUMMARIZE_DOCUMENT_PHRASES = (
    "总结文档",
    "总结这个文档",
    "总结一下文档",
    "总结这个文件",
    "总结一下这个文件",
    "概括文档",
    "概括这个文档",
    "文档总结",
    "summarize document",
    "summarise document",
)
_SEARCH_DOCUMENT_PHRASES = (
    "搜索文档",
    "文档里搜索",
    "文档中搜索",
    "文档内搜索",
    "在文档里找",
    "在文档中找",
    "查找文档",
    "search document",
)
_WEB_SEARCH_PHRASES = (
    "联网搜索",
    "搜索网络",
    "网页搜索",
    "网上搜索",
    "上网搜索",
    "网上查",
    "上网查",
    "帮我搜索",
    "搜索一下",
    "web search",
    "search web",
    "search online",
)
_WEB_READ_PHRASES = (
    "读取网页",
    "打开网页",
    "看看这个网页",
    "阅读网页",
    "总结这个网页",
    "总结网页",
    "read webpage",
    "read this page",
)
_URL_RE = re.compile(r"https?://[^\s<>\]\[\)\(\"']+", re.IGNORECASE)
_WINDOWS_PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\[^\r\n\"']+?\.(?:pdf|docx|txt|md|markdown))",
    re.IGNORECASE,
)
_QUOTED_PATH_RE = re.compile(
    r"[\"']([^\"']+\.(?:pdf|docx|txt|md|markdown))[\"']",
    re.IGNORECASE,
)


def _normalize(message: object) -> str:
    return " ".join(str(message or "").strip().split())


def _contains_any(lowered: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in lowered for phrase in phrases)


def _extract_path(message: str) -> str:
    quoted = _QUOTED_PATH_RE.search(message)
    if quoted:
        return quoted.group(1).strip()
    windows = _WINDOWS_PATH_RE.search(message)
    if windows:
        return windows.group(0).strip().rstrip(".,，。")
    return ""


def _extract_url(message: str) -> str:
    match = _URL_RE.search(message)
    return match.group(0).rstrip(".,，。") if match else ""


def _strip_request_prefix(message: str, phrases: tuple[str, ...]) -> str:
    text = _normalize(message)
    lowered = text.lower()
    best_index = -1
    best_phrase = ""
    for phrase in phrases:
        index = lowered.find(phrase)
        if index >= 0 and (best_index < 0 or index < best_index):
            best_index = index
            best_phrase = phrase
    if best_index < 0:
        return text
    remainder = text[best_index + len(best_phrase) :]
    remainder = re.sub(r"^[：:，,。\s]+", "", remainder).strip()
    return remainder


def _document_search_query(message: str) -> str:
    query = _strip_request_prefix(message, _SEARCH_DOCUMENT_PHRASES)
    query = re.sub(r"^(?:一下|一下子|内容|关键词)\s*", "", query).strip()
    return query


def _web_search_query(message: str) -> str:
    query = _strip_request_prefix(message, _WEB_SEARCH_PHRASES)
    query = re.sub(r"^(?:一下|一下子|关于)\s*", "", query).strip()
    return query


class AgentToolGraph:
    """Classify one tool intent and execute it through a stable registry."""

    def __init__(self, registry: AgentToolRegistry) -> None:
        self.registry = registry
        builder = StateGraph(AgentToolState)
        builder.add_node("classify", self._classify_node)
        builder.add_node("execute", self._execute_node)
        builder.add_node("no_tool", self._no_tool_node)
        builder.add_edge(START, "classify")
        builder.add_conditional_edges(
            "classify",
            self._route,
            {"execute": "execute", "no_tool": "no_tool"},
        )
        builder.add_edge("execute", END)
        builder.add_edge("no_tool", END)
        self.graph = builder.compile()

    @staticmethod
    def classify_message(message: object, *, selected_file: str = "") -> AgentToolPlan:
        text = _normalize(message)
        lowered = text.lower()
        if not text:
            return AgentToolPlan(False, user_message=text)

        url = _extract_url(text)
        if url and _contains_any(lowered, _WEB_READ_PHRASES):
            return AgentToolPlan(
                True,
                "web_read",
                "web_read",
                {"url": url},
                False,
                text,
            )

        if _contains_any(lowered, _OPEN_FILE_PHRASES):
            path = str(selected_file or _extract_path(text)).strip()
            return AgentToolPlan(
                True,
                "open_file",
                "open_file",
                {"path": path} if path else {},
                not bool(path),
                text,
            )

        if _contains_any(lowered, _SUMMARIZE_DOCUMENT_PHRASES):
            return AgentToolPlan(True, "summarize_document", "summarize_document", {}, False, text)

        if _contains_any(lowered, _EXTRACT_DOCUMENT_PHRASES):
            return AgentToolPlan(
                True,
                "extract_document_text",
                "extract_document_text",
                {},
                False,
                text,
            )

        if _contains_any(lowered, _SEARCH_DOCUMENT_PHRASES):
            query = _document_search_query(text)
            return AgentToolPlan(
                True,
                "search_document",
                "search_document",
                {"query": query},
                False,
                text,
            )

        if _contains_any(lowered, _READ_DOCUMENT_PHRASES):
            return AgentToolPlan(True, "read_document", "read_document", {}, False, text)

        if _contains_any(lowered, _WEB_SEARCH_PHRASES):
            query = _web_search_query(text)
            return AgentToolPlan(
                True,
                "web_search",
                "web_search",
                {"query": query},
                False,
                text,
            )

        return AgentToolPlan(False, user_message=text)

    def _classify_node(self, state: AgentToolState) -> AgentToolState:
        plan = self.classify_message(
            state.get("user_message", ""),
            selected_file=str(state.get("selected_file", "")),
        )
        return {
            "intent": plan.intent,
            "tool_name": plan.tool_name,
            "tool_args": dict(plan.tool_args),
            "handled": plan.handled,
            "ui_command": PICK_DOCUMENT_COMMAND if plan.requires_file_picker else "",
        }

    @staticmethod
    def _route(state: AgentToolState) -> Literal["execute", "no_tool"]:
        if state.get("handled") and state.get("tool_name") and not state.get("ui_command"):
            return "execute"
        return "no_tool"

    def _execute_node(self, state: AgentToolState) -> AgentToolState:
        result = self.registry.invoke(
            str(state.get("tool_name", "")),
            **dict(state.get("tool_args", {})),
        )
        user_message = _normalize(state.get("user_message", ""))
        if (
            result.ok
            and str(state.get("tool_name", "")) == "open_file"
            and ("总结" in user_message or "summar" in user_message.lower())
        ):
            summary = self.registry.invoke("summarize_document")
            if summary.ok:
                result = ToolResult(
                    name="summarize_document",
                    ok=True,
                    content=summary.content,
                    metadata={**summary.metadata, "opened_document": result.metadata},
                )
        return {"tool_result": result, "handled": True}

    @staticmethod
    def _no_tool_node(state: AgentToolState) -> AgentToolState:
        return {"handled": bool(state.get("handled", False))}

    def invoke(self, message: object, *, selected_file: str = "") -> AgentToolState:
        return self.graph.invoke(
            {
                "user_message": _normalize(message),
                "selected_file": str(selected_file or ""),
                "handled": False,
            }
        )


class AgentToolCoordinator:
    """Own document/web capabilities and convert tool results into chat observations."""

    def __init__(
        self,
        *,
        document_tools: DocumentTools | None = None,
        web_tools: WebTools | None = None,
        registry: AgentToolRegistry | None = None,
    ) -> None:
        self.document_tools = document_tools or DocumentTools()
        self.web_tools = web_tools or WebTools()
        self.registry = registry or AgentToolRegistry()
        self._register_defaults()
        self.workflow = AgentToolGraph(self.registry)

    def _register_defaults(self) -> None:
        self.registry.register("open_file", self.document_tools.open_file, description="Open PDF/DOCX/TXT/Markdown")
        self.registry.register("read_document", self.document_tools.read_document, description="Read active document excerpt")
        self.registry.register(
            "extract_document_text",
            self.document_tools.extract_document_text,
            description="Extract active document text",
        )
        self.registry.register("search_document", self.document_tools.search_document, description="Search active document")
        self.registry.register(
            "summarize_document",
            self.document_tools.summarize_document,
            description="Prepare active document evidence for summarization",
        )
        self.registry.register("web_search", self.web_tools.web_search, description="Search the public web")
        self.registry.register("web_read", self.web_tools.web_read, description="Read one public web page")

    def plan_message(self, message: object) -> AgentToolPlan:
        return self.workflow.classify_message(message)

    def execute_message(self, message: object, *, selected_file: str = "") -> AgentToolOutcome:
        state = self.workflow.invoke(message, selected_file=selected_file)
        handled = bool(state.get("handled", False))
        ui_command = str(state.get("ui_command", ""))
        if ui_command:
            return AgentToolOutcome(handled=True, ui_command=ui_command)
        if not handled:
            return AgentToolOutcome(handled=False)
        result = state.get("tool_result")
        if not isinstance(result, ToolResult):
            return AgentToolOutcome(
                handled=True,
                assistant_message="工具没有返回可用结果。",
            )
        if not result.ok:
            return AgentToolOutcome(
                handled=True,
                tool_name=result.name,
                result=result,
                assistant_message=f"{result.name} 执行失败：{result.content}",
            )

        requires_llm = result.name != "open_file"
        if result.name == "open_file":
            return AgentToolOutcome(
                handled=True,
                tool_name=result.name,
                result=result,
                assistant_message=result.content,
            )

        instruction = str(result.metadata.get("instruction", "")).strip()
        observation = self._build_tool_context(result, instruction=instruction)
        return AgentToolOutcome(
            handled=True,
            tool_name=result.name,
            result=result,
            tool_context=observation,
            requires_llm=requires_llm,
        )

    @staticmethod
    def _build_tool_context(result: ToolResult, *, instruction: str = "") -> str:
        raw_content = str(result.content or "")
        clipped = raw_content[:MAX_TOOL_OBSERVATION_CHARS]
        truncated = len(clipped) < len(raw_content)
        parts = [
            f"tool_name: {result.name}",
            "tool_status: success",
        ]
        if instruction:
            parts.append(f"tool_instruction: {instruction}")
        if truncated:
            parts.append(
                f"tool_note: observation truncated to {MAX_TOOL_OBSERVATION_CHARS} characters before LLM input"
            )
        parts.append("tool_observation:\n" + clipped)
        return "\n".join(parts)


__all__ = [
    "AgentToolCoordinator",
    "AgentToolGraph",
    "AgentToolOutcome",
    "AgentToolPlan",
    "AgentToolState",
    "MAX_TOOL_OBSERVATION_CHARS",
    "PICK_DOCUMENT_COMMAND",
    "ToolIntent",
]
