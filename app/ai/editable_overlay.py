"""Editable translation source field for the production resizable Overlay."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent, QTextOption
from PySide6.QtWidgets import QLabel, QSizePolicy, QTextEdit

from app.ai.resizable_overlay import (
    ResizableConversationalAIOverlayManager,
    ResizableConversationalAIOverlayWindow,
)
from app.overlay.context_menu import OVERLAY_THEMES
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


MANUAL_TRANSLATION_DEBOUNCE_MILLISECONDS = 420
TRANSLATION_STATUS_FEEDBACK_MILLISECONDS = 1100
SOURCE_EDITOR_MIN_HEIGHT = 48
SOURCE_EDITOR_MAX_HEIGHT = 150


class EditableSourceTextEdit(QTextEdit):
    """Compact multiline source editor that grows before it starts scrolling."""

    translate_now_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("OverlaySourceLabel")
        self.setAcceptRichText(False)
        self.setUndoRedoEnabled(True)
        self.setPlaceholderText("输入原文，停顿后自动翻译…  Ctrl+Enter 立即翻译")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(SOURCE_EDITOR_MIN_HEIGHT)
        self.setMaximumHeight(SOURCE_EDITOR_MAX_HEIGHT)
        self.textChanged.connect(self.adjust_editor_height)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            event.accept()
            self.translate_now_requested.emit()
            return
        super().keyPressEvent(event)

    def setText(self, text: str) -> None:  # noqa: N802 - QLabel compatibility
        """Keep the base Overlay's QLabel-style setter contract."""

        normalized = "" if text is None else str(text)
        if self.toPlainText() == normalized:
            return
        cursor = self.textCursor()
        position = cursor.position()
        self.setPlainText(normalized)
        cursor = self.textCursor()
        cursor.setPosition(min(position, len(normalized)))
        self.setTextCursor(cursor)

    def text(self) -> str:
        """Keep the base Overlay's QLabel-style getter contract."""

        return self.toPlainText()

    def adjust_editor_height(self) -> None:
        document_height = self.document().documentLayout().documentSize().height()
        frame = self.frameWidth() * 2
        margins = self.contentsMargins()
        desired = round(document_height + frame + margins.top() + margins.bottom() + 10)
        height = max(
            SOURCE_EDITOR_MIN_HEIGHT,
            min(SOURCE_EDITOR_MAX_HEIGHT, desired),
        )
        if self.height() != height:
            self.setFixedHeight(height)


