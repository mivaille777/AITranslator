"""Final production controller for adaptive Reading Context synchronization."""

from __future__ import annotations

import ctypes
import os
from typing import Any

from PySide6.QtCore import QTimer

from app.ai.adaptive_research_overlay import AdaptiveResearchAgentOverlayManager
from app.ai.chat import ChatContext, ReadingContext
from app.ai.research_agent_controller import ResearchAgentAppController
from app.infrastructure.settings import SettingsManager
from app.models.selection import SelectedText, SelectionContext
from app.selection.browser_bridge import BROWSER_PROCESS_NAMES
from app.selection.browser_page_bridge import BrowserPageSnapshot, BrowserReadingBridge
from app.selection.errors import SelectionError


BROWSER_PAGE_POLL_MILLISECONDS = 650
NATIVE_SELECTION_PAGE_MAX_AGE_SECONDS = 2.0
_BROWSER_TITLE_SUFFIXES = (
    " - Google Chrome",
    " — Google Chrome",
    " - Microsoft Edge",
    " — Microsoft Edge",
    " - Brave",
    " — Brave",
    " - Mozilla Firefox",
    " — Mozilla Firefox",
)


def _normalized_process(value: object) -> str:
    return str(value or "").replace("\\", "/").rsplit("/", 1)[-1].casefold()


def _window_title(hwnd: object) -> str:
    """Read only the frozen window title; never activate or manipulate it."""

    if os.name != "nt":
        return ""
    try:
        handle = int(hwnd or 0)
    except (TypeError, ValueError):
        return ""
    if handle <= 0:
        return ""
    try:
        user32 = ctypes.windll.user32
        length = int(user32.GetWindowTextLengthW(handle))
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        copied = int(user32.GetWindowTextW(handle, buffer, length + 1))
    except Exception:
        return ""
    if copied <= 0:
        return ""
    title = str(buffer.value or "").strip()
    for suffix in _BROWSER_TITLE_SUFFIXES:
        if title.endswith(suffix):
            title = title[: -len(suffix)].rstrip()
            break
    return title[:1024]


