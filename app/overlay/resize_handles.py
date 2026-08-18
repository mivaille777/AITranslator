"""Easy-to-hit edge/corner resize affordances for the frameless Overlay."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.overlay.context_menu import OVERLAY_THEMES


# Qt coordinates are device-independent pixels. A 12 px inner edge target is
# deliberately wider than the old 7 px strip and is much easier to acquire on
# high-DPI displays without stealing meaningful space from the Overlay body.
RESIZE_EDGE_THICKNESS = 12
RESIZE_CORNER_SIZE = 24
RESIZE_INDICATOR_LENGTH = 14
RESIZE_INDICATOR_WIDTH = 2
RESIZE_EDGES = (
    "left",
    "right",
    "top",
    "bottom",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
)

_CURSOR_BY_EDGE = {
    "left": Qt.CursorShape.SizeHorCursor,
    "right": Qt.CursorShape.SizeHorCursor,
    "top": Qt.CursorShape.SizeVerCursor,
    "bottom": Qt.CursorShape.SizeVerCursor,
    "top_left": Qt.CursorShape.SizeFDiagCursor,
    "bottom_right": Qt.CursorShape.SizeFDiagCursor,
    "top_right": Qt.CursorShape.SizeBDiagCursor,
    "bottom_left": Qt.CursorShape.SizeBDiagCursor,
}


class OverlayResizeHandle(QWidget):
    """Large transparent resize hit target with subtle hover confirmation."""

    def __init__(self, edge: str, parent=None) -> None:
        if edge not in RESIZE_EDGES:
            raise ValueError(f"Unsupported resize edge: {edge}")
        super().__init__(parent)
        self.edge = edge
        self._hovered = False
        self._normal_color = ""
        self._accent_override = ""
        self.setObjectName(f"OverlayResizeHandle{edge.title().replace('_', '')}")
        self.setCursor(_CURSOR_BY_EDGE[edge])
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation, True)
        self.setToolTip("拖动调整悬浮窗大小")
        self.setStyleSheet("background: transparent; border: none;")

    @property
    def hovered(self) -> bool:
        return self._hovered

    def set_theme_colors(self, normal: str, accent: str) -> None:
        """Accept Overlay palette updates without adding visible idle chrome."""

        self._normal_color = str(normal or "")
        self._accent_override = str(accent or "")
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def _accent_color(self) -> QColor:
        if self._accent_override:
            override = QColor(self._accent_override)
            if override.isValid():
                override.setAlpha(210)
                return override
        owner = self.parentWidget()
        theme = str(getattr(owner, "theme_name", getattr(owner, "_theme_name", "dark")))
        palette = OVERLAY_THEMES.get(theme, OVERLAY_THEMES["dark"])
        color = QColor(palette["accent"])
        color.setAlpha(210)
        return color

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        del event
        if not self._hovered:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self._accent_color(), RESIZE_INDICATOR_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        width = float(self.width())
        height = float(self.height())
        length = float(
            min(
                RESIZE_INDICATOR_LENGTH,
                max(4, self.width() - 4),
                max(4, self.height() - 4),
            )
        )

        if self.edge == "left":
            painter.drawLine(QPointF(1.5, 4.0), QPointF(1.5, max(4.0, height - 4.0)))
        elif self.edge == "right":
            x = max(1.5, width - 2.0)
            painter.drawLine(QPointF(x, 4.0), QPointF(x, max(4.0, height - 4.0)))
        elif self.edge == "top":
            painter.drawLine(QPointF(4.0, 1.5), QPointF(max(4.0, width - 4.0), 1.5))
        elif self.edge == "bottom":
            y = max(1.5, height - 2.0)
            painter.drawLine(QPointF(4.0, y), QPointF(max(4.0, width - 4.0), y))
        elif self.edge == "top_left":
            painter.drawLine(QPointF(1.5, 1.5), QPointF(1.5 + length, 1.5))
            painter.drawLine(QPointF(1.5, 1.5), QPointF(1.5, 1.5 + length))
        elif self.edge == "top_right":
            x = max(1.5, width - 2.0)
            painter.drawLine(QPointF(x - length, 1.5), QPointF(x, 1.5))
            painter.drawLine(QPointF(x, 1.5), QPointF(x, 1.5 + length))
        elif self.edge == "bottom_left":
            y = max(1.5, height - 2.0)
            painter.drawLine(QPointF(1.5, y), QPointF(1.5 + length, y))
            painter.drawLine(QPointF(1.5, y - length), QPointF(1.5, y))
        elif self.edge == "bottom_right":
            x = max(1.5, width - 2.0)
            y = max(1.5, height - 2.0)
            painter.drawLine(QPointF(x - length, y), QPointF(x, y))
            painter.drawLine(QPointF(x, y - length), QPointF(x, y))

        painter.end()


__all__ = [
    "OverlayResizeHandle",
    "RESIZE_CORNER_SIZE",
    "RESIZE_EDGE_THICKNESS",
    "RESIZE_EDGES",
    "RESIZE_INDICATOR_LENGTH",
    "RESIZE_INDICATOR_WIDTH",
]
