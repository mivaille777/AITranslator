"""Research-memory actions layered on top of the Desktop Academic Agent UI."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QAction

from app.ai.desktop_agent_overlay import (
    DesktopAgentOverlayManager,
    DesktopAgentOverlayWindow,
)
from app.ai.research_quick_actions import (
    QUICK_ACTION_COMPACT_WIDTH,
    RESEARCH_NOTE_SAVE,
    ResearchNoteToast,
    SelectionQuickActionBar,
)
from app.overlay.context_menu import OVERLAY_THEMES, symbol_icon
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


RESEARCH_NOTES_LIBRARY = "research_notes_library"
RESEARCH_NOTES_RECENT = "research_notes_recent"

_RESEARCH_ACTION_SPECS = (
    (RESEARCH_NOTE_SAVE, "加入研究笔记", "记"),
    (RESEARCH_NOTES_LIBRARY, "研究笔记库", "库"),
    (RESEARCH_NOTES_RECENT, "最近研究笔记", "簿"),
)


class ResearchAgentOverlayWindow(DesktopAgentOverlayWindow):
    """Desktop Agent window with deterministic research-memory actions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._research_actions: dict[str, QAction] = {}
        self._selection_quick_actions: SelectionQuickActionBar | None = None
        self._research_note_toast: ResearchNoteToast | None = None
        super().__init__(*args, **kwargs)
        self._install_research_actions()
        self._install_selection_quick_actions()
        self._install_research_note_toast()

    @property
    def research_actions(self) -> dict[str, QAction]:
        return dict(self._research_actions)

    @property
    def selection_quick_actions(self) -> SelectionQuickActionBar | None:
        return self._selection_quick_actions

    @property
    def research_note_toast(self) -> ResearchNoteToast | None:
        return self._research_note_toast

    def _set_content(
        self,
        source_text: object | None,
        translated_text: object | None,
        source_language: object,
        target_language: object,
        *,
        animate: bool = False,
    ) -> None:
        super()._set_content(
            source_text,
            translated_text,
            source_language,
            target_language,
            animate=animate,
        )
        if hasattr(self, "_context_menu"):
            self._sync_context_menu_state()
        self._sync_selection_quick_actions()

    def show_translation(
        self,
        source_text: object | None,
        translated_text: object | None,
        source_language: object = "auto",
        target_language: object = "zh-CN",
    ) -> None:
        super().show_translation(
            source_text,
            translated_text,
            source_language,
            target_language,
        )
        self._sync_selection_quick_actions()
        self._resize_to_content(animate=False)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._sync_selection_quick_actions()

    def _install_research_actions(self) -> None:
        menu = self.context_menu.ai_menu
        menu.addSeparator()
        palette = OVERLAY_THEMES[self._theme_name]
        action_index = getattr(self.context_menu, "_actions", None)
        for key, label, glyph in _RESEARCH_ACTION_SPECS:
            action = QAction(label, menu)
            action.setObjectName(
                f"OverlayContext{key.title().replace('_', '')}Action"
            )
            action.setIcon(symbol_icon(glyph, palette["text"], size=18))
            action.triggered.connect(
                lambda _checked=False, action_key=key: (
                    self.context_menu.action_requested.emit(action_key, None)
                )
            )
            menu.addAction(action)
            self._research_actions[key] = action
            if isinstance(action_index, dict):
                action_index[key] = action
        self._apply_research_action_theme()
        self._sync_context_menu_state()

    def _install_selection_quick_actions(self) -> None:
        bar = SelectionQuickActionBar(self)
        bar.action_requested.connect(lambda key: self.context_action.emit(key, None))
        content_index = self._layout.indexOf(self._content_scroll)
        self._layout.insertWidget(max(0, content_index + 1), bar)
        self._selection_quick_actions = bar
        bar.apply_palette(OVERLAY_THEMES[self._theme_name])
        self._sync_selection_quick_actions()

    def _install_research_note_toast(self) -> None:
        toast = ResearchNoteToast(self)
        toast.view_requested.connect(
            lambda: self.context_action.emit(RESEARCH_NOTES_LIBRARY, None)
        )
        toast.dismissed.connect(lambda: self._resize_to_content(animate=False))
        quick = self._selection_quick_actions
        quick_index = self._layout.indexOf(quick) if quick is not None else -1
        self._layout.insertWidget(max(0, quick_index + 1), toast)
        self._research_note_toast = toast
        toast.apply_palette(OVERLAY_THEMES[self._theme_name])

    def show_research_note_toast(
        self,
        message: object,
        *,
        show_view: bool = True,
        timeout_ms: int = 2200,
    ) -> None:
        toast = self._research_note_toast
        if toast is None:
            return
        toast.show_message(message, show_view=show_view, timeout_ms=timeout_ms)
        self._resize_to_content(animate=False)

    def _sync_selection_quick_actions(self) -> None:
        bar = getattr(self, "_selection_quick_actions", None)
        if bar is None:
            return
        bar.set_compact(self.width() < QUICK_ACTION_COMPACT_WIDTH)
        has_source = bool(str(getattr(self, "_source_text", "") or "").strip())
        surface_available = bool(
            has_source
            and not bool(getattr(self, "_chat_open", False))
            and not bool(getattr(self, "_agent_translation_mode", False))
        )
        bar.set_source_available(surface_available)

    def _apply_research_action_theme(self) -> None:
        actions = getattr(self, "_research_actions", None)
        if not actions:
            return
        palette = OVERLAY_THEMES[self._theme_name]
        for key, _label, glyph in _RESEARCH_ACTION_SPECS:
            action = actions.get(key)
            if action is not None:
                action.setIcon(symbol_icon(glyph, palette["text"], size=18))

    def _apply_header_style(self, palette: dict[str, str]) -> None:
        """Keep interactive chrome opaque enough to read over white papers/PDFs."""

        super()._apply_header_style(palette)
        background = palette["menu_background"]
        border = palette["border"]
        hover = palette["hover"]
        text = palette["text"]
        muted = palette["muted_text"]
        accent = palette["accent"]

        header = getattr(self, "_header", None)
        if header is not None:
            header.setStyleSheet(
                f"""
                QWidget#OverlayHeader {{
                    background-color: {background};
                    border: 1px solid {border};
                    border-radius: 9px;
                }}
                """
            )

        # Parent classes historically derive button alpha from the translation
        # card's background opacity. Re-apply the final production controls
        # directly so a translucent body never makes the toolbar disappear on
        # white PDFs or light webpages.
        for attribute in ("_ai_button", "_chat_button", "_copy_button", "_menu_button"):
            button = getattr(self, attribute, None)
            if button is None:
                continue
            button.setStyleSheet(
                f"""
                QToolButton {{
                    color: {text};
                    background-color: {background};
                    border: 1px solid {border};
                    border-radius: 7px;
                    padding: 2px 6px;
                }}
                QToolButton::menu-indicator {{ image: none; width: 0px; }}
                QToolButton:hover:enabled {{
                    color: {text};
                    background-color: {hover};
                    border-color: {accent};
                }}
                QToolButton:disabled {{
                    color: {muted};
                    background-color: {background};
                    border-color: {border};
                }}
                """
            )

    def _apply_theme(self, theme: str) -> None:
        super()._apply_theme(theme)
        self._apply_research_action_theme()
        palette = OVERLAY_THEMES[self._theme_name]
        bar = getattr(self, "_selection_quick_actions", None)
        if bar is not None:
            bar.apply_palette(palette)
        toast = getattr(self, "_research_note_toast", None)
        if toast is not None:
            toast.apply_palette(palette)

    def _sync_context_menu_state(self) -> None:
        super()._sync_context_menu_state()
        actions = getattr(self, "_research_actions", None)
        if not actions:
            return

        has_source = bool(str(getattr(self, "_source_text", "") or "").strip())
        for action in getattr(self, "_reading_actions", {}).values():
            action.setEnabled(has_source)

        save_action = actions.get(RESEARCH_NOTE_SAVE)
        if save_action is not None:
            save_action.setEnabled(has_source)
        for key in (RESEARCH_NOTES_LIBRARY, RESEARCH_NOTES_RECENT):
            action = actions.get(key)
            if action is not None:
                action.setEnabled(True)

        self.context_menu.ai_menu.setEnabled(True)
        self._sync_selection_quick_actions()

    def open_chat(self, **kwargs: Any) -> None:
        super().open_chat(**kwargs)
        self._sync_selection_quick_actions()

    def close_chat(self) -> None:
        super().close_chat()
        self._sync_selection_quick_actions()

    def enter_agent_translation_mode(self, assistant_message: object = "") -> None:
        super().enter_agent_translation_mode(assistant_message)
        self._sync_selection_quick_actions()

    def leave_agent_translation_mode(self) -> None:
        super().leave_agent_translation_mode()
        self._sync_selection_quick_actions()


class ResearchAgentOverlayManager(DesktopAgentOverlayManager):
    """Manager boundary for the research-memory enabled Desktop Agent."""

    def __init__(
        self,
        window: OverlayWindow | None = None,
        *,
        position_manager: PositionManager | None = None,
        config_manager: Any | None = None,
    ) -> None:
        if window is None:
            resolved_position_manager = position_manager or PositionManager(
                config_manager=config_manager
            )
            window = ResearchAgentOverlayWindow(
                position_manager=resolved_position_manager,
                config_manager=config_manager,
            )
        super().__init__(
            window=window,
            position_manager=position_manager,
            config_manager=config_manager,
        )

    def show_research_note_toast(
        self,
        message: object,
        *,
        show_view: bool = True,
        timeout_ms: int = 2200,
    ) -> None:
        callback = getattr(self.window, "show_research_note_toast", None)
        if callable(callback):
            callback(message, show_view=show_view, timeout_ms=timeout_ms)


__all__ = [
    "RESEARCH_NOTE_SAVE",
    "RESEARCH_NOTES_LIBRARY",
    "RESEARCH_NOTES_RECENT",
    "ResearchAgentOverlayManager",
    "ResearchAgentOverlayWindow",
]
