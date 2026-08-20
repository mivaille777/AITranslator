"""Production Academic Companion overlay without legacy fixed size caps."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize

from app.ai.research_agent_overlay import ResearchAgentOverlayManager, ResearchAgentOverlayWindow
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


QT_WIDGET_SIZE_MAX = 16_777_215


class AdaptiveResearchAgentOverlayWindow(ResearchAgentOverlayWindow):
    """Use screen geometry as the practical resize boundary, not 900x520 caps."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._remove_legacy_size_caps()
        self._apply_configured_chat_font_size()
        self._apply_responsive_minimum_width()
        self._resize_to_content(animate=False)

    def _remove_legacy_size_caps(self) -> None:
        """Replace configured legacy maxima with Qt's effectively-unbounded limit."""

        self._max_width = QT_WIDGET_SIZE_MAX
        self._max_height = QT_WIDGET_SIZE_MAX
        self.setMaximumSize(QT_WIDGET_SIZE_MAX, QT_WIDGET_SIZE_MAX)

        for widget in (
            getattr(self, "_label", None),
            getattr(self, "_source_label", None),
            getattr(self, "_content", None),
            getattr(self, "_content_scroll", None),
        ):
            if widget is None:
                continue
            widget.setMaximumWidth(QT_WIDGET_SIZE_MAX)
            widget.setMaximumHeight(QT_WIDGET_SIZE_MAX)

        self._set_content_maximum_width()

    def _scale_fonts_for_manual_size(self, new_size: QSize) -> None:
        """Resize translation typography without overriding the Chat font choice."""

        super()._scale_fonts_for_manual_size(new_size)
        self._apply_configured_chat_font_size()


class AdaptiveResearchAgentOverlayManager(ResearchAgentOverlayManager):
    """Construct the unbounded production Academic Companion overlay."""

    def __init__(
        self,
        window: OverlayWindow | None = None,
        *,
        position_manager: PositionManager | None = None,
        config_manager: Any | None = None,
    ) -> None:
        if window is None:
            resolved_position_manager = position_manager or PositionManager(
                config_manager=config_manager,
            )
            window = AdaptiveResearchAgentOverlayWindow(
                position_manager=resolved_position_manager,
                config_manager=config_manager,
            )
        super().__init__(
            window=window,
            position_manager=position_manager,
            config_manager=config_manager,
        )


__all__ = [
    "AdaptiveResearchAgentOverlayManager",
    "AdaptiveResearchAgentOverlayWindow",
    "QT_WIDGET_SIZE_MAX",
]
