from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ai.adaptive_research_overlay import (
    QT_WIDGET_SIZE_MAX,
    AdaptiveResearchAgentOverlayWindow,
)
from app.ai.chat.models import ChatContext, ChatRole, ReadingContext
from app.ai.reading_context_ui import ReadingContextChatPanel


def test_reading_context_does_not_leak_metadata_to_different_selection(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)
    panel.show()

    panel.set_reading_context(
        ChatContext(
            source_text="selection A",
            reading=ReadingContext(
                resource_url="https://example.com/a",
                resource_title="Paper A",
                section_heading="Methods",
                source_kind="browser_selection",
            ),
        )
    )
    assert panel.reading_context_title.text() == "Paper A"
    assert "Methods" in panel.reading_context_meta.text()

    panel.set_context("selection B", "")

    assert panel.reading_context_title.text() == "当前阅读选区"
    assert panel.reading_context_meta.isHidden()
    assert panel.reading_chat_context.reading.resource_url == ""


def test_chat_font_menu_and_input_height_are_independent_controls(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)
    panel.resize(620, 520)
    panel.show()

    panel.set_display_font_size(18)
    panel.append_message(
        ChatRole.ASSISTANT,
        "Read https://example.com/paper for details.",
    )
    qtbot.wait(40)

    body = panel._message_rows[-1].findChild(QLabel, "OverlayChatMessageBody")
    assert body is not None
    assert body.font().pointSize() == 18
    assert panel.font_button.text().startswith("A 18")
    assert body.textInteractionFlags() & Qt.TextInteractionFlag.LinksAccessibleByMouse
    assert body.property("rawMessage") == "Read https://example.com/paper for details."

    collapsed_height = panel.input_edit.maximumHeight()
    panel.input_edit.setPlainText("\n".join(f"line {index}" for index in range(16)))
    qtbot.wait(80)
    assert panel.input_edit.maximumHeight() >= collapsed_height
    assert panel.input_edit.maximumHeight() <= 180

    panel.input_edit.clear()
    qtbot.wait(60)
    assert panel.input_edit.maximumHeight() == 44


def test_production_overlay_has_no_legacy_fixed_width_or_height_cap(qtbot) -> None:
    window = AdaptiveResearchAgentOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)

    assert window.maximumWidth() == QT_WIDGET_SIZE_MAX
    assert window.maximumHeight() == QT_WIDGET_SIZE_MAX
    assert window._label.maximumWidth() == QT_WIDGET_SIZE_MAX
    assert window._source_label.maximumWidth() == QT_WIDGET_SIZE_MAX
