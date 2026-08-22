"""GUI contracts for the second AITrans SVG/icon-button migration pass."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QToolButton

from app.ai.adaptive_research_overlay import AdaptiveResearchAgentOverlayWindow
from app.ui.design_tokens import CONTROL, ICON, THEMES
from app.ui.icon_controls import (
    ICON_BUTTON_COMPACT,
    ICON_BUTTON_COMPOSER,
    ICON_BUTTON_TOOLBAR,
    apply_icon_button_palette,
    attach_menu_chevron,
    configure_icon_button,
)


def test_icon_button_variants_have_stable_hit_targets(qtbot) -> None:
    cases = (
        (ICON_BUTTON_COMPACT, CONTROL.compact_height, ICON.sm),
        (ICON_BUTTON_TOOLBAR, CONTROL.icon_button, ICON.md),
        (ICON_BUTTON_COMPOSER, CONTROL.large_height, ICON.md),
    )

    for metrics, expected_button, expected_icon in cases:
        button = QToolButton()
        qtbot.addWidget(button)
        configure_icon_button(button, metrics)

        assert button.width() == expected_button
        assert button.height() == expected_button
        assert button.iconSize().width() == expected_icon
        assert button.iconSize().height() == expected_icon
        assert button.property("aiTransIconButtonVariant") == metrics.name


def test_icon_button_palette_includes_hover_pressed_and_disabled_states(qtbot) -> None:
    button = QToolButton()
    qtbot.addWidget(button)
    configure_icon_button(button)
    apply_icon_button_palette(button, THEMES["dark"].legacy_overlay_palette())

    stylesheet = button.styleSheet()
    assert ":hover:enabled" in stylesheet
    assert ":pressed:enabled" in stylesheet
    assert ":disabled" in stylesheet
    assert "menu-indicator" in stylesheet


def test_menu_chevron_removes_legacy_glyph_and_native_indicator(qtbot) -> None:
    button = QToolButton()
    qtbot.addWidget(button)
    button.setText("DeepSeek · model ▾")
    attach_menu_chevron(
        button,
        color="#CBD5E1",
        disabled_color="#94A3B8",
    )
    button.resize(180, CONTROL.normal_height)
    button.show()
    qtbot.wait(1)

    assert button.text() == "DeepSeek · model"
    assert button.property("aiTransMenuChevron") is True
    assert "menu-indicator" in button.styleSheet()
    chevron = button.findChild(QLabel, "AITransMenuChevron")
    assert chevron is not None
    assert chevron.pixmap() is not None
    assert not chevron.pixmap().isNull()


def test_production_overlay_normalizes_header_and_chat_icon_controls(qtbot) -> None:
    window = AdaptiveResearchAgentOverlayWindow()
    qtbot.addWidget(window)

    assert window._copy_button.size().width() == CONTROL.icon_button
    assert window._copy_button.size().height() == CONTROL.icon_button
    assert window._copy_button.iconSize().width() == ICON.md
    assert ":pressed:enabled" in window._copy_button.styleSheet()

    panel = window._chat_panel
    for button in (
        panel.history_button,
        panel.new_chat_button,
        panel.delete_chat_button,
        panel.back_button,
    ):
        assert button.property("aiTransIconButtonVariant") == "toolbar"
        assert button.width() == CONTROL.icon_button
        assert button.iconSize().width() == ICON.md

    assert panel.undo_selection_button.property("aiTransIconButtonVariant") == "composer"
    assert panel.undo_selection_button.width() == CONTROL.large_height
    assert panel.reading_context_expand.property("aiTransIconButtonVariant") == "compact"
    assert panel.reading_context_expand.width() == CONTROL.compact_height

    assert panel.model_button.property("aiTransMenuChevron") is True
    assert panel.font_button.property("aiTransMenuChevron") is True
    assert "▾" not in panel.model_button.text()
    assert "▾" not in panel.font_button.text()
