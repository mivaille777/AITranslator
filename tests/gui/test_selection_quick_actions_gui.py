from __future__ import annotations

from app.ai.research_agent_overlay import ResearchAgentOverlayWindow
from app.ai.research_quick_actions import RESEARCH_NOTE_SAVE
from app.models.reading_actions import (
    READING_CONTEXT_TRANSLATE,
    READING_EXPLAIN,
    READING_SUMMARIZE,
)


def test_selection_quick_actions_appear_for_translation_result(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)

    bar = window.selection_quick_actions
    assert bar is not None
    assert not bar.isVisible()

    window.show_translation("selected source", "选中译文", "en", "zh-CN")
    qtbot.wait(10)

    assert bar.isVisible()
    assert set(bar.buttons) == {
        READING_CONTEXT_TRANSLATE,
        READING_EXPLAIN,
        READING_SUMMARIZE,
        RESEARCH_NOTE_SAVE,
    }
    assert bar.buttons[READING_CONTEXT_TRANSLATE].text() == "译"
    assert bar.buttons[READING_EXPLAIN].text() == "解释"
    assert bar.buttons[READING_SUMMARIZE].text() == "总结"
    assert bar.buttons[RESEARCH_NOTE_SAVE].text() == "笔记"


def test_selection_quick_action_reuses_semantic_controller_signal(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)
    emitted: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: emitted.append((key, value)))
    window.show_translation("source", "译文", "en", "zh-CN")

    bar = window.selection_quick_actions
    assert bar is not None
    bar.buttons[READING_EXPLAIN].click()

    assert emitted[-1] == (READING_EXPLAIN, None)


def test_selection_quick_actions_hide_in_chat(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)
    window.show_translation("source", "译文", "en", "zh-CN")

    bar = window.selection_quick_actions
    assert bar is not None and bar.isVisible()

    window.open_chat(source_text="source", translated_text="译文")
    qtbot.wait(10)

    assert not bar.isVisible()
