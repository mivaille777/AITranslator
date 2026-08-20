from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel, QToolButton

from app.ai.resizable_overlay import (
    CHAT_MIN_RESIZE_WIDTH,
    ResizableConversationalAIOverlayWindow,
)
from app.overlay.resize_handles import RESIZE_CORNER_SIZE, RESIZE_EDGE_THICKNESS


def test_chat_has_safe_minimum_width_and_drag_handle_never_overlaps_actions(qtbot) -> None:
    window = ResizableConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.open_chat(provider="DeepSeek", model="deepseek-v4-flash")
    window.resize(180, 300)
    qtbot.wait(20)

    assert window.width() >= CHAT_MIN_RESIZE_WIDTH

    handle = window.drag_handle
    if handle.isVisible():
        handle_rect = handle.geometry()
        for button in window._header.findChildren(QToolButton):
            if button.parentWidget() is window._header and button.isVisible():
                assert not handle_rect.intersects(button.geometry())


def test_resize_hit_targets_are_large_and_cover_each_boundary(qtbot) -> None:
    assert RESIZE_EDGE_THICKNESS >= 12
    assert RESIZE_CORNER_SIZE >= 24

    window = ResizableConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.show_translation("source", "translation", "en", "zh-CN")
    qtbot.wait(20)

    handles = window._resize_handles
    assert handles["left"].width() == RESIZE_EDGE_THICKNESS
    assert handles["right"].width() == RESIZE_EDGE_THICKNESS
    assert handles["top"].height() == RESIZE_EDGE_THICKNESS
    assert handles["bottom"].height() == RESIZE_EDGE_THICKNESS

    for edge in ("top_left", "top_right", "bottom_left", "bottom_right"):
        assert handles[edge].width() == RESIZE_CORNER_SIZE
        assert handles[edge].height() == RESIZE_CORNER_SIZE
        assert handles[edge].toolTip() == "拖动调整悬浮窗大小"


def test_manual_boundary_resize_changes_window_and_scales_content_font(qtbot) -> None:
    window = ResizableConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.show_translation("source", "translation", "en", "zh-CN")
    qtbot.wait(20)
    start_size = window.size()
    start_font = window.font_size
    start_point = window.frameGeometry().bottomRight()

    window._begin_manual_resize("bottom_right", start_point)
    window._continue_manual_resize(start_point + QPoint(100, 80))
    window._finish_manual_resize()

    assert window.manual_size_locked
    assert window.width() >= start_size.width()
    assert window.height() >= start_size.height()
    assert window.font_size >= start_font


def test_streaming_reply_updates_one_markdown_row_then_becomes_normal_message(qtbot) -> None:
    window = ResizableConversationalAIOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    window.open_chat(provider="DeepSeek", model="deepseek-v4-flash")

    window.begin_chat_stream(7)
    window.update_chat_stream(7, "第一段 **加粗**")

    streaming = window.chat_panel.findChild(QLabel, "OverlayChatMessageBody")
    assert streaming is not None
    assert "第一段" in streaming.text()
    assert streaming.textFormat() == Qt.TextFormat.MarkdownText

    window.finish_chat_stream(7, "第一段 **加粗**，完成。")
    assert window.chat_panel._streaming_row is None
    assert window.chat_panel.message_count == 1
    row = window.chat_panel._message_rows[0]
    copy_button = row.findChild(QToolButton, "OverlayChatMessageCopyButton")
    assert copy_button is not None
