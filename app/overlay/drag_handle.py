"""Theme-aware center drag affordance for the frameless Overlay header."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


DRAG_HANDLE_WIDTH = 54
DRAG_HANDLE_HEIGHT = 18
DRAG_PILL_WIDTH = 34
DRAG_PILL_HEIGHT = 4


class OverlayDragHandle(QWidget):
    """Small centered pill that brightens on hover and acts as a drag target."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("OverlayDragHandle")
        self.setFixedSize(DRAG_HANDLE_WIDTH, DRAG_HANDLE_HEIGHT)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._hovered = False
        self._normal_color = QColor("#CBD5E1")
        self._hover_color = QColor("#60A5FA")
        self.setToolTip("拖动悬浮窗；双击返回翻译页面")

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(DRAG_HANDLE_WIDTH, DRAG_HANDLE_HEIGHT)

    def set_theme_colors(self, normal: str, hover: str) -> None:
        normal_color = QColor(str(normal))
        hover_color = QColor(str(hover))
        if normal_color.isValid():
            self._normal_color = normal_color
        if hover_color.isValid():
            self._hover_color = hover_color
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(self._hover_color if self._hovered else self._normal_color)
        color.setAlpha(235 if self._hovered else 135)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        left = (self.width() - DRAG_PILL_WIDTH) / 2.0
        top = (self.height() - DRAG_PILL_HEIGHT) / 2.0
        painter.drawRoundedRect(
            QRectF(left, top, DRAG_PILL_WIDTH, DRAG_PILL_HEIGHT),
            DRAG_PILL_HEIGHT / 2.0,
            DRAG_PILL_HEIGHT / 2.0,
        )
        painter.end()


__all__ = [
    "DRAG_HANDLE_HEIGHT",
    "DRAG_HANDLE_WIDTH",
    "OverlayDragHandle",
]
