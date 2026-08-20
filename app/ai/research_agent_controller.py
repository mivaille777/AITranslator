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
    RESEARCH_NOTES_LIBRARY,
    RESEARCH_NOTES_RECENT,
    ResearchAgentOverlayManager,
)
from app.infrastructure.settings import SettingsManager
from app.models.reading_actions import READING_ACTION_KEYS
from app.overlay.context_menu import OVERLAY_THEMES
from app.research.library import ResearchNoteLibraryStore
from app.research.library_ui import ResearchNotesLibraryWindow
from app.research.notes import ResearchNote, ResearchNoteStore


RESEARCH_NOTE_SAVED_TEXT = "已加入研究笔记"
RESEARCH_NOTE_UPDATED_TEXT = "研究笔记已更新"
RESEARCH_NOTE_FAILED_TEXT = "研究笔记保存失败"
RESEARCH_NOTE_FEEDBACK_MILLISECONDS = 2200
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

        self.research_note_store = research_note_store or ResearchNoteLibraryStore()
        self._research_notes_window: ResearchNotesLibraryWindow | None = None
        self._pending_reading_action_request_id: int | None = None
        self._pending_reading_action_key = ""
        self._pending_reading_action_source_text = ""
        self._last_reading_action_key = ""
        self._last_reading_action_source_text = ""
        self._last_reading_action_output = ""
        super().__init__(*args, **kwargs)

    def shutdown(self) -> None:
        window = getattr(self, "_research_notes_window", None)
        if window is not None:
            try:
                window.close()
            except RuntimeError:
                pass
        super().shutdown()

    def _show_settings(self) -> None:
        """Bind runtime browser/research services to the product settings page."""

        super()._show_settings()
        window = getattr(self, "_settings_window", None)
        if window is None:
            return
        window.browser_bridge = self.browser_selection_bridge
        window.research_note_store = self.research_note_store
        if not bool(getattr(window, "_research_agent_runtime_bound", False)):
            signal = getattr(window, "research_notes_requested", None)
            connect = getattr(signal, "connect", None)
            if callable(connect):
                connect(self._open_research_notes_library)
            window._research_agent_runtime_bound = True
        refresh = getattr(window, "refresh_runtime_status", None)
        if callable(refresh):
            refresh()

    def _apply_saved_settings(self, values: object) -> None:
        super()._apply_saved_settings(values)
        library = getattr(self, "_research_notes_window", None)
        if library is not None:
            library.apply_palette(self._research_palette())

    def _research_palette(self) -> dict[str, str]:
        overlay_window = getattr(self.overlay_manager, "window", None)
        theme = str(getattr(overlay_window, "_theme_name", "dark") or "dark")
        return OVERLAY_THEMES.get(theme, OVERLAY_THEMES["dark"])

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

    def _sync_active_reading_context(self) -> None:
        """Persist context and keep the user-visible Reading Context card in sync."""

        context = self._current_reading_context()
        super()._sync_active_reading_context()
        self._chat_overlay_call("set_chat_reading_context", context)

    def _open_ai_chat(self) -> None:
        super()._open_ai_chat()
        self._chat_overlay_call(
            "set_chat_reading_context",
            self._current_reading_context(),
        )

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

    def _show_research_note_feedback(
        self,
        message: str,
        *,
        show_view: bool = False,
    ) -> None:
        text = str(message or "").strip()
        if not text:
            return
        set_status = getattr(self, "_set_translation_status", None)
        if callable(set_status):
            try:
                set_status(text, auto_hide_ms=RESEARCH_NOTE_FEEDBACK_MILLISECONDS)
            except Exception:
                pass
        show_toast = getattr(self.overlay_manager, "show_research_note_toast", None)
        if callable(show_toast):
            try:
                show_toast(
                    text,
                    show_view=show_view,
                    timeout_ms=RESEARCH_NOTE_FEEDBACK_MILLISECONDS,
                )
                return
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
        self._show_research_note_feedback(feedback, show_view=True)
        self.logger.info(
            "research_note_saved created=%s has_resource=%s has_ai_content=%s",
            result.created,
            bool(result.note.resource_url or result.note.resource_title),
            bool(result.note.ai_content),
        )
        library = getattr(self, "_research_notes_window", None)
        if library is not None and library.isVisible():
            self._refresh_research_notes_library(library.search_query)
        settings = getattr(self, "_settings_window", None)
        refresh = getattr(settings, "refresh_runtime_status", None)
        if callable(refresh):
            refresh()
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

    def _ensure_research_notes_window(self) -> ResearchNotesLibraryWindow:
        window = self._research_notes_window
        if window is not None:
            window.apply_palette(self._research_palette())
            return window
        parent = getattr(self.overlay_manager, "window", None)
        window = ResearchNotesLibraryWindow(parent, palette=self._research_palette())
        window.search_requested.connect(self._refresh_research_notes_library)
        window.user_note_save_requested.connect(self._update_research_note_user_text)
        window.note_delete_requested.connect(self._delete_research_note)
        self._research_notes_window = window
        return window

    def _query_research_notes(self, query: str = "") -> tuple[ResearchNote, ...]:
        search = getattr(self.research_note_store, "search", None)
        if callable(search):
            try:
                return tuple(search(query, limit=100))
            except Exception as exc:
                self._log_exception("research_notes_search_failed", exc)
        try:
            notes = tuple(self.research_note_store.list_recent(limit=100))
        except Exception as exc:
            self._log_exception("research_notes_list_failed", exc)
            return ()
        needle = " ".join(str(query or "").casefold().split())
        if not needle:
            return notes
        return tuple(
            note
            for note in notes
            if needle
            in " ".join(
                (
                    note.resource_title,
                    note.section_heading,
                    note.source_text,
                    note.translated_text,
                    note.ai_content,
                    note.user_note,
                )
            ).casefold()
        )

    def _refresh_research_notes_library(self, query: str = "") -> None:
        window = self._research_notes_window
        if window is None:
            return
        window.set_notes(self._query_research_notes(query))

    def _open_research_notes_library(self) -> bool:
        window = self._ensure_research_notes_window()
        self._refresh_research_notes_library(window.search_query)
        window.show()
        window.raise_()
        window.activateWindow()
        self.logger.info("research_notes_library_opened count=%s", self.research_note_store.count())
        return True

    def _update_research_note_user_text(self, note_id: str, user_note: str) -> None:
        update = getattr(self.research_note_store, "update_user_note", None)
        if not callable(update):
            self._show_research_note_feedback(RESEARCH_NOTE_FAILED_TEXT)
            return
        try:
            saved = update(note_id, user_note)
        except Exception as exc:
            self._log_exception("research_note_user_text_update_failed", exc)
            saved = None
        if saved is None:
            self._show_research_note_feedback(RESEARCH_NOTE_FAILED_TEXT)
            return
        self._show_research_note_feedback(RESEARCH_NOTE_UPDATED_TEXT)
        window = self._research_notes_window
        self._refresh_research_notes_library(window.search_query if window is not None else "")

    def _delete_research_note(self, note_id: str) -> None:
        try:
            deleted = bool(self.research_note_store.delete(note_id))
        except Exception as exc:
            self._log_exception("research_note_delete_failed", exc)
            deleted = False
        self._show_research_note_feedback("研究笔记已删除" if deleted else "研究笔记删除失败")
        window = self._research_notes_window
        self._refresh_research_notes_library(window.search_query if window is not None else "")
        settings = getattr(self, "_settings_window", None)
        refresh = getattr(settings, "refresh_runtime_status", None)
        if callable(refresh):
            refresh()

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        if key == RESEARCH_NOTE_SAVE:
            self._save_current_research_note()
            return
        if key == RESEARCH_NOTES_LIBRARY:
            self._open_research_notes_library()
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
