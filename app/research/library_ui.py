"""Research Notes Library window for browsing and editing persisted reading notes."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.overlay.context_menu import OVERLAY_THEMES
from app.research.notes import ResearchNote


class ResearchNotesLibraryWindow(QDialog):
    """Two-pane local research-memory browser with editable user notes."""

    search_requested = Signal(str)
    user_note_save_requested = Signal(str, str)
    note_delete_requested = Signal(str)

    def __init__(self, parent=None, *, palette: dict[str, str] | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ResearchNotesLibraryWindow")
        self.setWindowTitle("AITrans · Research Notes")
        self.setModal(False)
        self.resize(980, 650)
        self.setMinimumSize(760, 520)
        self._notes: dict[str, ResearchNote] = {}
        self._active_note_id = ""
        self._palette = dict(palette or OVERLAY_THEMES["dark"])

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Research Notes", self)
        title.setObjectName("ResearchNotesTitle")
        subtitle = QLabel("把阅读、翻译和 AI 理解沉淀为可检索的个人研究记忆", self)
        subtitle.setObjectName("ResearchNotesSubtitle")
        header_text = QVBoxLayout()
        header_text.setSpacing(1)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)
        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("ResearchNotesSearch")
        self.search_edit.setPlaceholderText("搜索文献、章节、原文、AI 结果或个人笔记…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(310)
        header.addWidget(self.search_edit)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("ResearchNotesSplitter")
        root.addWidget(splitter, 1)

        left = QFrame(splitter)
        left.setObjectName("ResearchNotesListPane")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)
        self.result_label = QLabel("0 条笔记", left)
        self.result_label.setObjectName("ResearchNotesResultCount")
        left_layout.addWidget(self.result_label)
        self.notes_list = QListWidget(left)
        self.notes_list.setObjectName("ResearchNotesList")
        self.notes_list.setSpacing(2)
        left_layout.addWidget(self.notes_list, 1)
        splitter.addWidget(left)

        right = QFrame(splitter)
        right.setObjectName("ResearchNotesDetailPane")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 10, 12, 10)
        right_layout.setSpacing(7)

        self.detail_title = QLabel("选择一条研究笔记", right)
        self.detail_title.setObjectName("ResearchNoteDetailTitle")
        self.detail_title.setWordWrap(True)
        right_layout.addWidget(self.detail_title)

        self.detail_meta = QLabel("", right)
        self.detail_meta.setObjectName("ResearchNoteDetailMeta")
        self.detail_meta.setWordWrap(True)
        self.detail_meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right_layout.addWidget(self.detail_meta)

        self.source_edit = self._read_only_area("ResearchNoteSource", "原文")
        self.translation_edit = self._read_only_area("ResearchNoteTranslation", "译文")
        self.ai_edit = self._read_only_area("ResearchNoteAI", "AI 阅读结果")
        self.user_note_edit = QPlainTextEdit(right)
        self.user_note_edit.setObjectName("ResearchNoteUserNote")
        self.user_note_edit.setPlaceholderText("写下你自己的理解、疑问、实验想法或待验证结论…")
        self.user_note_edit.setMinimumHeight(80)
        self.user_note_edit.setMaximumHeight(130)

        right_layout.addWidget(self._section_label("原文", right))
        right_layout.addWidget(self.source_edit)
        right_layout.addWidget(self._section_label("译文", right))
        right_layout.addWidget(self.translation_edit)
        right_layout.addWidget(self._section_label("AI 阅读结果", right))
        right_layout.addWidget(self.ai_edit)
        right_layout.addWidget(self._section_label("我的笔记", right))
        right_layout.addWidget(self.user_note_edit)

        actions = QHBoxLayout()
        self.open_source_button = QPushButton("打开来源", right)
        self.open_source_button.setObjectName("ResearchNoteOpenSource")
        self.save_button = QPushButton("保存我的笔记", right)
        self.save_button.setObjectName("ResearchNoteSaveUserNote")
        self.delete_button = QPushButton("删除", right)
        self.delete_button.setObjectName("ResearchNoteDelete")
        self.close_button = QPushButton("关闭", right)
        self.close_button.setObjectName("ResearchNotesClose")
        actions.addWidget(self.open_source_button)
        actions.addStretch(1)
        actions.addWidget(self.delete_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.close_button)
        right_layout.addLayout(actions)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([320, 640])

        self.search_edit.textChanged.connect(self.search_requested.emit)
        self.notes_list.currentItemChanged.connect(self._on_current_item_changed)
        self.save_button.clicked.connect(self._request_save)
        self.delete_button.clicked.connect(self._request_delete)
        self.open_source_button.clicked.connect(self._open_source)
        self.close_button.clicked.connect(self.hide)
        self._sync_detail_state()
        self.apply_palette(self._palette)

    @staticmethod
    def _section_label(text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName("ResearchNoteSectionLabel")
        return label

    @staticmethod
    def _read_only_area(object_name: str, _placeholder: str) -> QPlainTextEdit:
        edit = QPlainTextEdit()
        edit.setObjectName(object_name)
        edit.setReadOnly(True)
        edit.setMaximumHeight(105)
        return edit

    @property
    def active_note_id(self) -> str:
        return self._active_note_id

    @property
    def search_query(self) -> str:
        return self.search_edit.text().strip()

    @property
    def palette(self) -> dict[str, str]:
        return dict(self._palette)

    def set_notes(self, notes: tuple[ResearchNote, ...] | list[ResearchNote]) -> None:
        previous = self._active_note_id
        self._notes = {note.note_id: note for note in notes}
        self.notes_list.clear()
        for note in notes:
            section = f" · {note.section_heading}" if note.section_heading else ""
            item = QListWidgetItem(f"{note.display_title}{section}\n{note.excerpt}")
            item.setData(Qt.ItemDataRole.UserRole, note.note_id)
            item.setToolTip(note.resource_url or note.display_title)
            self.notes_list.addItem(item)
            if note.note_id == previous:
                self.notes_list.setCurrentItem(item)
        self.result_label.setText(f"{len(notes)} 条笔记")
        if self.notes_list.currentItem() is None and self.notes_list.count() > 0:
            self.notes_list.setCurrentRow(0)
        if self.notes_list.count() == 0:
            self._active_note_id = ""
            self._render_note(None)

    def _on_current_item_changed(self, current: QListWidgetItem | None, _previous) -> None:
        note_id = str(current.data(Qt.ItemDataRole.UserRole) or "") if current else ""
        self._active_note_id = note_id
        self._render_note(self._notes.get(note_id))

    def _render_note(self, note: ResearchNote | None) -> None:
        if note is None:
            self.detail_title.setText("选择一条研究笔记")
            self.detail_meta.clear()
            self.source_edit.clear()
            self.translation_edit.clear()
            self.ai_edit.clear()
            self.user_note_edit.clear()
            self._sync_detail_state()
            return

        self.detail_title.setText(note.display_title)
        meta: list[str] = []
        if note.section_heading:
            meta.append(f"§ {note.section_heading}")
        if note.source_kind:
            meta.append(note.source_kind)
        if note.updated_at:
            meta.append(f"更新 {note.updated_at[:19].replace('T', ' ')}")
        if note.resource_url:
            meta.append(note.resource_url)
        self.detail_meta.setText(" · ".join(meta))
        self.source_edit.setPlainText(note.source_text)
        self.translation_edit.setPlainText(note.translated_text)
        self.ai_edit.setPlainText(note.ai_content)
        self.user_note_edit.setPlainText(note.user_note)
        self._sync_detail_state()

    def _sync_detail_state(self) -> None:
        note = self._notes.get(self._active_note_id)
        active = note is not None
        self.user_note_edit.setEnabled(active)
        self.save_button.setEnabled(active)
        self.delete_button.setEnabled(active)
        self.open_source_button.setEnabled(bool(note and note.resource_url))

    def _request_save(self) -> None:
        if not self._active_note_id:
            return
        self.user_note_save_requested.emit(
            self._active_note_id,
            self.user_note_edit.toPlainText(),
        )

    def _request_delete(self) -> None:
        if self._active_note_id:
            self.note_delete_requested.emit(self._active_note_id)

    def _open_source(self) -> None:
        note = self._notes.get(self._active_note_id)
        if note is None or not note.resource_url:
            return
        QDesktopServices.openUrl(QUrl(note.resource_url))

    def apply_palette(self, palette: dict[str, str]) -> None:
        self._palette = dict(palette or OVERLAY_THEMES["dark"])
        p = self._palette
        self.setStyleSheet(
            f"""
            QDialog#ResearchNotesLibraryWindow {{
                background: {p['menu_background']}; color: {p['text']};
            }}
            QLabel#ResearchNotesTitle {{
                color: {p['text']}; font-size: 22px; font-weight: 650;
            }}
            QLabel#ResearchNotesSubtitle,
            QLabel#ResearchNotesResultCount,
            QLabel#ResearchNoteDetailMeta {{ color: {p['muted_text']}; }}
            QFrame#ResearchNotesListPane,
            QFrame#ResearchNotesDetailPane {{
                background: {p['label_background']};
                border: 1px solid {p['border']}; border-radius: 10px;
            }}
            QLineEdit#ResearchNotesSearch, QPlainTextEdit {{
                color: {p['text']}; background: {p['menu_background']};
                border: 1px solid {p['border']}; border-radius: 8px;
                padding: 7px 9px; selection-background-color: {p['accent']};
            }}
            QListWidget#ResearchNotesList {{
                color: {p['muted_text']}; background: transparent;
                border: none; outline: none;
            }}
            QListWidget#ResearchNotesList::item {{
                border-radius: 7px; padding: 8px; margin: 1px 0;
            }}
            QListWidget#ResearchNotesList::item:selected {{
                color: {p['text']}; background: {p['hover']};
            }}
            QLabel#ResearchNoteDetailTitle {{
                color: {p['text']}; font-size: 18px; font-weight: 620;
            }}
            QLabel#ResearchNoteSectionLabel {{
                color: {p['accent']}; font-size: 11px; font-weight: 600;
            }}
            QPushButton {{
                color: {p['text']}; background: transparent;
                border: 1px solid {p['border']}; border-radius: 7px;
                padding: 7px 12px;
            }}
            QPushButton:hover:enabled {{
                background: {p['hover']}; border-color: {p['accent']};
            }}
            QPushButton#ResearchNoteSaveUserNote {{
                color: {p['text']}; background: {p['hover']};
            }}
            QPushButton:disabled {{ color: {p['muted_text']}; }}
            """
        )


__all__ = ["ResearchNotesLibraryWindow"]
