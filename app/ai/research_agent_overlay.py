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
        save_action = actions.get(RESEARCH_NOTE_SAVE)
        if save_action is not None:
            save_action.setEnabled(has_source)
        recent_action = actions.get(RESEARCH_NOTES_RECENT)
        if recent_action is not None:
            recent_action.setEnabled(True)

        # Stage 5 disables the whole AI menu when no source exists. Research
        # memory is also a navigation surface, so keep the menu reachable while
        # the source-bound AI actions themselves remain disabled.
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
