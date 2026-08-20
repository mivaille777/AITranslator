from __future__ import annotations

from app.ai.research_agent_overlay import ResearchAgentOverlayWindow
from app.overlay.context_menu import OVERLAY_THEMES


def test_production_header_chrome_stays_opaque_when_body_is_translucent(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)
    window.apply_style(background_opacity=0.2, text_opacity=1.0)
    window.show_translation("source", "translation", "en", "zh-CN")
    qtbot.wait(20)

    palette = OVERLAY_THEMES[window.theme_name]
    assert palette["menu_background"] in window._header.styleSheet()

    for button in (
        window._ai_button,
        window._chat_button,
        window._copy_button,
        window._menu_button,
    ):
        style = button.styleSheet()
        assert palette["menu_background"] in style
        assert palette["text"] in style
        assert "rgba(" not in style


def test_chat_surface_uses_opaque_theme_surface(qtbot) -> None:
    window = ResearchAgentOverlayWindow()
    qtbot.addWidget(window)
    window.apply_style(background_opacity=0.2)
    window.open_chat(source_text="source", translated_text="translation")
    qtbot.wait(20)

    palette = OVERLAY_THEMES[window.theme_name]
    panel = window.chat_panel
    assert palette["menu_background"] in panel.styleSheet()
    assert palette["text"] in panel.styleSheet()
