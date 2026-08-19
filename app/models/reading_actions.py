"""Semantic quick actions for context-aware academic reading.

The UI and controller share these neutral action specifications so labels,
keys and prompts cannot drift apart.  The prompts are deliberately concise:
ReadingContext is supplied separately as structured reference data in the chat
request and remains the source of grounding.
"""

from __future__ import annotations

from dataclasses import dataclass


READING_EXPLAIN = "reading_explain"
READING_CONTEXT_TRANSLATE = "reading_context_translate"
READING_SUMMARIZE = "reading_summarize"
READING_SECTION_ROLE = "reading_section_role"


@dataclass(frozen=True, slots=True)
class ReadingActionSpec:
    key: str
    label: str
    symbol: str
    user_prompt: str


READING_ACTION_SPECS: tuple[ReadingActionSpec, ...] = (
    ReadingActionSpec(
        key=READING_EXPLAIN,
        label="解释这段",
        symbol="释",
        user_prompt=(
            "请结合当前阅读上下文解释这段内容：先说明核心含义，再解释关键概念或术语，"
            "最后说明作者在这里想表达什么。不要脱离给定上下文臆测。"
        ),
    ),
    ReadingActionSpec(
        key=READING_CONTEXT_TRANSLATE,
        label="结合上下文翻译",
        symbol="译",
        user_prompt=(
            "请结合当前阅读上下文，将选中的内容翻译为当前目标语言。根据前后文消除歧义，"
            "准确保留学术术语、公式、符号、数字和专有名词。除非存在关键歧义，否则只给出译文。"
        ),
    ),
    ReadingActionSpec(
        key=READING_SUMMARIZE,
        label="总结这段",
        symbol="摘",
        user_prompt=(
            "请结合当前阅读上下文，凝练总结这段内容。优先提炼研究问题、方法、论点、证据或结论中"
            "实际出现的要点，不要补充原文没有的信息。"
        ),
    ),
    ReadingActionSpec(
        key=READING_SECTION_ROLE,
        label="分析段落作用",
        symbol="章",
        user_prompt=(
            "请结合当前章节标题和前后文，分析这段内容在当前章节或论证结构中的作用，说明它承接了什么、"
            "推进了什么，以及与上下文的逻辑关系。若上下文不足，请明确说明。"
        ),
    ),
)

READING_ACTION_BY_KEY: dict[str, ReadingActionSpec] = {
    spec.key: spec for spec in READING_ACTION_SPECS
}
READING_ACTION_KEYS = frozenset(READING_ACTION_BY_KEY)


def reading_action_spec(key: object) -> ReadingActionSpec | None:
    """Return the registered reading action for one semantic menu key."""

    return READING_ACTION_BY_KEY.get(str(key or "").strip())


__all__ = [
    "READING_ACTION_BY_KEY",
    "READING_ACTION_KEYS",
    "READING_ACTION_SPECS",
    "READING_CONTEXT_TRANSLATE",
    "READING_EXPLAIN",
    "READING_SECTION_ROLE",
    "READING_SUMMARIZE",
    "ReadingActionSpec",
    "reading_action_spec",
]
