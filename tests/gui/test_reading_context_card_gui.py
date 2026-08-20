from __future__ import annotations

from app.ai.chat.models import ChatContext, ReadingContext
from app.ai.reading_context_ui import ReadingContextChatPanel


def _context() -> ChatContext:
    return ChatContext(
        source_text="The LLM performs local refinement around the GP anchor.",
        translated_text="LLM 围绕 GP 锚点执行局部细化。",
        reading=ReadingContext(
            resource_url="https://example.org/paper",
            resource_title="Safety-Constrained Bayesian Optimization",
            section_heading="3.2 LLM-guided Local Refinement",
            context_before="The GP identifies a statistically promising region.",
            context_after="The candidate is validated deterministically.",
            source_kind="browser_selection",
        ),
    )


def test_reading_context_card_exposes_document_section_and_selection(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)
    panel.show()

    panel.set_reading_context(_context())

    assert panel.reading_context_card.isVisible()
    assert "Browser" in panel.reading_context_source.text()
    assert "Safety-Constrained" in panel.reading_context_title.text()
    assert "3.2 LLM-guided" in panel.reading_context_meta.text()
    assert "The LLM performs local refinement" in panel.reading_context_selection.text()


def test_reading_context_details_are_progressively_disclosed(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.set_reading_context(_context())

    assert not panel.reading_context_details.isVisible()

    panel.reading_context_expand.setChecked(True)
    qtbot.wait(10)

    assert panel.reading_context_details.isVisible()
    assert "当前译文" in panel.reading_context_details.text()
    assert "前文" in panel.reading_context_details.text()
    assert "后文" in panel.reading_context_details.text()


def test_reading_context_card_hides_without_reading_evidence(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)
    panel.show()

    panel.set_reading_context(ChatContext())

    assert not panel.reading_context_card.isVisible()
