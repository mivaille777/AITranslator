"""GUI contracts for the first AITrans SVG icon migration pass."""

from __future__ import annotations

from app.ai.chat.models import ChatContext, ReadingContext
from app.ai.reading_context_ui import ReadingContextChatPanel
from app.ui.design_tokens import THEMES


def test_chat_primary_icon_buttons_do_not_depend_on_font_glyphs(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)

    for button in (
        panel.history_button,
        panel.new_chat_button,
        panel.delete_chat_button,
        panel.back_button,
        panel.undo_selection_button,
        panel.reading_context_expand,
        panel.jump_to_bottom_button,
    ):
        assert button.text() == ""
        assert not button.icon().isNull()

    assert panel.stop_button.text() == "停止"
    assert not panel.stop_button.icon().isNull()
    assert panel.reading_context_source.text() == "Reading"


def test_reading_context_source_and_chevron_stay_font_independent(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)
    panel.set_reading_context(
        ChatContext(
            source_text="selected paper text",
            reading=ReadingContext(
                source_kind="pdf",
                resource_title="paper.pdf",
                context_before="before",
            ),
        )
    )

    assert panel.reading_context_source.text() == "PDF"
    assert "📄" not in panel.reading_context_source.text()
    assert panel.reading_context_expand.text() == ""
    assert not panel.reading_context_expand.icon().isNull()

    panel.reading_context_expand.setChecked(True)
    assert panel.reading_context_expand.text() == ""
    assert not panel.reading_context_expand.icon().isNull()


def test_chat_svg_icons_survive_theme_recolor(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)

    soft = THEMES["soft"].legacy_overlay_palette()
    panel.apply_palette(soft)

    assert not panel.history_button.icon().isNull()
    assert not panel.back_button.icon().isNull()
    assert not panel.undo_selection_button.icon().isNull()
    assert not panel.reading_context_expand.icon().isNull()
    assert not panel.jump_to_bottom_button.icon().isNull()
