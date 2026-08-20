from __future__ import annotations

from app.ai.reading_context_ui import ReadingContextChatPanel
from app.ai.chat.models import ChatRole


def _long_text(seed: str, repeat: int = 30) -> str:
    return " ".join([seed] * repeat)


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
    panel.resize(620, 430)
    panel.show()

    for index in range(8):
        panel.append_message(
            ChatRole.ASSISTANT,
            _long_text(f"message {index}", 45),
        )
    qtbot.wait(80)
    panel.refresh_adaptive_height(430)
    qtbot.wait(30)

    bar = panel.messages_scroll.verticalScrollBar()
    assert bar.maximum() > bar.minimum()

    panel._scroll_to_bottom()
    qtbot.wait(10)
    assert panel.follow_tail
    assert panel.jump_to_bottom_button.isHidden()

    target = max(bar.minimum(), bar.maximum() - max(80, bar.pageStep()))
    bar.setValue(target)
    qtbot.wait(20)
    assert not panel.follow_tail
    assert not panel.jump_to_bottom_button.isHidden()
    held_position = bar.value()

    panel.begin_streaming_reply(101)
    panel.update_streaming_reply(101, _long_text("new streamed tokens", 180))
    qtbot.wait(80)

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
    panel.resize(620, 430)
    panel.show()

    for index in range(5):
        panel.append_message(ChatRole.ASSISTANT, _long_text(f"base {index}", 30))
    qtbot.wait(60)
    panel._scroll_to_bottom()

    panel.begin_streaming_reply(7)
    panel.update_streaming_reply(7, _long_text("streaming", 120))
    qtbot.wait(80)

    bar = panel.messages_scroll.verticalScrollBar()
    assert panel.follow_tail
    assert bar.value() == bar.maximum()
    assert panel.jump_to_bottom_button.isHidden()
