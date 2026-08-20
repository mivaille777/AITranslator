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
from app.ui.design_tokens import (
    CONTROL,
    LAYOUT,
    MOTION,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)


_CONTEXT_EXCERPT_LIMIT = 220
_CONTEXT_DETAIL_LIMIT = 420
_CHAT_MODEL_BUTTON_MIN_WIDTH = LAYOUT.chat_model_min_width
_CHAT_MODEL_BUTTON_MAX_WIDTH = LAYOUT.chat_model_max_width
_CHAT_FONT_BUTTON_WIDTH = CONTROL.large_height + SPACING.xxl
_CHAT_CLEAR_BUTTON_WIDTH = CONTROL.normal_height + SPACING.md
_CHAT_DELETE_BUTTON_WIDTH = CONTROL.normal_height + SPACING.xs
_CHAT_MODEL_TEXT_LIMIT = 22
_FINAL_REFLOW_DELAYS_MS = MOTION.final_reflow_ms


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
        card_layout.setContentsMargins(
            SPACING.sm,
            RADIUS.sm,
            SPACING.sm,
            RADIUS.sm,
        )
        card_layout.setSpacing(SPACING.xs)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(SPACING.sm)
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
        self.reading_context_expand.setFixedSize(
            CONTROL.compact_height,
            CONTROL.compact_height - SPACING.xs,
        )
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

        top.setSpacing(SPACING.sm)
        self.title_label.setMinimumWidth(CONTROL.large_height + TYPOGRAPHY.title)
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

    def _fit_message_rows_to_viewport(self) -> None:
        """Bind transcript rows to the realized viewport before height measurement.

        Qt can keep a stale Markdown QLabel height-for-width cache when a
        streaming row is replaced by the final assistant row. Reapplying the
        font invalidated that cache, which is why changing font size used to
        make a clipped answer tail suddenly appear. Explicit row/body widths
        make the final height deterministic without changing typography.
        """

        viewport_width = self.messages_scroll.viewport().width()
        if viewport_width <= 16:
            return
        margins = self.messages_layout.contentsMargins()
        available_width = max(
            1,
            viewport_width - margins.left() - margins.right(),
        )
        rows = list(self._message_rows)
        streaming_row = getattr(self, "_streaming_row", None)
        if streaming_row is not None:
            rows.append(streaming_row)

        for row in rows:
            try:
                row.setMinimumWidth(available_width)
                row.setMaximumWidth(available_width)
                row.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Preferred,
                )
                row_layout = row.layout()
                inner_width = available_width
                if row_layout is not None:
                    inner_margins = row_layout.contentsMargins()
                    inner_width = max(
                        1,
                        available_width
                        - inner_margins.left()
                        - inner_margins.right(),
                    )
                body = row.findChild(QLabel, "OverlayChatMessageBody")
                if body is not None:
                    body.setMinimumWidth(inner_width)
                    body.setMaximumWidth(inner_width)
                    body.setSizePolicy(
                        QSizePolicy.Policy.Fixed,
                        QSizePolicy.Policy.Preferred,
                    )
                    body.updateGeometry()
                if row_layout is not None:
                    row_layout.invalidate()
                    row_layout.activate()
                row.updateGeometry()
            except RuntimeError:
                continue

        self.messages_layout.invalidate()
        self.messages_layout.activate()
        self.messages_content.updateGeometry()
        QTimer.singleShot(0, self.refresh_adaptive_height)

    def _schedule_final_transcript_reflow(self) -> None:
        """Run bounded post-render passes while Qt settles Markdown geometry."""

        for delay in _FINAL_REFLOW_DELAYS_MS:
            QTimer.singleShot(delay, self._force_final_transcript_reflow)

    def _force_final_transcript_reflow(self) -> None:
        try:
            self._fit_message_rows_to_viewport()
            rows = list(self._message_rows)
            streaming_row = getattr(self, "_streaming_row", None)
            if streaming_row is not None:
                rows.append(streaming_row)
            for row in rows:
                body = row.findChild(QLabel, "OverlayChatMessageBody")
                if body is not None:
                    body.updateGeometry()
                row_layout = row.layout()
                if row_layout is not None:
                    row_layout.invalidate()
                    row_layout.activate()
                row.updateGeometry()
            self.messages_layout.invalidate()
            self.messages_layout.activate()
            self.messages_content.updateGeometry()
            self.refresh_adaptive_height()
            self.stream_layout_changed.emit()
            self._scroll_after_content_change()
        except RuntimeError:
            # The overlay may be closing while one of the bounded timers fires.
            return

    def append_message(self, role, text: str) -> None:
        """Apply current chat font and finalize wrapped Markdown geometry."""

        super().append_message(role, text)
        self.set_display_font_size(self.display_font_size)
        self._schedule_final_transcript_reflow()

    def finish_streaming_reply(self, request_id: int, text: str) -> bool:
        """Finalize a streamed answer only after its replacement row reflows."""

        finished = super().finish_streaming_reply(request_id, text)
        if finished:
            self._schedule_final_transcript_reflow()
        return finished

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
                border-radius: {RADIUS.lg}px;
            }}
            QLabel#OverlayReadingContextSource {{
                color: {palette['accent']};
                font-size: {TYPOGRAPHY.caption}px;
                font-weight: {TYPOGRAPHY.weight_semibold};
            }}
            QLabel#OverlayReadingContextTitle {{
                color: {chrome_text};
                font-weight: {TYPOGRAPHY.weight_semibold};
            }}
            QLabel#OverlayReadingContextMeta {{
                color: {chrome_muted};
                font-size: {TYPOGRAPHY.caption}px;
            }}
            QLabel#OverlayReadingContextSelection {{
                color: {chrome_text};
                background-color: transparent;
            }}
            QLabel#OverlayReadingContextDetails {{
                color: {chrome_muted};
                background-color: transparent;
                padding-top: {SPACING.xxs}px;
            }}
            QToolButton#OverlayReadingContextExpand {{
                color: {chrome_muted};
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: {RADIUS.sm}px;
            }}
            QToolButton#OverlayReadingContextExpand:hover:enabled {{
                color: {chrome_text};
                background-color: {chrome_hover};
                border-color: {chrome_border};
            }}
            """
        )


__all__ = ["ReadingContextChatPanel"]
