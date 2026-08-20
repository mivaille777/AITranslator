from __future__ import annotations

from app.research.library_ui import ResearchNotesLibraryWindow
from app.research.notes import ResearchNote


def _note(note_id: str = "note-1") -> ResearchNote:
    return ResearchNote(
        note_id=note_id,
        fingerprint=f"fp-{note_id}",
        created_at="2026-08-20T01:00:00+00:00",
        updated_at="2026-08-20T02:00:00+00:00",
        resource_url="https://example.org/paper",
        resource_title="Safety-Constrained Bayesian Optimization",
        section_heading="3. Methodology",
        source_kind="browser_selection",
        source_text="The LLM performs local refinement around the GP anchor.",
        translated_text="LLM 围绕 GP 锚点执行局部细化。",
        ai_content="GP 负责统计定位，LLM 负责局部机制细化。",
        ai_action="reading_explain",
        user_note="已有个人备注",
    )


def test_research_notes_library_renders_selected_note(qtbot) -> None:
    window = ResearchNotesLibraryWindow()
    qtbot.addWidget(window)
    window.show()

    window.set_notes((_note(),))
    qtbot.wait(10)

    assert window.active_note_id == "note-1"
    assert "Safety-Constrained" in window.detail_title.text()
    assert "3. Methodology" in window.detail_meta.text()
    assert "LLM performs local refinement" in window.source_edit.toPlainText()
    assert "局部细化" in window.translation_edit.toPlainText()
    assert "GP 负责统计定位" in window.ai_edit.toPlainText()
    assert window.user_note_edit.toPlainText() == "已有个人备注"


def test_research_notes_library_emits_user_note_update(qtbot) -> None:
    window = ResearchNotesLibraryWindow()
    qtbot.addWidget(window)
    window.set_notes((_note(),))
    emitted: list[tuple[str, str]] = []
    window.user_note_save_requested.connect(
        lambda note_id, text: emitted.append((note_id, text))
    )

    window.user_note_edit.setPlainText("新的研究想法")
    window.save_button.click()

    assert emitted == [("note-1", "新的研究想法")]


def test_research_notes_library_search_signal_is_deterministic(qtbot) -> None:
    window = ResearchNotesLibraryWindow()
    qtbot.addWidget(window)
    queries: list[str] = []
    window.search_requested.connect(queries.append)

    window.search_edit.setText("safety gate")

    assert queries[-1] == "safety gate"
