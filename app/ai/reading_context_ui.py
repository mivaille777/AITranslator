"""User-visible Reading Context card for the Academic Companion chat surface."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)

from app.ai.chat.models import ChatContext, ReadingContext
from app.ai.chat_interaction_ui import InteractiveManagedChatPanel


_CONTEXT_EXCERPT_LIMIT = 220
_CONTEXT_DETAIL_LIMIT = 420
_CHAT_MODEL_BUTTON_MIN_WIDTH = 118
_CHAT_MODEL_BUTTON_MAX_WIDTH = 168
_CHAT_FONT_BUTTON_WIDTH = 76
_CHAT_CLEAR_BUTTON_WIDTH = 48
_CHAT_DELETE_BUTTON_WIDTH = 40
_CHAT_MODEL_TEXT_LIMIT = 22


def _trim(text: object, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(1, limit - 1)].rstrip() + "…"


def _source_label(source_kind: str) -> str:
    normalized = str(source_kind or "").strip().lower()
    if normalized in {"browser_selection", "browser_page"}:
        return "Browser"
    if "pdf" in normalized:
        return "PDF"
    if "word" in normalized:
        return "Word"
    if "uia" in normalized:
        return "Desktop"
    return "Reading"


def _compact_model_label(provider: object, model: object) -> tuple[str, str]:
    provider_text = str(provider or "").strip()
    model_text = str(model or "").strip()
    if provider_text and model_text:
        full = f"{provider_text} · {model_text}"
    else:
        full = provider_text or model_text or "选择模型"
    return _trim(full, _CHAT_MODEL_TEXT_LIMIT), full


class ReadingContextChatPanel(InteractiveManagedChatPanel):
    """Managed chat that makes the model's active reading evidence visible."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._reading_chat_context = ChatContext()
        self._reading_details_expanded = False
        self._stabilize_chat_header()

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
        if root is not None:
            root.insertWidget(1, self.reading_context_card)

        self.reading_context_expand.toggled.connect(self._toggle_reading_details)
        self.reading_context_card.hide()

    def _stabilize_chat_header(self) -> None:
        """Give variable model text and fixed actions independent layout budgets."""

        root = self.layout()
        top_item = root.itemAt(0) if root is not None else None
        top = top_item.layout() if top_item is not None else None
        if not isinstance(top, QHBoxLayout):
            return

        top.setSpacing(6)
        self.title_label.setMinimumWidth(62)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        model_index = top.indexOf(self.model_button)
        if model_index >= 0:
            # The previous implementation made the model selector the only
            # expanding item. Its long text could then visually collide with
            # Clear/font controls. Put flexible space before a bounded model
            # selector instead so the right-hand action cluster stays stable.
            top.setStretch(model_index, 0)
            top.insertStretch(model_index, 1)

        self.model_button.setMinimumWidth(_CHAT_MODEL_BUTTON_MIN_WIDTH)
        self.model_button.setMaximumWidth(_CHAT_MODEL_BUTTON_MAX_WIDTH)
        self.model_button.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.font_button.setFixedWidth(_CHAT_FONT_BUTTON_WIDTH)
        self.clear_button.setFixedWidth(_CHAT_CLEAR_BUTTON_WIDTH)
        self.delete_chat_button.setFixedWidth(_CHAT_DELETE_BUTTON_WIDTH)

    def set_identity(self, provider: str, model: str) -> None:
        """Elide long model names inside their own bounded toolbar control."""

        compact, full = _compact_model_label(provider, model)
        self.model_button.setText(f"{compact} ▾")
        self.model_button.setToolTip(full if full != "选择模型" else "切换当前对话使用的模型")

    @property
    def reading_chat_context(self) -> ChatContext:
        return self._reading_chat_context

    def append_message(self, role, text: str) -> None:
        """Apply the current independent chat font to every newly-created row."""

        super().append_message(role, text)
        self.set_display_font_size(self.display_font_size)

    def set_context(self, source_text: str, translated_text: str = "") -> None:
        """Update plain context without leaking metadata from another conversation."""

        super().set_context(source_text, translated_text)
        source = str(source_text or "").strip()
        translated = str(translated_text or "").strip()
        current = self._reading_chat_context
        same_selection = bool(
            source
            and source == str(current.source_text or "").strip()
        )
        self.set_reading_context(
            ChatContext(
                source_text=source,
                translated_text=translated,
                reading=current.reading if same_selection else ReadingContext(),
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
        has_page_context = bool(
            reading.resource_title
            or reading.section_heading
            or reading.resource_url
        )
        has_context = bool(source or translated or has_page_context)
        self.reading_context_card.setVisible(has_context)
        if not has_context:
            self.reading_context_details.clear()
            self.reading_context_selection.clear()
            QTimer.singleShot(0, self.refresh_adaptive_height)
            return

        source_name = _source_label(reading.source_kind)
        self.reading_context_source.setText(f"📄 {source_name}")
        title = _trim(reading.resource_title, 84) or (
            "当前页面" if has_page_context and not source else "当前阅读选区"
        )
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
            self.reading_context_selection.setText(
                f"选区 · {_trim(source, _CONTEXT_EXCERPT_LIMIT)}"
            )
        elif translated:
            self.reading_context_selection.setText(
                f"译文 · {_trim(translated, _CONTEXT_EXCERPT_LIMIT)}"
            )
        elif has_page_context:
            self.reading_context_selection.setText("当前页面 · 尚未选择具体文本")
        else:
            self.reading_context_selection.clear()

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
        QTimer.singleShot(0, self.refresh_adaptive_height)

    def _toggle_reading_details(self, expanded: bool) -> None:
        self._reading_details_expanded = bool(expanded)
        has_details = bool(self.reading_context_details.text())
        self.reading_context_details.setVisible(self._reading_details_expanded and has_details)
        self.reading_context_expand.setText("⌃" if self._reading_details_expanded else "⌄")
        QTimer.singleShot(0, self.refresh_adaptive_height)

    def apply_palette(self, palette: dict[str, str]) -> None:
        super().apply_palette(palette)
        chrome_background = palette.get("chrome_background", palette["menu_background"])
        chrome_border = palette.get("chrome_border", palette["border"])
        chrome_hover = palette.get("chrome_hover", palette["hover"])
        chrome_text = palette.get("chrome_text", palette["text"])
        chrome_muted = palette.get("chrome_muted_text", palette["muted_text"])
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QFrame#OverlayReadingContextCard {{
                background-color: {chrome_background};
                border: 1px solid {chrome_border};
                border-radius: 9px;
            }}
            QLabel#OverlayReadingContextSource {{
                color: {palette['accent']};
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#OverlayReadingContextTitle {{
                color: {chrome_text};
                font-weight: 600;
            }}
            QLabel#OverlayReadingContextMeta {{
                color: {chrome_muted};
                font-size: 10px;
            }}
            QLabel#OverlayReadingContextSelection {{
                color: {chrome_text};
                background-color: transparent;
            }}
            QLabel#OverlayReadingContextDetails {{
                color: {chrome_muted};
                background-color: transparent;
                padding-top: 3px;
            }}
            QToolButton#OverlayReadingContextExpand {{
                color: {chrome_muted};
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
            }}
            QToolButton#OverlayReadingContextExpand:hover:enabled {{
                color: {chrome_text};
                background-color: {chrome_hover};
                border-color: {chrome_border};
            }}
            """
        )


__all__ = ["ReadingContextChatPanel"]
