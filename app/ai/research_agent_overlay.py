"""Research-memory actions layered on top of the Desktop Academic Agent UI."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QAction

from app.ai.desktop_agent_overlay import (
    DesktopAgentOverlayManager,
    DesktopAgentOverlayWindow,
)
from app.ai.research_quick_actions import (
    RESEARCH_NOTE_SAVE,
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
        super().__init__(*args, **kwargs)
        self._install_research_actions()
        self._install_selection_quick_actions()

    @property
    def research_actions(self) -> dict[str, QAction]:
        return dict(self._research_actions)

    @property
    def selection_quick_actions(self) -> SelectionQuickActionBar | None:
        return self._selection_quick_actions

    def _set_content(
        self,
        source_text: object | None,
        translated_text: object | None,
        source_language: object,
        target_language: object,
        *,
        animate: bool = False,
    ) -> None:
        """Keep source-bound research actions aligned with displayed content."""

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
        # The base content measurement runs before the quick row becomes
        # visible. Reflow once after source availability is known so the row is
        # never clipped below the translation card.
        self._sync_selection_quick_actions()
        self._resize_to_content(animate=False)

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
        bar.action_requested.connect(
            lambda key: self.context_action.emit(key, None)
        )
        content_index = self._layout.indexOf(self._content_scroll)
        self._layout.insertWidget(max(0, content_index + 1), bar)
        self._selection_quick_actions = bar
        bar.apply_palette(OVERLAY_THEMES[self._theme_name])
        self._sync_selection_quick_actions()

    def _sync_selection_quick_actions(self) -> None:
        bar = getattr(self, "_selection_quick_actions", None)
        if bar is None:
            return
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

    def _apply_theme(self, theme: str) -> None:
        super()._apply_theme(theme)
        self._apply_research_action_theme()
        bar = getattr(self, "_selection_quick_actions", None)
        if bar is not None:
            bar.apply_palette(OVERLAY_THEMES[self._theme_name])

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

        # Keep the submenu available even without a current selection because
        # the library and recent-note views are source-independent.
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


__all__ = [
    "RESEARCH_NOTE_SAVE",
    "RESEARCH_NOTES_LIBRARY",
    "RESEARCH_NOTES_RECENT",
    "ResearchAgentOverlayManager",
    "ResearchAgentOverlayWindow",
]