class AdaptiveResearchAgentAppController(ResearchAgentAppController):
    """Keep visible reading evidence synchronized without discarding chat history."""

    def __init__(
        self,
        *args: Any,
        browser_selection_bridge: BrowserReadingBridge | Any | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_config = kwargs.get("config_manager")
        if resolved_config is None:
            resolved_config = SettingsManager()
            kwargs["config_manager"] = resolved_config
        if kwargs.get("overlay_manager") is None:
            kwargs["overlay_manager"] = AdaptiveResearchAgentOverlayManager(
                config_manager=resolved_config,
            )
        bridge = browser_selection_bridge or BrowserReadingBridge(
            logger=kwargs.get("logger"),
        )
        super().__init__(
            *args,
            browser_selection_bridge=bridge,
            **kwargs,
        )
        self._observed_page_signature = ""
        self._page_context_timer = QTimer()
        self._page_context_timer.setInterval(BROWSER_PAGE_POLL_MILLISECONDS)
        self._page_context_timer.timeout.connect(self._poll_browser_page_context)

    def start(self, *, start_hotkey: bool = True) -> None:
        super().start(start_hotkey=start_hotkey)
        if start_hotkey:
            self._page_context_timer.start()

    def shutdown(self) -> None:
        timer = getattr(self, "_page_context_timer", None)
        if timer is not None:
            timer.stop()
        super().shutdown()

    @staticmethod
    def _page_signature(snapshot: object) -> str:
        url = str(getattr(snapshot, "url", "") or "").strip()
        title = str(getattr(snapshot, "title", "") or "").strip()
        return f"{url}\n{title}"

    def _latest_page_snapshot(
        self,
        *,
        max_age_seconds: float | None = None,
    ) -> BrowserPageSnapshot | None:
        reader = getattr(self.browser_selection_bridge, "latest_page_snapshot", None)
        if not callable(reader):
            return None
        try:
            if max_age_seconds is None:
                snapshot = reader()
            else:
                snapshot = reader(max_age_seconds=max_age_seconds)
        except SelectionError:
            return None
        except Exception as exc:
            self._log_exception("browser_page_context_read_failed", exc)
            return None
        return snapshot if isinstance(snapshot, BrowserPageSnapshot) else snapshot

    def _prime_observed_page_signature(self) -> None:
        snapshot = self._latest_page_snapshot()
        self._observed_page_signature = (
            self._page_signature(snapshot) if snapshot is not None else ""
        )

    def _reading_resource_signature(self) -> str:
        reading = getattr(self, "_active_reading_context", ReadingContext())
        return (
            f"{str(reading.resource_url or '').strip()}\n"
            f"{str(reading.resource_title or '').strip()}"
        )

    def _apply_page_snapshot(
        self,
        snapshot: object,
        *,
        force: bool = False,
    ) -> bool:
        signature = self._page_signature(snapshot)
        if not signature.strip():
            return False
        self._observed_page_signature = signature
        if not force and signature == self._reading_resource_signature():
            return False

        reading = ReadingContext(
            resource_url=str(getattr(snapshot, "url", "") or "").strip(),
            resource_title=str(getattr(snapshot, "title", "") or "").strip(),
            section_heading=str(getattr(snapshot, "heading", "") or "").strip(),
            source_kind="browser_page",
        )
        self._set_reading_context("", reading)
        self._sync_active_reading_context()
        self.logger.info(
            "reading_context_page_changed has_url=%s has_title=%s",
            bool(reading.resource_url),
            bool(reading.resource_title),
        )
        return True

    def _poll_browser_page_context(self) -> None:
        if self._shutdown or not self._is_ai_chat_open():
            return
        snapshot = self._latest_page_snapshot()
        if snapshot is None:
            return
        signature = self._page_signature(snapshot)
        if not signature or signature == self._observed_page_signature:
            return
        self._apply_page_snapshot(snapshot)

    def _restore_controller_reading_context(self, context: ChatContext) -> None:
        reading = (
            context.reading
            if isinstance(context.reading, ReadingContext)
            else ReadingContext()
        )
        self._active_reading_context = reading
        self._reading_context_source_text = str(context.source_text or "").strip()
        self._reading_context_translation_text = str(
            context.translated_text or ""
        ).strip()

    def _show_managed_conversation(self, conversation) -> None:
        """Conversation switching is itself a Reading Context transition."""

        self._restore_controller_reading_context(conversation.context)
        # Treat the currently visible browser page as already observed. It must
        # not immediately overwrite the context merely because a history item
        # was opened; a subsequent page change or selection will update it.
        self._prime_observed_page_signature()
        super()._show_managed_conversation(conversation)
        self._chat_overlay_call("set_chat_reading_context", conversation.context)

    def _current_reading_context(self) -> ChatContext:
        reading = getattr(self, "_active_reading_context", ReadingContext())
        source = str(getattr(self, "_reading_context_source_text", "") or "").strip()
        translated = str(
            getattr(self, "_reading_context_translation_text", "") or ""
        ).strip()
        if source or translated or reading.has_context:
            return ChatContext(
                source_text=source,
                translated_text=translated,
                reading=reading,
            )
        return super()._current_reading_context()

    def _capture_browser_context(self) -> None:
        """Refresh page-level context before opening Chat without erasing same-page selections."""

        snapshot = self._latest_page_snapshot()
        if snapshot is not None:
            signature = self._page_signature(snapshot)
            self._observed_page_signature = signature
            if signature != self._reading_resource_signature():
                self._apply_page_snapshot(snapshot)
            return

        try:
            result = self.desktop_tool_runtime.browser_tools.capture_foreground()
        except Exception as exc:
            self._log_exception("agent_browser_context_capture_failed", exc)
            return
        if not result.ok:
            return
        url = str(result.metadata.get("url", "") or "").strip()
        title = str(result.metadata.get("title", "") or "").strip()
        if not url and not title:
            return
        fallback = BrowserPageSnapshot(url=url, title=title)
        if self._page_signature(fallback) != self._reading_resource_signature():
            self._apply_page_snapshot(fallback)

    def _capture_automatic_selection(
        self,
        context: SelectionContext,
    ) -> SelectedText:
        """Enrich native browser/PDF selection with a fresh active page identity."""

        selected = super()._capture_automatic_selection(context)
        reading = getattr(self, "_active_reading_context", ReadingContext())
        process = _normalized_process(context.process_name)
        if process not in BROWSER_PROCESS_NAMES:
            return selected
        if reading.resource_url or reading.resource_title:
            self._prime_observed_page_signature()
            return selected

        # A native PDF fallback can run after a previous normal webpage. Only
        # trust a page ping if it is very recent; otherwise use the frozen HWND
        # title so stale metadata can never label the newly selected PDF.
        page = self._latest_page_snapshot(
            max_age_seconds=NATIVE_SELECTION_PAGE_MAX_AGE_SECONDS,
        )
        title = ""
        url = ""
        heading = ""
        if page is not None:
            url = str(getattr(page, "url", "") or "").strip()
            title = str(getattr(page, "title", "") or "").strip()
            heading = str(getattr(page, "heading", "") or "").strip()
        if not title:
            title = _window_title(context.foreground_hwnd)

        if url or title or heading:
            self._set_reading_context(
                selected.text,
                ReadingContext(
                    resource_url=url,
                    resource_title=title,
                    section_heading=heading,
                    source_kind=selected.provider,
                ),
            )
            self._prime_observed_page_signature()
        return selected


__all__ = [
    "AdaptiveResearchAgentAppController",
    "BROWSER_PAGE_POLL_MILLISECONDS",
    "NATIVE_SELECTION_PAGE_MAX_AGE_SECONDS",
]
