from __future__ import annotations

from app.ai.research_agent_overlay import (
    RESEARCH_NOTE_SAVE,
    RESEARCH_NOTES_LIBRARY,
    RESEARCH_NOTES_RECENT,
    ResearchAgentOverlayWindow,
)


def test_research_agent_ai_menu_exposes_note_actions(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)

    actions = window.research_actions

    assert set(actions) == {
        RESEARCH_NOTE_SAVE,
        RESEARCH_NOTES_LIBRARY,
        RESEARCH_NOTES_RECENT,
    }
    assert actions[RESEARCH_NOTE_SAVE].text() == "加入研究笔记"
    assert actions[RESEARCH_NOTES_LIBRARY].text() == "研究笔记库"
    assert actions[RESEARCH_NOTES_RECENT].text() == "最近研究笔记"
    assert all(action.parent() is window.context_menu.ai_menu for action in actions.values())


def test_note_library_remains_available_without_current_selection(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)

    window._sync_context_menu_state()

    assert window.context_menu.ai_menu.isEnabled()
    assert not window.research_actions[RESEARCH_NOTE_SAVE].isEnabled()
    assert window.research_actions[RESEARCH_NOTES_LIBRARY].isEnabled()
    assert window.research_actions[RESEARCH_NOTES_RECENT].isEnabled()
    assert all(not action.isEnabled() for action in window.reading_actions.values())


def test_save_note_becomes_available_after_selection_translation(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)

    window.show_translation(
        "A selected research sentence.",
        "一段选中的科研文本。",
        "en",
        "zh-CN",
    )
    window._sync_context_menu_state()

    assert window.research_actions[RESEARCH_NOTE_SAVE].isEnabled()
    assert window.research_actions[RESEARCH_NOTES_LIBRARY].isEnabled()
    assert window.research_actions[RESEARCH_NOTES_RECENT].isEnabled()
    assert all(action.isEnabled() for action in window.reading_actions.values())


def test_research_note_action_uses_existing_semantic_context_signal(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)
    emitted: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: emitted.append((key, value)))

    window.show_translation("source", "译文", "en", "zh-CN")
    window.research_actions[RESEARCH_NOTE_SAVE].trigger()

    assert emitted[-1] == (RESEARCH_NOTE_SAVE, None)
