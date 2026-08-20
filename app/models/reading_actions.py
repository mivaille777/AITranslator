"""Semantic quick actions for context-aware academic reading.

The UI and controller share these neutral action specifications so labels,
keys and prompts cannot drift apart. ReadingContext is supplied separately as
structured reference data in the chat request and remains the grounding source.
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
        user_prompt="请结合当前阅读上下文解释这段内容，并说明关键概念和作者想表达的核心含义。",
    ),
    ReadingActionSpec(
        key=READING_CONTEXT_TRANSLATE,
        label="结合上下文翻译",
        symbol="译",
        user_prompt=(
            "请结合当前阅读上下文，将这段内容翻译为{target_language}，"
            "保持学术术语、公式、符号、数字和专有名词准确；除非存在关键歧义，否则只给出译文。"
        ),
    ),
    ReadingActionSpec(
        key=READING_SUMMARIZE,
        label="总结这段",
        symbol="摘",
        user_prompt="请结合当前阅读上下文总结这段内容，只提炼原文实际出现的核心要点。",
    ),
    ReadingActionSpec(
        key=READING_SECTION_ROLE,
        label="分析段落作用",
        symbol="章",
        user_prompt=(
            "请结合当前章节标题和前后文，分析这段内容在当前章节或论证结构中的作用，"
            "说明它承接了什么、推进了什么；如果上下文不足请明确说明。"
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


def reading_action_prompt(
    key: object,
    *,
    target_language: object = "zh-CN",
) -> str:
    """Build the concise user-visible prompt for one registered action."""

    spec = reading_action_spec(key)
    if spec is None:
        return ""
    target = str(target_language or "zh-CN").strip() or "zh-CN"
    try:
        return spec.user_prompt.format(target_language=target)
    except (KeyError, ValueError):
        return spec.user_prompt


__all__ = [
    "READING_ACTION_BY_KEY",
    "READING_ACTION_KEYS",
    "READING_ACTION_SPECS",
    "READING_CONTEXT_TRANSLATE",
    "READING_EXPLAIN",
    "READING_SECTION_ROLE",
    "READING_SUMMARIZE",
    "ReadingActionSpec",
    "reading_action_prompt",
    "reading_action_spec",
]
