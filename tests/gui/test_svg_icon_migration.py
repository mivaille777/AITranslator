"""GUI contracts for the first AITrans SVG icon migration pass."""

from __future__ import annotations

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
    ):
        assert button.text() == ""
        assert not button.icon().isNull()

    assert panel.stop_button.text() == "停止"
    assert not panel.stop_button.icon().isNull()


def test_chat_svg_icons_survive_theme_recolor(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)

    soft = THEMES["soft"].legacy_overlay_palette()
    panel.apply_palette(soft)

    assert not panel.history_button.icon().isNull()
    assert not panel.back_button.icon().isNull()
    assert not panel.undo_selection_button.icon().isNull()
