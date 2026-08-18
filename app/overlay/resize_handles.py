"""Transparent edge/corner resize affordances for the frameless Overlay."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


RESIZE_EDGE_THICKNESS = 7
RESIZE_CORNER_SIZE = 13
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
    """Invisible resize hit target kept above normal Overlay content."""

    def __init__(self, edge: str, parent=None) -> None:
        if edge not in RESIZE_EDGES:
            raise ValueError(f"Unsupported resize edge: {edge}")
        super().__init__(parent)
        self.edge = edge
        self.setObjectName(f"OverlayResizeHandle{edge.title().replace('_', '')}")
        self.setCursor(_CURSOR_BY_EDGE[edge])
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setStyleSheet("background: transparent; border: none;")


__all__ = [
    "OverlayResizeHandle",
    "RESIZE_CORNER_SIZE",
    "RESIZE_EDGE_THICKNESS",
    "RESIZE_EDGES",
]
