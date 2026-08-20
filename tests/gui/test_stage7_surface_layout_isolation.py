from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QSizePolicy

from app.ai.adaptive_research_overlay import AdaptiveResearchAgentOverlayWindow


def _window(qtbot) -> AdaptiveResearchAgentOverlayWindow:
    window = AdaptiveResearchAgentOverlayWindow(win32_adapter=MagicMock())
    qtbot.addWidget(window)
    return window


def test_chat_header_budgets_model_and_font_controls_separately(qtbot) -> None:
    window = _window(qtbot)
    window.resize(744, 560)
    window.open_chat(
        provider="DeepSeek",
        model="deepseek-v4-flash-0731-long-display-name",
    )
    qtbot.wait(50)

    panel = window.chat_panel
    assert panel.model_button.maximumWidth() <= 168
    assert panel.font_button.width() == 76
    assert panel.model_button.geometry().right() < panel.clear_button.geometry().left()
    assert panel.clear_button.geometry().right() < panel.font_button.geometry().left()
    assert panel.font_button.geometry().right() < panel.delete_chat_button.geometry().left()
    assert "…" in panel.model_button.text()


def test_chat_resize_does_not_scale_translation_typography(qtbot) -> None:
    window = _window(qtbot)
    original_font_size = int(window._font_size)
    window.open_chat(provider="DeepSeek", model="deepseek-v4-flash")

    window._resize_start_geometry = QRect(0, 0, 560, 360)
    window._resize_start_font_size = original_font_size
    window._scale_fonts_for_manual_size(QSize(1100, 820))

    assert window._font_size == original_font_size
    assert window._label.font().pointSize() == original_font_size

    window.close_chat()
    assert window._font_size == original_font_size
    assert window._label.font().pointSize() == original_font_size


def test_returning_to_translation_drops_chat_local_height_lock(qtbot) -> None:
    window = _window(qtbot)
    window.show_translation("source", "translated")
    qtbot.wait(30)
    translation_height = window.height()

    window.open_chat(provider="DeepSeek", model="deepseek-v4-flash")
    window._manual_height_locked = True
    window._manual_size_locked = True
    window.resize(window.width(), translation_height + 320)
    window.close_chat()
    qtbot.wait(40)

    assert not window._manual_height_locked
    assert window.height() < translation_height + 320


def test_outer_header_never_expands_with_window_height(qtbot) -> None:
    window = _window(qtbot)
    window.resize(780, 900)
    window.show()
    qtbot.wait(30)

    assert (
        window._header.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Fixed
    )
    assert window._header.height() < window.height() // 3