class EditableResizableConversationalAIOverlayWindow(
    ResizableConversationalAIOverlayWindow
):
    """Resizable Overlay whose visible source row is an editable live input."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._source_editor_programmatic = False
        super().__init__(*args, **kwargs)

        old_source = self._source_label
        index = self._content_layout.indexOf(old_source)
        self._content_layout.removeWidget(old_source)
        old_source.hide()
        old_source.setParent(None)
        old_source.deleteLater()

        self._source_editor = EditableSourceTextEdit(self._content)
        self._source_label = self._source_editor
        self._source_editor.setMaximumWidth(self._max_width)
        self._source_editor.setFont(
            QFont(
                self._font_family,
                max(8, min(18, round(self._font_size * 0.55))),
            )
        )
        source_index = max(0, index)
        self._content_layout.insertWidget(source_index, self._source_editor)

        self._translation_status_label = QLabel("", self._content)
        self._translation_status_label.setObjectName("OverlayTranslationStatus")
        self._translation_status_label.setTextFormat(Qt.TextFormat.PlainText)
        self._translation_status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._translation_status_label.hide()
        self._content_layout.insertWidget(source_index + 1, self._translation_status_label)
        self._translation_status_timer = QTimer(self)
        self._translation_status_timer.setSingleShot(True)
        self._translation_status_timer.timeout.connect(
            lambda: self.set_translation_status("")
        )

        # The old presentation-only content container ignored all mouse input.
        # The source editor needs normal focus/selection/Ctrl+C behavior while
        # the translated QLabel remains transparent to mouse events.
        self._content.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._source_editor.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            False,
        )

        self._manual_translation_timer = QTimer(self)
        self._manual_translation_timer.setSingleShot(True)
        self._manual_translation_timer.setInterval(
            MANUAL_TRANSLATION_DEBOUNCE_MILLISECONDS
        )
        self._manual_translation_timer.timeout.connect(
            self._emit_manual_source_translation
        )
        self._source_editor.textChanged.connect(self._on_source_editor_changed)
        self._source_editor.translate_now_requested.connect(
            self._translate_source_immediately
        )

        self._source_editor_programmatic = True
        try:
            self._source_editor.setText(self._source_text)
        finally:
            self._source_editor_programmatic = False
        self._source_editor.setVisible(self._original_visible)
        self._source_editor.adjust_editor_height()
        self._apply_theme(self._theme_name)
        self._resize_to_content()

    @property
    def source_editor(self) -> EditableSourceTextEdit:
        return self._source_editor

    @property
    def translation_status_label(self) -> QLabel:
        return self._translation_status_label

    def _on_source_editor_changed(self) -> None:
        if self._source_editor_programmatic:
            return
        self._source_text = self._source_editor.toPlainText()
        self._source_editor.adjust_editor_height()
        self.set_translation_status("输入中…")
        self._manual_translation_timer.start()
        if self._manual_size_locked:
            self._update_scroll_area_limits()
        else:
            self._resize_to_content(animate=False)

    def _translate_source_immediately(self) -> None:
        if self._source_editor_programmatic:
            return
        self._manual_translation_timer.stop()
        self._emit_manual_source_translation()

    def _emit_manual_source_translation(self) -> None:
        if self._chat_open or not self._original_visible:
            return
        text = self._source_editor.toPlainText()
        self.set_translation_status("翻译中…" if text.strip() else "")
        self.context_action.emit("manual_source_text", text)

    def set_translation_status(
        self,
        status: object,
        *,
        auto_hide_ms: int = 0,
    ) -> str:
        text = str(status or "").strip()
        self._translation_status_timer.stop()
        self._translation_status_label.setText(text)
        self._translation_status_label.setVisible(
            bool(text) and self._original_visible and not self._chat_open
        )
        if text and auto_hide_ms > 0:
            self._translation_status_timer.start(int(auto_hide_ms))
        if not self._manual_size_locked:
            self._resize_to_content(animate=False)
        return text

    def set_original_visible(self, visible: bool) -> bool:
        """Show an empty editor too, so users can type without prior selection."""

        result = super().set_original_visible(visible)
        editor = getattr(self, "_source_editor", None)
        if editor is not None:
            editor.setVisible(bool(visible))
            editor.adjust_editor_height()
            self._translation_status_label.setVisible(
                bool(visible) and bool(self._translation_status_label.text())
            )
            self._resize_to_content(animate=False)
        return result

    def open_chat(self, **kwargs: Any) -> None:
        self._manual_translation_timer.stop()
        self._translation_status_timer.stop()
        self._translation_status_label.hide()
        super().open_chat(**kwargs)

    def close_chat(self) -> None:
        super().close_chat()
        if self._original_visible and self._translation_status_label.text():
            self._translation_status_label.show()

    def _set_content(
        self,
        source_text: object | None,
        translated_text: object | None,
        source_language: object,
        target_language: object,
        *,
        animate: bool = False,
    ) -> None:
        editor = getattr(self, "_source_editor", None)
        if editor is None:
            super()._set_content(
                source_text,
                translated_text,
                source_language,
                target_language,
                animate=animate,
            )
            return

        self._source_editor_programmatic = True
        try:
            super()._set_content(
                source_text,
                translated_text,
                source_language,
                target_language,
                animate=animate,
            )
        finally:
            self._source_editor_programmatic = False
        editor.setVisible(self._original_visible)
        editor.adjust_editor_height()

    def _style_source_editor(self) -> None:
        editor = getattr(self, "_source_editor", None)
        if editor is None:
            return
        palette = OVERLAY_THEMES[self._theme_name]
        source_text = self._rgba_with_opacity(
            palette["text"],
            self._text_opacity,
        )
        source_background = self._rgba_with_opacity(
            palette["label_background"],
            self._background_opacity * 0.88,
            multiply_existing_alpha=True,
        )
        source_border = self._rgba_with_opacity(
            palette["border"],
            self._background_opacity * 0.86,
        )
        focus_border = palette["accent"]
        scroll_handle = self._rgba_with_opacity(
            palette["muted_text"],
            self._background_opacity * 0.6,
        )
        editor.setStyleSheet(
            f"""
            QTextEdit#OverlaySourceLabel {{
                color: {source_text};
                background-color: {source_background};
                border: 1px solid {source_border};
                border-radius: 7px;
                padding: 6px 8px;
                selection-background-color: {palette['accent']};
            }}
            QTextEdit#OverlaySourceLabel:focus {{
                border: 1px solid {focus_border};
            }}
            QTextEdit#OverlaySourceLabel QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 3px 1px;
            }}
            QTextEdit#OverlaySourceLabel QScrollBar::handle:vertical {{
                background: {scroll_handle};
                min-height: 20px;
                border-radius: 3px;
            }}
            QTextEdit#OverlaySourceLabel QScrollBar::add-line:vertical,
            QTextEdit#OverlaySourceLabel QScrollBar::sub-line:vertical,
            QTextEdit#OverlaySourceLabel QScrollBar::add-page:vertical,
            QTextEdit#OverlaySourceLabel QScrollBar::sub-page:vertical {{
                background: transparent;
                height: 0px;
            }}
            """
        )
        self._translation_status_label.setStyleSheet(
            f"""
            QLabel#OverlayTranslationStatus {{
                color: {palette['muted_text']};
                background: transparent;
                padding: 0px 4px 2px 4px;
                font-size: 11px;
            }}
            """
        )

    def _apply_theme(self, theme: str) -> None:
        super()._apply_theme(theme)
        self._style_source_editor()

    def _scale_fonts_for_manual_size(self, new_size: QSize) -> None:
        super()._scale_fonts_for_manual_size(new_size)
        editor = getattr(self, "_source_editor", None)
        if editor is not None:
            editor.adjust_editor_height()


class EditableResizableConversationalAIOverlayManager(
    ResizableConversationalAIOverlayManager
):
    """Manager boundary for the editable production Overlay."""

    def __init__(
        self,
        window: OverlayWindow | None = None,
        *,
        position_manager: PositionManager | None = None,
        config_manager: Any | None = None,
    ) -> None:
        if window is None:
            resolved_position_manager = position_manager or PositionManager(
                config_manager=config_manager,
            )
            window = EditableResizableConversationalAIOverlayWindow(
                position_manager=resolved_position_manager,
                config_manager=config_manager,
            )
        super().__init__(window=window)

    def set_translation_status(self, status: object, *, auto_hide_ms: int = 0) -> str:
        callback = getattr(self.window, "set_translation_status", None)
        if not callable(callback):
            return ""
        return str(callback(status, auto_hide_ms=auto_hide_ms))


__all__ = [
    "EditableResizableConversationalAIOverlayManager",
    "EditableResizableConversationalAIOverlayWindow",
    "EditableSourceTextEdit",
    "MANUAL_TRANSLATION_DEBOUNCE_MILLISECONDS",
    "TRANSLATION_STATUS_FEEDBACK_MILLISECONDS",
]
