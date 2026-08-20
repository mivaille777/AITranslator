"""Production Academic Companion overlay without legacy fixed size caps."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QHBoxLayout, QMenu, QSizePolicy, QToolButton

from app.ai.research_agent_overlay import ResearchAgentOverlayManager, ResearchAgentOverlayWindow
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow
from app.ui.design_tokens import (
    CONTROL,
    ICON,
    LAYOUT,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
    legacy_overlay_palette,
)
from app.ui.icon_controls import (
    ICON_BUTTON_COMPACT,
    ICON_BUTTON_COMPOSER,
    ICON_BUTTON_TOOLBAR,
    apply_icon_button_palette,
    attach_menu_chevron,
    configure_icon_button,
)
from app.ui.svg_icons import svg_icon


QT_WIDGET_SIZE_MAX = 16_777_215


class AdaptiveResearchAgentOverlayWindow(ResearchAgentOverlayWindow):
    """Use screen geometry as the practical resize boundary, not 900x520 caps."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._translation_surface_size = QSize()
        self._translation_width_locked_before_chat = False
        self._translation_height_locked_before_chat = False
        self._translation_font_size_before_chat = 0
        self._chat_overflow_button: QToolButton | None = None
        self._chat_overflow_menu: QMenu | None = None
        self._chat_overflow_clear_action: QAction | None = None
        self._chat_overflow_delete_action: QAction | None = None
        super().__init__(*args, **kwargs)
        self._remove_legacy_size_caps()
        self._install_chat_overflow_menu()
        self._apply_design_metrics()
        self._stabilize_outer_header()
        self._apply_configured_chat_font_size()
        self._apply_design_metrics()
        self._apply_responsive_minimum_width()
        self._resize_to_content(animate=False)
        self._translation_surface_size = QSize(self.size())
        self._translation_font_size_before_chat = int(self._font_size)

    def _resolved_palette(self) -> dict[str, str]:
        panel = getattr(self, "_chat_panel", None)
        panel_palette = getattr(panel, "_palette", None) if panel is not None else None
        if isinstance(panel_palette, dict) and panel_palette:
            return dict(panel_palette)
        return legacy_overlay_palette(getattr(self, "_theme_name", "dark"))

    def _chat_header_layout(self) -> QHBoxLayout | None:
        panel = getattr(self, "_chat_panel", None)
        root = panel.layout() if panel is not None else None
        top_item = root.itemAt(0) if root is not None else None
        top = top_item.layout() if top_item is not None else None
        return top if isinstance(top, QHBoxLayout) else None

    def _install_chat_overflow_menu(self) -> None:
        """Collapse secondary Chat actions into one persistent More menu.

        The legacy font/clear/delete controls remain alive for compatibility and
        retain their existing signals/layout contracts, but no longer consume
        permanent header space on the production Academic Companion surface.
        """

        panel = getattr(self, "_chat_panel", None)
        top = self._chat_header_layout()
        if panel is None or top is None or self._chat_overflow_button is not None:
            return

        button = QToolButton(panel)
        button.setObjectName("AITransChatOverflowButton")
        button.setText("")
        button.setToolTip("更多对话操作")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        configure_icon_button(button, ICON_BUTTON_TOOLBAR)

        menu = QMenu(button)
        menu.setObjectName("AITransChatOverflowMenu")
        button.setMenu(menu)

        font_menu = getattr(panel, "font_menu", None)
        if isinstance(font_menu, QMenu):
            font_menu.setTitle("字体大小")
            menu.addMenu(font_menu)
            menu.addSeparator()

        clear_action = QAction("清空当前对话", menu)
        clear_action.setObjectName("AITransChatOverflowClearAction")
        clear_action.triggered.connect(panel.clear_requested.emit)
        menu.addAction(clear_action)

        delete_action = QAction("删除当前对话", menu)
        delete_action.setObjectName("AITransChatOverflowDeleteAction")
        delete_action.triggered.connect(panel._request_delete_current)
        menu.addAction(delete_action)

        # Keep the old controls available to callers/tests, but move their
        # responsibilities into the secondary menu for the visible product UI.
        for attribute in ("font_button", "clear_button", "delete_chat_button"):
            legacy = getattr(panel, attribute, None)
            if legacy is not None:
                legacy.hide()

        top.addWidget(button)
        menu.aboutToShow.connect(self._sync_chat_overflow_menu)
        self._chat_overflow_button = button
        self._chat_overflow_menu = menu
        self._chat_overflow_clear_action = clear_action
        self._chat_overflow_delete_action = delete_action
        self._sync_chat_overflow_menu()

    def _sync_chat_overflow_menu(self) -> None:
        """Refresh secondary-action state and theme immediately before use."""

        panel = getattr(self, "_chat_panel", None)
        button = self._chat_overflow_button
        menu = self._chat_overflow_menu
        if panel is None or button is None or menu is None:
            return

        palette = self._resolved_palette()
        text = palette.get("chrome_text", palette["text"])
        muted = palette.get("chrome_muted_text", palette["muted_text"])
        background = palette.get("chrome_background", palette["menu_background"])
        border = palette.get("chrome_border", palette["border"])
        hover = palette.get("chrome_hover", palette["hover"])

        button.setIcon(svg_icon("more", muted, size=ICON.md))
        apply_icon_button_palette(button, palette)

        font_menu = getattr(panel, "font_menu", None)
        if isinstance(font_menu, QMenu):
            font_menu.setTitle(f"字体大小 · {int(panel.display_font_size)} pt")
            font_menu.setIcon(svg_icon("font", text, size=ICON.sm))

        clear_action = self._chat_overflow_clear_action
        if clear_action is not None:
            clear_action.setIcon(svg_icon("close", text, size=ICON.sm))

        delete_action = self._chat_overflow_delete_action
        if delete_action is not None:
            delete_action.setIcon(svg_icon("delete", text, size=ICON.sm))
            delete_action.setEnabled(bool(getattr(panel, "active_conversation_id", "")))

        menu.setStyleSheet(
            f"""
            QMenu#AITransChatOverflowMenu {{
                background-color: {background};
                color: {text};
                border: 1px solid {border};
                border-radius: {RADIUS.md}px;
                padding: {RADIUS.sm}px;
            }}
            QMenu#AITransChatOverflowMenu::item {{
                padding: {SPACING.sm}px {SPACING.lg}px;
                border-radius: {RADIUS.sm}px;
            }}
            QMenu#AITransChatOverflowMenu::item:selected {{
                background-color: {hover};
            }}
            QMenu#AITransChatOverflowMenu::item:disabled {{
                color: {muted};
            }}
            QMenu#AITransChatOverflowMenu::separator {{
                height: 1px;
                background: {border};
                margin: {SPACING.xs}px {SPACING.sm}px;
            }}
            """
        )

    def _apply_chat_control_metrics(self) -> None:
        """Normalize production Chat controls without changing their behavior."""

        panel = getattr(self, "_chat_panel", None)
        if panel is None:
            return
        palette = self._resolved_palette()
        muted = palette.get("chrome_muted_text", palette["muted_text"])
        disabled = palette.get("text_muted", palette["muted_text"])

        # Header icon controls share one 36px hit target and an 18px glyph.
        for attribute in (
            "history_button",
            "new_chat_button",
            "delete_chat_button",
            "back_button",
        ):
            button = getattr(panel, attribute, None)
            if isinstance(button, QToolButton):
                configure_icon_button(button, ICON_BUTTON_TOOLBAR)
                apply_icon_button_palette(button, palette)

        # The floating follow-tail control keeps the same hit target but stays
        # circular so it reads as a viewport affordance rather than toolbar UI.
        jump = getattr(panel, "jump_to_bottom_button", None)
        if isinstance(jump, QToolButton):
            configure_icon_button(jump, ICON_BUTTON_TOOLBAR)
            apply_icon_button_palette(
                jump,
                palette,
                radius=ICON_BUTTON_TOOLBAR.button_size // 2,
            )

        # Composer actions need the 44px target used by the input/send row.
        undo = getattr(panel, "undo_selection_button", None)
        if isinstance(undo, QToolButton):
            configure_icon_button(undo, ICON_BUTTON_COMPOSER)
            apply_icon_button_palette(undo, palette)

        # Reading Context is intentionally denser than the main toolbar.
        expand = getattr(panel, "reading_context_expand", None)
        if isinstance(expand, QToolButton):
            configure_icon_button(expand, ICON_BUTTON_COMPACT)
            apply_icon_button_palette(expand, palette)

        # Text-menu buttons use one custom SVG chevron on the right. The
        # controller strips legacy `▾` suffixes and suppresses Qt's native one.
        for attribute in ("model_button", "font_button"):
            button = getattr(panel, attribute, None)
            if isinstance(button, QToolButton):
                button.setMinimumHeight(CONTROL.normal_height)
                button.setMaximumHeight(CONTROL.normal_height)
                attach_menu_chevron(
                    button,
                    color=muted,
                    disabled_color=disabled,
                )
                chevron = getattr(button, "_aitrans_menu_chevron", None)
                normalize = getattr(chevron, "normalize_text", None)
                if callable(normalize):
                    normalize()

        # Preserve the frozen Stage-7 layout budgets. Decorative SVG chevrons
        # must never make these text controls wider than their existing slots.
        model_button = getattr(panel, "model_button", None)
        if isinstance(model_button, QToolButton):
            model_button.setMinimumWidth(LAYOUT.chat_model_min_width)
            model_button.setMaximumWidth(LAYOUT.chat_model_max_width)
        font_button = getattr(panel, "font_button", None)
        if isinstance(font_button, QToolButton):
            font_button.setFixedWidth(CONTROL.large_height + SPACING.xxl)

        clear_button = getattr(panel, "clear_button", None)
        if isinstance(clear_button, QToolButton):
            clear_button.setMinimumHeight(CONTROL.normal_height)
            clear_button.setMaximumHeight(CONTROL.normal_height)

        # Secondary actions stay logically present but visually collapsed.
        for attribute in ("font_button", "clear_button", "delete_chat_button"):
            legacy = getattr(panel, attribute, None)
            if legacy is not None:
                legacy.hide()

        if self._chat_overflow_button is not None:
            configure_icon_button(self._chat_overflow_button, ICON_BUTTON_TOOLBAR)
            apply_icon_button_palette(self._chat_overflow_button, palette)
            self._sync_chat_overflow_menu()

    def _apply_design_metrics(self) -> None:
        """Apply shared spacing/control metrics to the production surface."""

        root = getattr(self, "_layout", None)
        if root is not None:
            root.setContentsMargins(
                LAYOUT.floating_margin,
                SPACING.sm,
                LAYOUT.floating_margin,
                LAYOUT.floating_margin,
            )
            root.setSpacing(SPACING.xs)

        header_layout = getattr(self, "_header_layout", None)
        if header_layout is not None:
            header_layout.setSpacing(SPACING.sm)

        content_layout = getattr(self, "_content_layout", None)
        if content_layout is not None:
            content_layout.setSpacing(SPACING.xs)

        for attribute in ("_ai_button", "_chat_button", "_language_button"):
            button = getattr(self, attribute, None)
            if button is not None:
                button.setMinimumHeight(CONTROL.normal_height)
                button.setMaximumHeight(CONTROL.normal_height)

        for attribute in ("_copy_button", "_menu_button"):
            button = getattr(self, attribute, None)
            if isinstance(button, QToolButton):
                configure_icon_button(button, ICON_BUTTON_TOOLBAR)

        self._apply_chat_control_metrics()

    def _apply_header_style(self, palette: dict[str, str]) -> None:
        """Add one shared hover/pressed contract to production icon chrome."""

        super()._apply_header_style(palette)
        for attribute in ("_copy_button", "_menu_button", "_ai_button", "_chat_button"):
            button = getattr(self, attribute, None)
            if not isinstance(button, QToolButton):
                continue
            if not button.text().strip():
                configure_icon_button(button, ICON_BUTTON_TOOLBAR)
                apply_icon_button_palette(button, palette)
        self._apply_chat_control_metrics()

    def _apply_theme(self, theme: str) -> None:
        super()._apply_theme(theme)
        self._apply_design_metrics()

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
                    self._font_family or TYPOGRAPHY.family,
                    max(8, min(TYPOGRAPHY.title, round(size * 0.55))),
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
        self._apply_configured_chat_font_size()
        self._apply_design_metrics()
        self._stabilize_outer_header()

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

        self._apply_design_metrics()
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
            self._apply_design_metrics()
            return

        super()._scale_fonts_for_manual_size(new_size)
        self._apply_configured_chat_font_size()
        self._apply_design_metrics()


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
