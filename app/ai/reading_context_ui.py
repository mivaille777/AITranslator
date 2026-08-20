"""User-visible Reading Context card for the Academic Companion chat surface."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout

from app.ai.chat.models import ChatContext, ReadingContext
from app.ai.chat_interaction_ui import InteractiveManagedChatPanel


_CONTEXT_EXCERPT_LIMIT = 220
_CONTEXT_DETAIL_LIMIT = 420


def _trim(text: object, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(1, limit - 1)].rstrip() + "…"


def _source_label(source_kind: str) -> str:
    normalized = str(source_kind or "").strip().lower()
    if normalized == "browser_selection":
        return "Browser"
    if "word" in normalized:
        return "Word"
    if "uia" in normalized:
        return "Desktop"
    if "pdf" in normalized:
        return "PDF"
    return "Reading"


class ReadingContextChatPanel(InteractiveManagedChatPanel):
    """Managed chat that makes the model's active reading evidence visible."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._reading_chat_context = ChatContext()
        self._reading_details_expanded = False

        # Replace the legacy character-count control with a compact evidence
        # card. Keep the old widgets alive for compatibility but out of sight.
        self.context_button.hide()
        self.context_preview.hide()

        self.reading_context_card = QFrame(self)
        self.reading_context_card.setObjectName("OverlayReadingContextCard")
        self.reading_context_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card_layout = QVBoxLayout(self.reading_context_card)
        card_layout.setContentsMargins(9, 7, 9, 7)
        card_layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        self.reading_context_source = QLabel("📄 Reading", self.reading_context_card)
        self.reading_context_source.setObjectName("OverlayReadingContextSource")
        self.reading_context_title = QLabel("", self.reading_context_card)
        self.reading_context_title.setObjectName("OverlayReadingContextTitle")
        self.reading_context_title.setTextFormat(Qt.TextFormat.PlainText)
        self.reading_context_title.setWordWrap(False)
        self.reading_context_expand = QToolButton(self.reading_context_card)
        self.reading_context_expand.setObjectName("OverlayReadingContextExpand")
        self.reading_context_expand.setText("⌄")
        self.reading_context_expand.setToolTip("查看 Reading Context")
        self.reading_context_expand.setCheckable(True)
        self.reading_context_expand.setFixedSize(28, 24)
        header.addWidget(self.reading_context_source)
        header.addWidget(self.reading_context_title, 1)
        header.addWidget(self.reading_context_expand)
        card_layout.addLayout(header)

        self.reading_context_meta = QLabel("", self.reading_context_card)
        self.reading_context_meta.setObjectName("OverlayReadingContextMeta")
        self.reading_context_meta.setTextFormat(Qt.TextFormat.PlainText)
        self.reading_context_meta.setWordWrap(True)
        card_layout.addWidget(self.reading_context_meta)

        self.reading_context_selection = QLabel("", self.reading_context_card)
        self.reading_context_selection.setObjectName("OverlayReadingContextSelection")
        self.reading_context_selection.setTextFormat(Qt.TextFormat.PlainText)
        self.reading_context_selection.setWordWrap(True)
        self.reading_context_selection.setMaximumHeight(58)
        card_layout.addWidget(self.reading_context_selection)

        self.reading_context_details = QLabel("", self.reading_context_card)
        self.reading_context_details.setObjectName("OverlayReadingContextDetails")
        self.reading_context_details.setTextFormat(Qt.TextFormat.PlainText)
        self.reading_context_details.setWordWrap(True)
        self.reading_context_details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.reading_context_details.setMaximumHeight(150)
        self.reading_context_details.hide()
        card_layout.addWidget(self.reading_context_details)

        root = self.layout()
        # Header is index 0. Place Reading Context immediately after it so the
        # evidence remains visible before the conversation transcript.
        if root is not None:
            root.insertWidget(1, self.reading_context_card)

        self.reading_context_expand.toggled.connect(self._toggle_reading_details)
        self.reading_context_card.hide()

    @property
    def reading_chat_context(self) -> ChatContext:
        return self._reading_chat_context

    def set_context(self, source_text: str, translated_text: str = "") -> None:
        super().set_context(source_text, translated_text)
        # Preserve visible context even before browser/Word metadata arrives.
        current = self._reading_chat_context
        self.set_reading_context(
            ChatContext(
                source_text=str(source_text or "").strip(),
                translated_text=str(translated_text or "").strip(),
                reading=current.reading,
            )
        )

    def set_reading_context(self, context: ChatContext | object) -> None:
        if isinstance(context, ChatContext):
            resolved = context
        else:
            resolved = ChatContext()
        self._reading_chat_context = resolved

        source = str(resolved.source_text or "").strip()
        translated = str(resolved.translated_text or "").strip()
        reading = resolved.reading if isinstance(resolved.reading, ReadingContext) else ReadingContext()
        has_context = bool(
            source
            or translated
            or reading.resource_title
            or reading.section_heading
            or reading.resource_url
        )
        self.reading_context_card.setVisible(has_context)
        if not has_context:
            self.reading_context_details.clear()
            self.reading_context_selection.clear()
            return

        source_name = _source_label(reading.source_kind)
        self.reading_context_source.setText(f"📄 {source_name}")
        title = _trim(reading.resource_title, 84) or "当前阅读选区"
        self.reading_context_title.setText(title)
        self.reading_context_title.setToolTip(str(reading.resource_title or title))

        meta_parts: list[str] = []
        if reading.section_heading:
            meta_parts.append(f"§ {_trim(reading.section_heading, 100)}")
        if reading.resource_url:
            meta_parts.append(_trim(reading.resource_url, 100))
        self.reading_context_meta.setText(" · ".join(meta_parts))
        self.reading_context_meta.setVisible(bool(meta_parts))

        if source:
            self.reading_context_selection.setText(f"选区 · {_trim(source, _CONTEXT_EXCERPT_LIMIT)}")
        else:
            self.reading_context_selection.setText(f"译文 · {_trim(translated, _CONTEXT_EXCERPT_LIMIT)}")

        detail_lines: list[str] = []
        if translated and source:
            detail_lines.append(f"当前译文\n{_trim(translated, _CONTEXT_DETAIL_LIMIT)}")
        if reading.context_before:
            detail_lines.append(f"前文\n{_trim(reading.context_before, _CONTEXT_DETAIL_LIMIT)}")
        if reading.context_after:
            detail_lines.append(f"后文\n{_trim(reading.context_after, _CONTEXT_DETAIL_LIMIT)}")
        self.reading_context_details.setText("\n\n".join(detail_lines))
        self.reading_context_expand.setEnabled(bool(detail_lines))
        if not detail_lines:
            self.reading_context_expand.setChecked(False)
        self._toggle_reading_details(self.reading_context_expand.isChecked())

    def _toggle_reading_details(self, expanded: bool) -> None:
        self._reading_details_expanded = bool(expanded)
        has_details = bool(self.reading_context_details.text())
        self.reading_context_details.setVisible(self._reading_details_expanded and has_details)
        self.reading_context_expand.setText("⌃" if self._reading_details_expanded else "⌄")

    def apply_palette(self, palette: dict[str, str]) -> None:
        super().apply_palette(palette)
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QFrame#OverlayReadingContextCard {{
                background-color: {palette['label_background']};
                border: 1px solid {palette['border']};
                border-radius: 9px;
            }}
            QLabel#OverlayReadingContextSource {{
                color: {palette['accent']};
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#OverlayReadingContextTitle {{
                color: {palette['text']};
                font-weight: 600;
            }}
            QLabel#OverlayReadingContextMeta {{
                color: {palette['muted_text']};
                font-size: 10px;
            }}
            QLabel#OverlayReadingContextSelection {{
                color: {palette['text']};
                background-color: transparent;
            }}
            QLabel#OverlayReadingContextDetails {{
                color: {palette['muted_text']};
                background-color: transparent;
                padding-top: 3px;
            }}
            QToolButton#OverlayReadingContextExpand {{
                color: {palette['muted_text']};
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
            }}
            QToolButton#OverlayReadingContextExpand:hover:enabled {{
                color: {palette['text']};
                background-color: {palette['hover']};
                border-color: {palette['border']};
            }}
            """
        )


__all__ = ["ReadingContextChatPanel"]
