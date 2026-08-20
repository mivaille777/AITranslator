"""Production Academic Companion overlay without legacy fixed size caps."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QSizePolicy

from app.ai.research_agent_overlay import ResearchAgentOverlayManager, ResearchAgentOverlayWindow
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


QT_WIDGET_SIZE_MAX = 16_777_215


class AdaptiveResearchAgentOverlayWindow(ResearchAgentOverlayWindow):
    """Use screen geometry as the practical resize boundary, not 900x520 caps."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._translation_surface_size = QSize()
        self._translation_width_locked_before_chat = False
        self._translation_height_locked_before_chat = False
        self._translation_font_size_before_chat = 0
        super().__init__(*args, **kwargs)
        self._remove_legacy_size_caps()
        self._stabilize_outer_header()
        self._apply_configured_chat_font_size()
        self._apply_responsive_minimum_width()
        self._resize_to_content(animate=False)
        self._translation_surface_size = QSize(self.size())
        self._translation_font_size_before_chat = int(self._font_size)

    def _stabilize_outer_header(self) -> None:
        """Never let extra window height stretch the toolbar vertically."""

        header = getattr(self, "_header", None)
        if header is None:
            return
        header.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        header.updateGeometry()

    def _set_content_maximum_width(self) -> None:
        """Let the layout/window geometry constrain text instead of a legacy cap."""

        label = getattr(self, "_label", None)
        if label is not None:
            label.setMaximumWidth(QT_WIDGET_SIZE_MAX)
        source = getattr(self, "_source_label", None)
        if source is not None:
            source.setMaximumWidth(QT_WIDGET_SIZE_MAX)

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

    def _restore_translation_typography(self) -> None:
        """Restore translation fonts after leaving the independently-sized Chat surface."""

        size = int(self._translation_font_size_before_chat or self._font_size)
        self._font_size = size
        label = getattr(self, "_label", None)
        if label is not None:
            label.setFont(QFont(self._font_family, size))
        source = getattr(self, "_source_label", None)
        if source is not None:
            source.setFont(
                QFont(
                    self._font_family,
                    max(8, min(18, round(size * 0.55))),
                )
            )
        self._apply_theme(self._theme_name)

    def open_chat(self, **kwargs: Any) -> None:
        """Enter Chat without letting its geometry or typography mutate Translation."""

        if not getattr(self, "_chat_open", False):
            self._translation_surface_size = QSize(self.size())
            self._translation_width_locked_before_chat = bool(
                getattr(self, "_manual_width_locked", False)
            )
            self._translation_height_locked_before_chat = bool(
                getattr(self, "_manual_height_locked", False)
            )
            self._translation_font_size_before_chat = int(self._font_size)

            # Chat gets its own adaptive geometry. Manual resize ownership from
            # the Translation surface must not prevent the transcript from
            # fitting its contents.
            self._manual_width_locked = False
            self._manual_height_locked = False
            self._manual_size_locked = False

        super().open_chat(**kwargs)
        self._stabilize_outer_header()
        self._apply_configured_chat_font_size()

    def close_chat(self) -> None:
        """Return to a clean Translation surface rather than retaining Chat geometry."""

        if not getattr(self, "_chat_open", False):
            return

        # A resize performed while Chat was open is Chat-local. Clear its lock
        # before the base close transition, then restore the Translation
        # surface ownership recorded before entering Chat.
        self._manual_width_locked = False
        self._manual_height_locked = False
        self._manual_size_locked = False
        super().close_chat()

        self._restore_translation_typography()
        self._manual_width_locked = self._translation_width_locked_before_chat
        self._manual_height_locked = self._translation_height_locked_before_chat
        self._manual_size_locked = bool(
            self._manual_width_locked or self._manual_height_locked
        )

        saved = QSize(self._translation_surface_size)
        if saved.isValid():
            width = saved.width() if self._manual_width_locked else self.width()
            height = saved.height() if self._manual_height_locked else self.height()
            self.resize(max(1, width), max(1, height))

        editor = getattr(self, "_source_editor", None)
        if editor is not None:
            editor.adjust_editor_height()

        self._stabilize_outer_header()
        if self._manual_height_locked:
            self._update_scroll_area_limits()
            self.updateGeometry()
        else:
            self._resize_to_content(animate=False)
        self._apply_responsive_minimum_width()

    def _scale_fonts_for_manual_size(self, new_size: QSize) -> None:
        """Resize Translation typography only while the Translation surface owns the resize."""

        if getattr(self, "_chat_open", False):
            # Chat has an explicit A-size control; resizing the Chat window must
            # neither change nor persist the Translation font size.
            self._apply_configured_chat_font_size()
            return

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
