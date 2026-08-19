"""Research-memory actions layered on top of the Desktop Academic Agent UI."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QAction

from app.ai.desktop_agent_overlay import (
    DesktopAgentOverlayManager,
    DesktopAgentOverlayWindow,
)
from app.overlay.context_menu import OVERLAY_THEMES, symbol_icon
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


RESEARCH_NOTE_SAVE = "research_note_save"
RESEARCH_NOTES_RECENT = "research_notes_recent"

_RESEARCH_ACTION_SPECS = (
    (RESEARCH_NOTE_SAVE, "加入研究笔记", "记"),
    (RESEARCH_NOTES_RECENT, "最近研究笔记", "簿"),
)


class ResearchAgentOverlayWindow(DesktopAgentOverlayWindow):
    """Desktop Agent window with deterministic research-memory actions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._research_actions: dict[str, QAction] = {}
        super().__init__(*args, **kwargs)
        self._install_research_actions()

    @property
    def research_actions(self) -> dict[str, QAction]:
        return dict(self._research_actions)

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
        # OverlayWindow changes source/translation state through _set_content,
        # but its generic menu has no knowledge of Stage-6 research actions.
        # Refresh here so a newly displayed selection immediately enables
        # Save Note, while replacing it with source-less text disables the
        # action again.  The guards in _sync_context_menu_state keep this safe
        # during base-class construction before reading actions are installed.
        if hasattr(self, "_context_menu"):
            self._sync_context_menu_state()

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

    def _sync_context_menu_state(self) -> None:
        super()._sync_context_menu_state()
        actions = getattr(self, "_research_actions", None)
        if not actions:
            return

        has_source = bool(str(getattr(self, "_source_text", "") or "").strip())

        # Stage 5 could rely on disabling the complete AI submenu when no
        # source existed. Stage 6 deliberately keeps that submenu reachable so
        # users can open recent notes. Therefore every source-bound action must
        # now carry its own enabled state instead of inheriting the menu state.
        for action in getattr(self, "_reading_actions", {}).values():
            action.setEnabled(has_source)

        save_action = actions.get(RESEARCH_NOTE_SAVE)
        if save_action is not None:
            save_action.setEnabled(has_source)
        recent_action = actions.get(RESEARCH_NOTES_RECENT)
        if recent_action is not None:
            recent_action.setEnabled(True)

        # Base set_ai_enabled() already keeps AI translate/polish disabled when
        # source text is absent. Re-enable only the submenu container so the
        # source-independent Recent Notes action remains reachable.
        self.context_menu.ai_menu.setEnabled(True)


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
    "RESEARCH_NOTES_RECENT",
    "ResearchAgentOverlayManager",
    "ResearchAgentOverlayWindow",
]
