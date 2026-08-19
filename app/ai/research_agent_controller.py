"""Production Academic Companion controller with persistent research notes."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QToolTip

from app.ai.chat import ChatResult
from app.ai.chat.task import AIChatTaskFailure
from app.ai.desktop_agent_controller import DesktopAgentAppController
from app.ai.research_agent_overlay import (
    RESEARCH_NOTE_SAVE,
    RESEARCH_NOTES_RECENT,
    ResearchAgentOverlayManager,
)
from app.infrastructure.settings import SettingsManager
from app.models.reading_actions import READING_ACTION_KEYS
from app.research.notes import ResearchNote, ResearchNoteStore


RESEARCH_NOTE_SAVED_TEXT = "已加入研究笔记"
RESEARCH_NOTE_UPDATED_TEXT = "研究笔记已更新"
RESEARCH_NOTE_FAILED_TEXT = "研究笔记保存失败"
RESEARCH_NOTE_FEEDBACK_MILLISECONDS = 1500
RECENT_RESEARCH_NOTE_LIMIT = 8


class ResearchAgentAppController(DesktopAgentAppController):
    """Add deterministic research-memory persistence to the Desktop Agent."""

    def __init__(
        self,
        *args: Any,
        research_note_store: ResearchNoteStore | Any | None = None,
        **kwargs: Any,
    ) -> None:
        if kwargs.get("overlay_manager") is None:
            resolved_config = kwargs.get("config_manager")
            if resolved_config is None:
                resolved_config = SettingsManager()
                kwargs["config_manager"] = resolved_config
            kwargs["overlay_manager"] = ResearchAgentOverlayManager(
                config_manager=resolved_config,
            )

        self.research_note_store = research_note_store or ResearchNoteStore()
        self._pending_reading_action_request_id: int | None = None
        self._pending_reading_action_key = ""
        self._pending_reading_action_source_text = ""
        self._last_reading_action_key = ""
        self._last_reading_action_source_text = ""
        self._last_reading_action_output = ""
        super().__init__(*args, **kwargs)

    def _clear_pending_reading_action(self) -> None:
        self._pending_reading_action_request_id = None
        self._pending_reading_action_key = ""
        self._pending_reading_action_source_text = ""

    def _set_reading_context(self, selected_text: str, reading) -> None:
        normalized = str(selected_text or "").strip()
        previous = str(getattr(self, "_reading_context_source_text", "") or "").strip()
        super()._set_reading_context(selected_text, reading)
        if normalized != previous:
            self._clear_pending_reading_action()
            self._last_reading_action_key = ""
            self._last_reading_action_source_text = ""
            self._last_reading_action_output = ""

    def _submit_reading_action(self, key: str) -> bool:
        if key not in READING_ACTION_KEYS:
            return super()._submit_reading_action(key)

        source_text = str(self._last_source_text or "").strip()
        previous_request = self._active_stream_request_id
        handled = super()._submit_reading_action(key)
        request_id = self._active_stream_request_id
        if (
            handled
            and source_text
            and request_id is not None
            and request_id != previous_request
        ):
            self._pending_reading_action_request_id = request_id
            self._pending_reading_action_key = key
            self._pending_reading_action_source_text = source_text
        return handled

    def _on_chat_task_succeeded(self, result: object) -> None:
        should_capture = bool(
            isinstance(result, ChatResult)
            and result.request_id == self._pending_reading_action_request_id
            and self._chat_request_versions.is_latest(result.request_id)
        )
        action_key = self._pending_reading_action_key
        source_text = self._pending_reading_action_source_text
        super()._on_chat_task_succeeded(result)
        if should_capture and isinstance(result, ChatResult):
            self._last_reading_action_key = action_key
            self._last_reading_action_source_text = source_text
            self._last_reading_action_output = str(result.output_text or "").strip()
            self._clear_pending_reading_action()

    def _on_chat_task_failed(self, failure: object) -> None:
        request_id = (
            failure.request_id if isinstance(failure, AIChatTaskFailure) else None
        )
        super()._on_chat_task_failed(failure)
        if request_id == self._pending_reading_action_request_id:
            self._clear_pending_reading_action()

    def _stop_chat_generation(self) -> None:
        request_id = self._active_stream_request_id
        partial = str(self._active_stream_partial or "").strip()
        action_key = self._pending_reading_action_key
        source_text = self._pending_reading_action_source_text
        was_reading_action = bool(
            request_id is not None
            and request_id == self._pending_reading_action_request_id
        )
        super()._stop_chat_generation()
        if was_reading_action:
            if partial:
                self._last_reading_action_key = action_key
                self._last_reading_action_source_text = source_text
                self._last_reading_action_output = partial
            self._clear_pending_reading_action()

    def _current_note_ai_fields(self, source_text: str) -> tuple[str, str]:
        normalized = str(source_text or "").strip()
        if normalized and normalized == self._last_reading_action_source_text:
            return self._last_reading_action_output, self._last_reading_action_key
        return "", ""

    def _show_research_note_feedback(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        set_status = getattr(self, "_set_translation_status", None)
        if callable(set_status):
            try:
                set_status(text, auto_hide_ms=RESEARCH_NOTE_FEEDBACK_MILLISECONDS)
            except Exception:
                pass
        try:
            window = getattr(self.overlay_manager, "window", None)
            QToolTip.showText(QCursor.pos(), text, window)
        except Exception:
            pass

    def _save_current_research_note(self) -> bool:
        context = self._current_reading_context()
        source_text = str(context.source_text or "").strip()
        if not source_text:
            self._show_research_note_feedback("请先选中一段需要保存的内容")
            return True

        ai_content, ai_action = self._current_note_ai_fields(source_text)
        active = getattr(self.conversation_manager, "active", None)
        conversation_id = (
            str(getattr(active, "conversation_id", "") or "").strip()
            if active is not None
            else ""
        )
        try:
            result = self.research_note_store.save_context(
                context,
                ai_content=ai_content,
                ai_action=ai_action,
                conversation_id=conversation_id,
            )
        except Exception as exc:
            self._log_exception("research_note_save_failed", exc)
            self._show_research_note_feedback(RESEARCH_NOTE_FAILED_TEXT)
            return True

        feedback = RESEARCH_NOTE_SAVED_TEXT if result.created else RESEARCH_NOTE_UPDATED_TEXT
        self._show_research_note_feedback(feedback)
        self.logger.info(
            "research_note_saved created=%s has_resource=%s has_ai_content=%s",
            result.created,
            bool(result.note.resource_url or result.note.resource_title),
            bool(result.note.ai_content),
        )
        return True

    @staticmethod
    def _format_recent_note(note: ResearchNote, index: int) -> str:
        title = note.display_title
        location = f" · {note.section_heading}" if note.section_heading else ""
        ai_marker = " · 含 AI 阅读结果" if note.ai_content else ""
        updated = note.updated_at[:10] if note.updated_at else ""
        date_marker = f" · {updated}" if updated else ""
        return (
            f"{index}. **{title}**{location}{ai_marker}{date_marker}\n"
            f"   {note.excerpt}"
        )

    def _show_recent_research_notes(self) -> bool:
        try:
            notes = self.research_note_store.list_recent(limit=RECENT_RESEARCH_NOTE_LIMIT)
        except Exception as exc:
            self._log_exception("research_notes_list_failed", exc)
            notes = ()

        if notes:
            body = "最近研究笔记：\n\n" + "\n\n".join(
                self._format_recent_note(note, index)
                for index, note in enumerate(notes, start=1)
            )
        else:
            body = "研究笔记中还没有内容。选中文献段落后，使用“AI 助手 → 加入研究笔记”即可保存。"

        if not self._is_ai_chat_open():
            self._open_ai_chat()
        self._present_tool_direct_reply(
            "查看最近研究笔记",
            body,
            user_already_rendered=False,
        )
        self.logger.info("research_notes_recent_presented count=%s", len(notes))
        return True

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        if key == RESEARCH_NOTE_SAVE:
            self._save_current_research_note()
            return
        if key == RESEARCH_NOTES_RECENT:
            self._show_recent_research_notes()
            return
        super()._on_overlay_context_action(key, value)


__all__ = [
    "RECENT_RESEARCH_NOTE_LIMIT",
    "RESEARCH_NOTE_FAILED_TEXT",
    "RESEARCH_NOTE_SAVED_TEXT",
    "RESEARCH_NOTE_UPDATED_TEXT",
    "ResearchAgentAppController",
]
