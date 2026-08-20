"""Desktop Agent presentation: interactive Chat and a collapsible crab mini window."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.ai.agent_workspace_overlay import AgentWorkspaceOverlayManager, AgentWorkspaceOverlayWindow
from app.models.reading_actions import READING_ACTION_SPECS
from app.overlay.context_menu import OVERLAY_THEMES, symbol_icon
from app.overlay.positioning import PositionManager
from app.overlay.window import OverlayWindow


AGENT_CRAB_SIZE = 56


class AgentCrabWindow(QWidget):
    """Tiny original line-art crab used as the persistent Desktop Agent handle.

    The mini surface intentionally consumes the same palette dictionary as the
    full Overlay. This keeps dark, soft and contrast themes visually coherent
    instead of giving the collapsed Agent its own unrelated hard-coded colors.
    """

    restore_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setObjectName("DesktopAgentCrab")
        self.setFixedSize(AGENT_CRAB_SIZE, AGENT_CRAB_SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # The crab must not steal focus from Chrome/Edge; this lets the
        # Controller snapshot the page that was active immediately before the
        # user re-opens the Agent.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("AI Agent · 双击打开对话；拖动移动")
        self._dragging = False
        self._drag_offset = QPoint()
        self._hovered = False
        self.setMouseTracking(True)

        self._panel_color = QColor("#1E293B")
        self._hover_panel_color = QColor("#334155")
        self._border_color = QColor("#334155")
        self._line_color = QColor("#CBD5E1")
        self._accent_color = QColor("#60A5FA")

    @staticmethod
    def _palette_color(palette: dict[str, str], key: str, fallback: str) -> QColor:
        color = QColor(str(palette.get(key, fallback)))
        return color if color.isValid() else QColor(fallback)

    def set_theme_palette(self, palette: dict[str, str]) -> None:
        """Apply one existing Overlay palette to the collapsed Agent surface."""

        self._panel_color = self._palette_color(palette, "menu_background", "#1E293B")
        self._hover_panel_color = self._palette_color(palette, "hover", "#334155")
        self._border_color = self._palette_color(palette, "border", "#334155")
        self._line_color = self._palette_color(palette, "muted_text", "#CBD5E1")
        self._accent_color = self._palette_color(palette, "accent", "#60A5FA")
        self.update()

    @property
    def theme_colors(self) -> dict[str, str]:
        """Expose the resolved palette for GUI regression tests."""

        return {
            "panel": self._panel_color.name().upper(),
            "hover": self._hover_panel_color.name().upper(),
            "border": self._border_color.name().upper(),
            "line": self._line_color.name().upper(),
            "accent": self._accent_color.name().upper(),
        }

    def enterEvent(self, event) -> None:  # noqa: N802
        del event
        self._hovered = True
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        del event
        self._hovered = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.restore_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        panel = QColor(self._hover_panel_color if self._hovered else self._panel_color)
        painter.setPen(QPen(self._border_color, 1.2))
        painter.setBrush(panel)
        painter.drawRoundedRect(QRectF(2.5, 2.5, 51, 51), 15, 15)

        line = QColor(self._accent_color if self._hovered else self._line_color)
        pen = QPen(
            line,
            2.0,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(16, 20, 24, 19), 0, 180 * 16)
        painter.drawLine(18, 30, 15, 34)
        painter.drawLine(38, 30, 41, 34)
        painter.drawLine(19, 35, 15, 39)
        painter.drawLine(24, 37, 21, 42)
        painter.drawLine(32, 37, 35, 42)
        painter.drawLine(37, 35, 41, 39)
        painter.drawArc(QRectF(8, 24, 10, 10), 70 * 16, 220 * 16)
        painter.drawArc(QRectF(38, 24, 10, 10), -110 * 16, 220 * 16)
        painter.drawLine(23, 20, 23, 16)
        painter.drawLine(33, 20, 33, 16)
        painter.setBrush(line)
        painter.drawEllipse(QRectF(21.5, 14.5, 3, 3))
        painter.drawEllipse(QRectF(31.5, 14.5, 3, 3))
        painter.end()


class DesktopAgentOverlayWindow(AgentWorkspaceOverlayWindow):
    """Agent Overlay that makes Chat always interactive and supports mini mode."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._collapsed_to_crab = False
        self._interactive_mode_suspended_lock = False
        super().__init__(*args, **kwargs)
        self._reading_actions: dict[str, QAction] = {}
        self._install_reading_actions()
        self._agent_crab = AgentCrabWindow()
        self._agent_crab.set_theme_palette(OVERLAY_THEMES[self._theme_name])
        self._agent_crab.restore_requested.connect(self.restore_from_agent_crab)

    @property
    def collapsed_to_crab(self) -> bool:
        return self._collapsed_to_crab

    @property
    def agent_crab(self) -> AgentCrabWindow:
        return self._agent_crab

    @property
    def reading_actions(self) -> dict[str, QAction]:
        """Return the Academic Companion quick actions installed in the AI menu."""

        return dict(self._reading_actions)

    def _install_reading_actions(self) -> None:
        """Add Stage-5 reading actions without coupling the base Overlay to AI."""

        menu = self.context_menu.ai_menu
        menu.addSeparator()
        palette = OVERLAY_THEMES[self._theme_name]
        action_index = getattr(self.context_menu, "_actions", None)
        for spec in READING_ACTION_SPECS:
            action = QAction(spec.label, menu)
            action.setObjectName(
                f"OverlayContext{spec.key.title().replace('_', '')}Action"
            )
            action.setIcon(symbol_icon(spec.symbol, palette["text"], size=18))
            action.triggered.connect(
                lambda _checked=False, action_key=spec.key: (
                    self.context_menu.action_requested.emit(action_key, None)
                )
            )
            menu.addAction(action)
            self._reading_actions[spec.key] = action
            if isinstance(action_index, dict):
                action_index[spec.key] = action
        self._apply_reading_action_theme()
        self._sync_context_menu_state()

    def _apply_reading_action_theme(self) -> None:
        actions = getattr(self, "_reading_actions", None)
        if not actions:
            return
        palette = OVERLAY_THEMES[self._theme_name]
        for spec in READING_ACTION_SPECS:
            action = actions.get(spec.key)
            if action is not None:
                action.setIcon(symbol_icon(spec.symbol, palette["text"], size=18))

    def _apply_theme(self, theme: str) -> None:
        super()._apply_theme(theme)
        self._apply_reading_action_theme()
        crab = getattr(self, "_agent_crab", None)
        if crab is not None:
            crab.set_theme_palette(OVERLAY_THEMES[self._theme_name])

    def _sync_context_menu_state(self) -> None:
        """Disable all AI/reading actions when no selected source text exists."""

        super()._sync_context_menu_state()
        context_menu = getattr(self, "_context_menu", None)
        if context_menu is not None:
            context_menu.set_ai_enabled(bool(str(self._source_text or "").strip()))

    def _enter_interactive_window_mode(self) -> None:
        if self.is_locked:
            self._interactive_mode_suspended_lock = True
            self.unlock_overlay()
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        panel = getattr(self, "_chat_panel", None)
        if panel is not None:
            panel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            for child in panel.findChildren(QWidget):
                child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def _leave_interactive_window_mode_if_possible(self) -> None:
        if self._chat_open or self._agent_translation_mode:
            return
        if self._interactive_mode_suspended_lock:
            self._interactive_mode_suspended_lock = False
            self.lock_overlay()

    def open_chat(self, **kwargs: Any) -> None:
        self._collapsed_to_crab = False
        self._agent_crab.hide()
        self._enter_interactive_window_mode()
        super().open_chat(**kwargs)
        self.activateWindow()
        self.raise_()

    def close_chat(self) -> None:
        super().close_chat()
        self._leave_interactive_window_mode_if_possible()

    def enter_agent_translation_mode(self, assistant_message: object = "") -> None:
        self._enter_interactive_window_mode()
        super().enter_agent_translation_mode(assistant_message)

    def leave_agent_translation_mode(self) -> None:
        super().leave_agent_translation_mode()
        self._leave_interactive_window_mode_if_possible()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        handle = getattr(self, "_drag_handle", None)
        if handle is not None and watched is handle and event.type() == QEvent.Type.MouseButtonDblClick:
            if event.button() == Qt.MouseButton.LeftButton:
                self.collapse_to_agent_crab()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def collapse_to_agent_crab(self) -> None:
        """Hide only presentation; conversations and running workers keep living."""

        if self._collapsed_to_crab:
            return
        self._stop_resize_animation()
        self._collapsed_to_crab = True
        geometry = self.frameGeometry()
        crab_x = geometry.x() + max(0, (geometry.width() - AGENT_CRAB_SIZE) // 2)
        crab_y = geometry.y() + 6
        self.hide()
        self._agent_crab.move(crab_x, crab_y)
        self._agent_crab.show()
        self._agent_crab.raise_()

    def restore_from_agent_crab(self) -> None:
        if not self._collapsed_to_crab:
            return
        # Synchronous signal: the Controller snapshots Chrome/Edge while the
        # no-activate crab is still the only Agent surface on screen.
        self.context_action.emit("agent_capture_browser_context", None)
        self._collapsed_to_crab = False
        self._agent_crab.hide()
        if self._chat_open:
            self._enter_interactive_window_mode()
            super().show_overlay()
            self.activateWindow()
            self.raise_()
            return
        self.context_action.emit("ai_chat", None)

    def show_overlay(self) -> None:
        if self._collapsed_to_crab:
            return
        super().show_overlay()

    def hide_overlay(self) -> None:
        self._collapsed_to_crab = False
        self._agent_crab.hide()
        super().hide_overlay()


class DesktopAgentOverlayManager(AgentWorkspaceOverlayManager):
    def __init__(
        self,
        window: OverlayWindow | None = None,
        *,
        position_manager: PositionManager | None = None,
        config_manager: Any | None = None,
    ) -> None:
        if window is None:
            resolved_position_manager = position_manager or PositionManager(config_manager=config_manager)
            window = DesktopAgentOverlayWindow(
                position_manager=resolved_position_manager,
                config_manager=config_manager,
            )
        super().__init__(window=window)

    def collapse_to_agent_crab(self) -> None:
        callback = getattr(self.window, "collapse_to_agent_crab", None)
        if callable(callback):
            callback()

    def restore_from_agent_crab(self) -> None:
        callback = getattr(self.window, "restore_from_agent_crab", None)
        if callable(callback):
            callback()


__all__ = [
    "AGENT_CRAB_SIZE",
    "AgentCrabWindow",
    "DesktopAgentOverlayManager",
    "DesktopAgentOverlayWindow",
]
