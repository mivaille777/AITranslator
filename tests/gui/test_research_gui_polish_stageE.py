from __future__ import annotations

from app.ai.research_agent_overlay import (
    RESEARCH_NOTES_LIBRARY,
    ResearchAgentOverlayWindow,
)
from app.models.reading_actions import (
    READING_CONTEXT_TRANSLATE,
    READING_EXPLAIN,
    READING_SUMMARIZE,
)
from app.ai.research_quick_actions import RESEARCH_NOTE_SAVE
from app.overlay.context_menu import OVERLAY_THEMES
from app.research.library_ui import ResearchNotesLibraryWindow


def test_quick_action_bar_uses_compact_labels_for_narrow_surface(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)
    window.show_translation("source", "译文", "en", "zh-CN")
    bar = window.selection_quick_actions
    assert bar is not None

    bar.set_compact(True)

    assert bar.buttons[READING_CONTEXT_TRANSLATE].text() == "译"
    assert bar.buttons[READING_EXPLAIN].text() == "解"
    assert bar.buttons[READING_SUMMARIZE].text() == "总"
    assert bar.buttons[RESEARCH_NOTE_SAVE].text() == "记"

    bar.set_compact(False)
    assert bar.buttons[READING_EXPLAIN].text() == "解释"
    assert bar.buttons[READING_SUMMARIZE].text() == "总结"
    assert bar.buttons[RESEARCH_NOTE_SAVE].text() == "笔记"


def test_note_toast_view_routes_to_research_library(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)
    emitted: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: emitted.append((key, value)))

    window.show_research_note_toast("已加入研究笔记", show_view=True, timeout_ms=5000)
    toast = window.research_note_toast
    assert toast is not None
    assert not toast.isHidden()
    assert toast.message_label.text() == "已加入研究笔记"
    assert not toast.view_button.isHidden()

    toast.view_button.click()

    assert emitted[-1] == (RESEARCH_NOTES_LIBRARY, None)
    assert toast.isHidden()


def test_research_notes_library_accepts_overlay_palette(qtbot) -> None:
    palette = OVERLAY_THEMES["soft"]
    window = ResearchNotesLibraryWindow(palette=palette)
    qtbot.addWidget(window)

    assert window.palette["menu_background"] == palette["menu_background"]
    assert palette["accent"] in window.styleSheet()

    window.apply_palette(OVERLAY_THEMES["contrast"])
    assert window.palette["accent"] == OVERLAY_THEMES["contrast"]["accent"]
    assert OVERLAY_THEMES["contrast"]["accent"] in window.styleSheet()
