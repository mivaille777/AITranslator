"""Production controller variant with a compact scrollable settings dialog."""

from __future__ import annotations

from app.ai.controller import AIAppController
from app.ui.compact_settings import (
    apply_compact_settings_layout,
    ensure_settings_widget_visible,
)


class CompactAIAppController(AIAppController):
    """Keep the settings dialog bounded while preserving existing behavior."""

    def _show_settings(self) -> None:
        super()._show_settings()
        settings_window = self._settings_window
        if settings_window is None:
            return
        self._safe_call(
            "compact_settings_layout_failed",
            apply_compact_settings_layout,
            settings_window,
        )

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        super()._on_overlay_context_action(key, value)
        if key != "ai_settings":
            return
        settings_window = self._settings_window
        ai_group = getattr(settings_window, "ai_group", None) if settings_window else None
        if settings_window is not None and ai_group is not None:
            self._safe_call(
                "ai_settings_scroll_failed",
                ensure_settings_widget_visible,
                settings_window,
                ai_group,
            )


__all__ = ["CompactAIAppController"]
