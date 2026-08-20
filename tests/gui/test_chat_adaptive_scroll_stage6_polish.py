from __future__ import annotations

from app.ai.chat.models import ChatRole
from app.ai.reading_context_ui import ReadingContextChatPanel


def _long_text(seed: str, repeat: int = 30) -> str:
    return " ".join([seed] * repeat)


def _multiline_text(seed: str, lines: int = 8) -> str:
    return "\n".join(f"{seed} · line {index}" for index in range(lines))


def test_chat_messages_height_grows_with_content_and_stays_bounded(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)
    panel.resize(620, 420)
    panel.show()
    qtbot.wait(20)

    panel.append_message(ChatRole.ASSISTANT, "short answer")
    qtbot.wait(20)
    panel.refresh_adaptive_height(500)
    short_height = panel.messages_scroll.minimumHeight()

    panel.append_message(ChatRole.ASSISTANT, _long_text("long academic explanation", 160))
    qtbot.wait(30)
    panel.refresh_adaptive_height(500)
    long_height = panel.messages_scroll.minimumHeight()

    assert long_height >= short_height
    assert long_height <= panel.messages_scroll.maximumHeight()
    assert panel.maximumHeight() <= 500


def test_user_scroll_up_shows_jump_button_and_streaming_preserves_position(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)
    panel.resize(620, 320)
    panel.show()

    # Newline-heavy rows make overflow deterministic even with Qt's offscreen
    # plugin, whose font/layout metrics differ from an interactive desktop.
    for index in range(18):
        panel.append_message(
            ChatRole.ASSISTANT,
            _multiline_text(f"message {index}", 8),
        )
    panel.refresh_adaptive_height(320)
    qtbot.waitUntil(
        lambda: panel.messages_scroll.verticalScrollBar().maximum() > 0,
        timeout=1500,
    )

    bar = panel.messages_scroll.verticalScrollBar()
    panel._scroll_to_bottom()
    qtbot.wait(10)
    assert panel.follow_tail
    assert panel.jump_to_bottom_button.isHidden()

    target = max(bar.minimum(), bar.maximum() - max(80, bar.pageStep()))
    if target >= bar.maximum():
        target = max(bar.minimum(), bar.maximum() // 2)
    bar.setValue(target)
    qtbot.wait(20)
    assert bar.value() < bar.maximum()
    assert not panel.follow_tail
    assert not panel.jump_to_bottom_button.isHidden()
    held_position = bar.value()

    panel.begin_streaming_reply(101)
    panel.update_streaming_reply(101, _multiline_text("new streamed tokens", 35))
    qtbot.wait(100)

    assert not panel.follow_tail
    assert bar.value() == held_position
    assert not panel.jump_to_bottom_button.isHidden()

    panel.jump_to_bottom_button.click()
    qtbot.wait(20)
    assert panel.follow_tail
    assert bar.value() == bar.maximum()
    assert panel.jump_to_bottom_button.isHidden()


def test_follow_tail_tracks_new_stream_output_when_user_is_at_bottom(qtbot) -> None:
    panel = ReadingContextChatPanel()
    qtbot.addWidget(panel)
    panel.resize(620, 340)
    panel.show()

    for index in range(10):
        panel.append_message(ChatRole.ASSISTANT, _multiline_text(f"base {index}", 5))
    panel.refresh_adaptive_height(340)
    qtbot.waitUntil(
        lambda: panel.messages_scroll.verticalScrollBar().maximum() > 0,
        timeout=1500,
    )
    panel._scroll_to_bottom()

    panel.begin_streaming_reply(7)
    panel.update_streaming_reply(7, _multiline_text("streaming", 28))
    qtbot.wait(100)

    bar = panel.messages_scroll.verticalScrollBar()
    assert panel.follow_tail
    assert bar.value() == bar.maximum()
    assert panel.jump_to_bottom_button.isHidden()
