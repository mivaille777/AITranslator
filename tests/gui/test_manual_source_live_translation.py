"""GUI tests for manual source editing in the production Overlay."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.ai.editable_overlay import (
    EditableResizableConversationalAIOverlayWindow,
    MANUAL_TRANSLATION_DEBOUNCE_MILLISECONDS,
)


def test_show_original_exposes_editable_input_even_when_empty(qapp) -> None:
    window = EditableResizableConversationalAIOverlayWindow()
    window.show_translation("", "", "auto", "zh-CN")

    window.set_original_visible(True)

    assert window.source_editor.isVisible()
    assert window.source_editor.toPlainText() == ""
    assert window.source_editor.placeholderText()
    window.close()


def test_manual_source_text_emits_debounced_translation_action(qapp) -> None:
    window = EditableResizableConversationalAIOverlayWindow()
    window.set_original_visible(True)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))

    window.source_editor.setPlainText("Hello from manual input")
    QTest.qWait(MANUAL_TRANSLATION_DEBOUNCE_MILLISECONDS + 80)

    assert ("manual_source_text", "Hello from manual input") in events
    window.close()


def test_programmatic_translation_refresh_does_not_retrigger_manual_input(qapp) -> None:
    window = EditableResizableConversationalAIOverlayWindow()
    window.set_original_visible(True)
    events: list[tuple[str, object]] = []
    window.context_action.connect(lambda key, value: events.append((key, value)))

    window.show_translation("programmatic source", "程序化译文", "en", "zh-CN")
    QTest.qWait(MANUAL_TRANSLATION_DEBOUNCE_MILLISECONDS + 80)

    assert window.source_editor.toPlainText() == "programmatic source"
    assert not any(key == "manual_source_text" for key, _ in events)
    window.close()


def test_source_editor_keeps_native_text_copy_shortcut(qapp) -> None:
    window = EditableResizableConversationalAIOverlayWindow()
    window.set_original_visible(True)
    window.show()
    window.source_editor.setPlainText("copy me")
    window.source_editor.selectAll()
    window.source_editor.setFocus()

    QTest.keyClick(window.source_editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)

    assert qapp.clipboard().text() == "copy me"
    window.close()
