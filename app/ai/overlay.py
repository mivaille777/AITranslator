"""AI controls layered onto the existing translation Overlay."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QToolButton

from app.overlay.context_menu import OVERLAY_THEMES, symbol_icon
from app.overlay.manager import OverlayManager
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


class AIOverlayWindow(OverlayWindow):
    """Add a compact sparkle AI menu without duplicating Overlay rendering."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._ai_button = QToolButton(self._header)
        self._ai_button.setObjectName("OverlayAIButton")
        self._ai_button.setText("")
        self._ai_button.setToolTip("AI 翻译 / AI 润色")
        self._ai_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_button.setAutoRaise(True)
        self._ai_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._ai_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._ai_button.setIconSize(QSize(22, 22))
        self._ai_button.setFixedSize(38, 34)
        self._ai_button.setMenu(self.context_menu.ai_menu)

        copy_index = self._header_layout.indexOf(self._copy_button)
        self._header_layout.insertWidget(max(0, copy_index), self._ai_button)
        self._sync_ai_availability()
        self._apply_theme(self._theme_name)
        self._resize_to_content()

    @property
    def ai_button(self) -> QToolButton:
        """Return the compact sparkle button used by GUI tests and adapters."""

        return self._ai_button

    def _sync_ai_availability(self) -> None:
        """Keep the AI menu reachable and gate only text-dependent operations."""

        enabled = bool(str(getattr(self, "_source_text", "")).strip())
        context_menu = getattr(self, "_context_menu", None)
        set_ai_enabled = getattr(context_menu, "set_ai_enabled", None)
        if callable(set_ai_enabled):
            set_ai_enabled(enabled)

        # ``set_ai_enabled`` predates Overlay Chat and disables the whole AI
        # submenu. Re-enable the submenu itself so Chat remains reachable;
        # the two text actions retain their individual enabled state above.
        ai_menu = getattr(context_menu, "ai_menu", None)
        if ai_menu is not None:
            ai_menu.setEnabled(True)

        # The sparkle button is a menu entry point, not a text operation by
        # itself. Keeping it enabled fixes the state where AI 翻译/润色 never
        # became reachable after startup while still leaving those QAction
        # rows disabled until a real source text exists.
        button = getattr(self, "_ai_button", None)
        if button is not None:
            button.setEnabled(True)

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
        self._sync_ai_availability()

    def _sync_context_menu_state(self) -> None:
        super()._sync_context_menu_state()
        self._sync_ai_availability()

    def _apply_header_style(self, palette: dict[str, str]) -> None:
        super()._apply_header_style(palette)
        button = getattr(self, "_ai_button", None)
        if button is None:
            return
        button_background = self._rgba_with_opacity(
            palette["hover"],
            self._background_opacity * 0.34 * self._header_emphasis,
        )
        button_border = self._rgba_with_opacity(
            palette["border"],
            self._background_opacity * 0.78 * self._header_emphasis,
        )
        button_hover_background = self._rgba_with_opacity(
            palette["hover"],
            min(1.0, self._background_opacity * 0.92),
        )
        muted = self._rgba_with_opacity(
            palette["muted_text"],
            self._header_emphasis,
        )
        button.setStyleSheet(
            f"""
            QToolButton#OverlayAIButton {{
                background-color: {button_background};
                border: 1px solid {button_border};
                border-radius: 6px;
                padding: 2px 6px;
            }}
            QToolButton#OverlayAIButton::menu-indicator {{
                image: none;
                width: 0px;
            }}
            QToolButton#OverlayAIButton:hover {{
                background-color: {button_hover_background};
                border: 1px solid {palette['accent']};
            }}
            QToolButton#OverlayAIButton:disabled {{
                color: {muted};
                background-color: {button_background};
                border: 1px solid {button_border};
            }}
            """
        )

    def _apply_theme(self, theme: str) -> None:
        super()._apply_theme(theme)
        button = getattr(self, "_ai_button", None)
        if button is None:
            return
        palette = OVERLAY_THEMES[self._theme_name]
        button.setIcon(symbol_icon("✦", palette["accent"], size=22))


class AIOverlayManager(OverlayManager):
    """Default Overlay manager that constructs :class:`AIOverlayWindow`."""

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
            window = AIOverlayWindow(
                position_manager=resolved_position_manager,
                config_manager=config_manager,
            )
        super().__init__(window=window)


__all__ = ["AIOverlayManager", "AIOverlayWindow"]
