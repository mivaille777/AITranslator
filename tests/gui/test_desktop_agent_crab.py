from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ai.chat.models import ChatMessage, ChatRole
from app.ai.desktop_agent_overlay import DesktopAgentOverlayWindow
from app.overlay.context_menu import OVERLAY_THEMES


def test_chat_messages_remain_mouse_selectable(qtbot) -> None:
    window = DesktopAgentOverlayWindow()
    qtbot.addWidget(window)
    window.open_chat(
        messages=(
            ChatMessage(ChatRole.USER, "my question"),
            ChatMessage(ChatRole.ASSISTANT, "assistant answer"),
        )
    )

    bodies = window.chat_panel.findChildren(QLabel, "OverlayChatMessageBody")
    assert len(bodies) >= 2
    for body in bodies[-2:]:
        flags = body.textInteractionFlags()
        assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
        assert flags & Qt.TextInteractionFlag.TextSelectableByKeyboard
        assert not body.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert not window.chat_panel.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_double_click_handle_collapses_to_crab_and_restores_chat(qtbot) -> None:
    window = DesktopAgentOverlayWindow()
    qtbot.addWidget(window)
    window.open_chat(messages=(ChatMessage(ChatRole.ASSISTANT, "keep me"),))
    assert window.chat_open

    qtbot.mouseDClick(window.drag_handle, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.collapsed_to_crab)
    assert window.chat_open
    assert window.agent_crab.isVisible()
    assert not window.isVisible()

    qtbot.mouseDClick(window.agent_crab, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.collapsed_to_crab)
    assert window.chat_open
    assert window.isVisible()
    assert not window.agent_crab.isVisible()
    assert window.chat_panel.message_count == 1


def test_agent_crab_follows_overlay_theme(qtbot) -> None:
    window = DesktopAgentOverlayWindow()
    qtbot.addWidget(window)

    dark = OVERLAY_THEMES["dark"]
    assert window.agent_crab.theme_colors == {
        "panel": dark["menu_background"].upper(),
        "hover": dark["hover"].upper(),
        "border": dark["border"].upper(),
        "line": dark["muted_text"].upper(),
        "accent": dark["accent"].upper(),
    }

    window.set_theme("contrast")
    contrast = OVERLAY_THEMES["contrast"]
    assert window.agent_crab.theme_colors == {
        "panel": contrast["menu_background"].upper(),
        "hover": contrast["hover"].upper(),
        "border": contrast["border"].upper(),
        "line": contrast["muted_text"].upper(),
        "accent": contrast["accent"].upper(),
    }
