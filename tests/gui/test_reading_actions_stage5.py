from __future__ import annotations

from app.ai.desktop_agent_overlay import DesktopAgentOverlayWindow
from app.models.reading_actions import (
    READING_ACTION_SPECS,
    READING_EXPLAIN,
)


def test_desktop_agent_ai_menu_exposes_context_aware_reading_actions(qtbot) -> None:
    window = DesktopAgentOverlayWindow()
    qtbot.addWidget(window)

    actions = window.reading_actions

    assert set(actions) == {spec.key for spec in READING_ACTION_SPECS}
    assert [actions[spec.key].text() for spec in READING_ACTION_SPECS] == [
        spec.label for spec in READING_ACTION_SPECS
    ]
    assert all(action.parent() is window.context_menu.ai_menu for action in actions.values())


def test_reading_action_emits_the_existing_semantic_context_signal(qtbot) -> None:
    window = DesktopAgentOverlayWindow()
    qtbot.addWidget(window)
    emitted: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: emitted.append((key, value)))

    window.reading_actions[READING_EXPLAIN].trigger()

    assert emitted[-1] == (READING_EXPLAIN, None)


def test_ai_reading_menu_is_only_enabled_when_source_text_exists(qtbot) -> None:
    window = DesktopAgentOverlayWindow()
    qtbot.addWidget(window)

    window._sync_context_menu_state()
    assert not window.context_menu.ai_menu.isEnabled()

    window.show_translation(
        "A selected research sentence.",
        "一段选中的科研文本。",
        "en",
        "zh-CN",
    )
    window._sync_context_menu_state()

    assert window.context_menu.ai_menu.isEnabled()
    assert all(action.isEnabled() for action in window.reading_actions.values())
