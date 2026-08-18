"""LangGraph human-in-the-loop orchestration for Overlay workspace switching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


WorkspaceName = Literal["chat", "translation"]
WorkspaceIntent = Literal[
    "request_translation",
    "finish_translation",
    "continue_chat",
]

OPEN_TRANSLATION_COMMAND = "open_translation"
RETURN_TO_CHAT_COMMAND = "return_to_chat"

TRANSLATION_CONFIRMATION_TEXT = (
    "检测到你想进行翻译任务。要切换到翻译界面吗？回复“确定”或“取消”。"
)
TRANSLATION_ENTERED_TEXT = (
    "好的，已切换到翻译界面。你可以在原文框中输入内容，也可以继续在下方和我对话。"
)
TRANSLATION_CANCELLED_TEXT = "好的，暂不切换，继续在当前 AI 对话中。"
TRANSLATION_FINISHED_TEXT = "好的，翻译任务已结束，已返回完整 AI 对话。"
CONFIRMATION_RETRY_TEXT = "请回复“确定”或“取消”，我再决定是否切换到翻译界面。"


class WorkspaceAgentState(TypedDict, total=False):
    """Short-term state for one UI-workspace orchestration thread."""

    user_message: str
    workspace: WorkspaceName
    intent: WorkspaceIntent
    handled: bool
    assistant_message: str
    ui_command: str


@dataclass(frozen=True, slots=True)
class WorkspaceAgentOutcome:
    """Controller-facing result from one workspace-agent turn."""

    handled: bool
    pending_confirmation: bool = False
    assistant_message: str = ""
    ui_command: str = ""


_TRANSLATION_REQUEST_PHRASES = (
    "帮我翻译",
    "帮我做翻译",
    "我要你翻译",
    "我要翻译",
    "我想翻译",
    "想让你翻译",
    "需要翻译",
    "开始翻译",
    "进入翻译",
    "切到翻译",
    "切换到翻译",
    "打开翻译",
    "翻译东西",
    "translate something",
    "help me translate",
    "switch to translation",
)

_TRANSLATION_FINISH_PHRASES = (
    "翻译完了",
    "翻译完成",
    "翻译结束",
    "结束翻译",
    "退出翻译",
    "不用翻译了",
    "回到聊天",
    "回到对话",
    "done translating",
    "translation done",
    "finish translation",
)

_APPROVE_PHRASES = (
    "确定",
    "确认",
    "好",
    "好的",
    "可以",
    "行",
    "是",
    "切换",
    "进入",
    "yes",
    "y",
    "ok",
    "okay",
)

_REJECT_PHRASES = (
    "取消",
    "不用",
    "不要",
    "算了",
    "否",
    "不切换",
    "no",
    "n",
)


def _normalize_message(message: object) -> str:
    return " ".join(str(message or "").strip().lower().split())


def _contains_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _confirmation_value(message: object) -> bool | None:
    text = _normalize_message(message)
    if not text:
        return None
    if _contains_phrase(text, _REJECT_PHRASES):
        return False
    if _contains_phrase(text, _APPROVE_PHRASES):
        return True
    return None


class WorkspaceAgentGraph:
    """StateGraph controlling translation-workspace entry and exit.

    The graph deliberately does not mutate Qt widgets itself. It returns a
    deterministic ``ui_command`` which the GUI controller executes after the
    graph has completed. Entering translation is protected by a LangGraph
    interrupt so the user explicitly approves the workspace tool call first.
    """

    def __init__(self) -> None:
        builder = StateGraph(WorkspaceAgentState)
        builder.add_node("classify", self._classify)
        builder.add_node("confirm_translation", self._confirm_translation)
        builder.add_node("finish_translation", self._finish_translation)
        builder.add_node("continue_chat", self._continue_chat)
        builder.add_edge(START, "classify")
        builder.add_conditional_edges(
            "classify",
            self._route,
            {
                "request_translation": "confirm_translation",
                "finish_translation": "finish_translation",
                "continue_chat": "continue_chat",
            },
        )
        builder.add_edge("confirm_translation", END)
        builder.add_edge("finish_translation", END)
        builder.add_edge("continue_chat", END)
        self.graph = builder.compile(checkpointer=InMemorySaver())

    @staticmethod
    def _classify(state: WorkspaceAgentState) -> WorkspaceAgentState:
        text = _normalize_message(state.get("user_message", ""))
        workspace = state.get("workspace", "chat")
        if workspace == "translation" and _contains_phrase(
            text,
            _TRANSLATION_FINISH_PHRASES,
        ):
            intent: WorkspaceIntent = "finish_translation"
        elif workspace == "chat" and _contains_phrase(
            text,
            _TRANSLATION_REQUEST_PHRASES,
        ):
            intent = "request_translation"
        else:
            intent = "continue_chat"
        return {
            "intent": intent,
            "handled": False,
            "assistant_message": "",
            "ui_command": "",
        }

    @staticmethod
    def _route(state: WorkspaceAgentState) -> WorkspaceIntent:
        return state.get("intent", "continue_chat")

    @staticmethod
    def _confirm_translation(state: WorkspaceAgentState) -> WorkspaceAgentState:
        approved = interrupt(
            {
                "kind": "workspace_confirmation",
                "target": "translation",
                "message": TRANSLATION_CONFIRMATION_TEXT,
            }
        )
        if bool(approved):
            return {
                "handled": True,
                "assistant_message": TRANSLATION_ENTERED_TEXT,
                "ui_command": OPEN_TRANSLATION_COMMAND,
            }
        return {
            "handled": True,
            "assistant_message": TRANSLATION_CANCELLED_TEXT,
            "ui_command": "",
        }

    @staticmethod
    def _finish_translation(_state: WorkspaceAgentState) -> WorkspaceAgentState:
        return {
            "handled": True,
            "assistant_message": TRANSLATION_FINISHED_TEXT,
            "ui_command": RETURN_TO_CHAT_COMMAND,
        }

    @staticmethod
    def _continue_chat(_state: WorkspaceAgentState) -> WorkspaceAgentState:
        return {
            "handled": False,
            "assistant_message": "",
            "ui_command": "",
        }


class WorkspaceAgentCoordinator:
    """Thin runtime wrapper around the interruptible workspace StateGraph."""

    def __init__(self, graph: WorkspaceAgentGraph | None = None) -> None:
        self.workflow = graph or WorkspaceAgentGraph()
        self._pending_threads: set[str] = set()

    @staticmethod
    def _config(thread_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": str(thread_id)}}

    def is_waiting_for_confirmation(self, thread_id: str) -> bool:
        return str(thread_id) in self._pending_threads

    def handle_message(
        self,
        thread_id: str,
        message: object,
        *,
        workspace: WorkspaceName,
    ) -> WorkspaceAgentOutcome:
        """Process one user turn or resume a pending HITL confirmation."""

        resolved_thread = str(thread_id).strip()
        if not resolved_thread:
            raise ValueError("workspace agent thread_id is required")

        if resolved_thread in self._pending_threads:
            decision = _confirmation_value(message)
            if decision is None:
                return WorkspaceAgentOutcome(
                    handled=True,
                    pending_confirmation=True,
                    assistant_message=CONFIRMATION_RETRY_TEXT,
                )
            result = self.workflow.graph.invoke(
                Command(resume=decision),
                config=self._config(resolved_thread),
            )
            self._pending_threads.discard(resolved_thread)
            return WorkspaceAgentOutcome(
                handled=bool(result.get("handled", True)),
                pending_confirmation=False,
                assistant_message=str(result.get("assistant_message", "")),
                ui_command=str(result.get("ui_command", "")),
            )

        result = self.workflow.graph.invoke(
            {
                "user_message": str(message or ""),
                "workspace": workspace,
                "handled": False,
                "assistant_message": "",
                "ui_command": "",
            },
            config=self._config(resolved_thread),
        )
        interrupts = result.get("__interrupt__", ())
        if interrupts:
            self._pending_threads.add(resolved_thread)
            first = interrupts[0]
            payload = getattr(first, "value", {})
            if isinstance(payload, dict):
                prompt = str(payload.get("message", TRANSLATION_CONFIRMATION_TEXT))
            else:
                prompt = TRANSLATION_CONFIRMATION_TEXT
            return WorkspaceAgentOutcome(
                handled=True,
                pending_confirmation=True,
                assistant_message=prompt,
            )

        return WorkspaceAgentOutcome(
            handled=bool(result.get("handled", False)),
            pending_confirmation=False,
            assistant_message=str(result.get("assistant_message", "")),
            ui_command=str(result.get("ui_command", "")),
        )


__all__ = [
    "CONFIRMATION_RETRY_TEXT",
    "OPEN_TRANSLATION_COMMAND",
    "RETURN_TO_CHAT_COMMAND",
    "TRANSLATION_CANCELLED_TEXT",
    "TRANSLATION_CONFIRMATION_TEXT",
    "TRANSLATION_ENTERED_TEXT",
    "TRANSLATION_FINISHED_TEXT",
    "WorkspaceAgentCoordinator",
    "WorkspaceAgentGraph",
    "WorkspaceAgentOutcome",
    "WorkspaceAgentState",
]
