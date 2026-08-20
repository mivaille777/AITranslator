"""Production-header contracts for the final SVG icon-system pass."""

from __future__ import annotations

from app.ai.adaptive_research_overlay import AdaptiveResearchAgentOverlayWindow
from app.ui.design_tokens import CONTROL, ICON


def test_secondary_chat_actions_collapse_into_more_menu(qtbot) -> None:
    window = AdaptiveResearchAgentOverlayWindow()
    qtbot.addWidget(window)
    panel = window._chat_panel

    overflow = window._chat_overflow_button
    menu = window._chat_overflow_menu
    assert overflow is not None
    assert menu is not None
    assert overflow.objectName() == "AITransChatOverflowButton"
    assert overflow.width() == CONTROL.icon_button
    assert overflow.height() == CONTROL.icon_button
    assert overflow.iconSize().width() == ICON.md
    assert not overflow.icon().isNull()
    assert not overflow.isHidden()

    # Secondary controls remain alive for compatibility, but no longer occupy
    # permanent header space on the production surface.
    assert panel.font_button.isHidden()
    assert panel.clear_button.isHidden()
    assert panel.delete_chat_button.isHidden()
    assert not panel.model_button.isHidden()
    assert not panel.history_button.isHidden()
    assert not panel.new_chat_button.isHidden()
    assert not panel.back_button.isHidden()

    assert panel.font_menu.menuAction() in menu.actions()
    assert window._chat_overflow_clear_action in menu.actions()
    assert window._chat_overflow_delete_action in menu.actions()


def test_chat_overflow_reuses_font_clear_and_delete_behaviors(qtbot) -> None:
    window = AdaptiveResearchAgentOverlayWindow()
    qtbot.addWidget(window)
    panel = window._chat_panel

    clear_action = window._chat_overflow_clear_action
    delete_action = window._chat_overflow_delete_action
    assert clear_action is not None
    assert delete_action is not None

    window._sync_chat_overflow_menu()
    assert panel.font_menu.title() == f"字体大小 · {panel.display_font_size} pt"
    assert not panel.font_menu.icon().isNull()
    assert not delete_action.isEnabled()

    with qtbot.waitSignal(panel.clear_requested, timeout=200):
        clear_action.trigger()

    panel.set_conversations(
        [{"conversation_id": "conversation-1", "title": "Paper discussion"}],
        active_id="conversation-1",
    )
    window._sync_chat_overflow_menu()
    assert delete_action.isEnabled()

    with qtbot.waitSignal(panel.conversation_delete_requested, timeout=200) as signal:
        delete_action.trigger()
    assert signal.args == ["conversation-1"]


def test_chat_overflow_palette_keeps_shared_pressed_state(qtbot) -> None:
    window = AdaptiveResearchAgentOverlayWindow()
    qtbot.addWidget(window)

    overflow = window._chat_overflow_button
    assert overflow is not None
    style = overflow.styleSheet()
    assert ":pressed:enabled" in style
    assert "QToolButton::menu-indicator" in style
