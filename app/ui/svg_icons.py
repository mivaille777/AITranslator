"""Theme-aware SVG icon registry for AITrans QWidget surfaces.

The registry keeps icon semantics independent from fonts and widget code. Icons
are rendered from small local SVG fragments through QtSvg, so Windows font
fallback and DPI differences can no longer change glyph shape or alignment.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.ui.design_tokens import ICON


# 24x24 outline icon bodies authored specifically for AITrans. Shapes inherit
# stroke/fill rules from the shared SVG wrapper unless a body opts into fill.
_ICON_BODIES: dict[str, str] = {
    "menu": '<path d="M5 7h14M5 12h14M5 17h14"/>',
    "more": '<circle cx="6" cy="12" r="1.2" fill="{color}" stroke="none"/><circle cx="12" cy="12" r="1.2" fill="{color}" stroke="none"/><circle cx="18" cy="12" r="1.2" fill="{color}" stroke="none"/>',
    "copy": '<rect x="8" y="8" width="10" height="11" rx="2"/><path d="M6 16H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "add": '<path d="M12 5v14M5 12h14"/>',
    "back": '<path d="M15.5 5.5 9 12l6.5 6.5M9.5 12H20"/>',
    "down": '<path d="M6 9l6 6 6-6"/>',
    "chevron_down": '<path d="M7 9.5 12 14.5l5-5"/>',
    "chevron_up": '<path d="m7 14.5 5-5 5 5"/>',
    "delete": '<path d="M5 7h14M9 7V4.5h6V7M8 10v7M12 10v7M16 10v7M7 7l1 13h8l1-13"/>',
    "stop": '<rect x="7" y="7" width="10" height="10" rx="2" fill="{color}" stroke="none"/>',
    "refresh": '<path d="M19 8V4l-2 2a7 7 0 1 0 1.5 8.5M19 4h-4"/>',
    "undo": '<path d="M9 8 5 12l4 4M6 12h7a6 6 0 0 1 6 6"/>',
    "history": '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2M6.5 5.5 4 6v-3"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M6 6l1.4 1.4M16.6 16.6 18 18M18 6l-1.4 1.4M7.4 16.6 6 18"/><circle cx="12" cy="12" r="7" stroke-dasharray="2.2 2.2"/>',
    "sparkle": '<path d="M12 3l1.3 4.1L17 9l-3.7 1.9L12 15l-1.3-4.1L7 9l3.7-1.9L12 3ZM18 14l.7 2.1L21 17l-2.3.9L18 20l-.7-2.1L15 17l2.3-.9L18 14Z"/>',
    "document": '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v5h4M10 12h5M10 16h5"/>',
    "note": '<path d="M6 4h12v14l-3 3H6z"/><path d="M15 21v-4h3M9 9h6M9 13h5"/>',
    "library": '<path d="M5 5h4v14H5zM10 5h4v14h-4zM15 6l3-1 3 13-3 1z"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 10v6"/><circle cx="12" cy="7" r="1" fill="{color}" stroke="none"/>',
    "power": '<path d="M12 3v8M7.1 6.5a8 8 0 1 0 9.8 0"/>',
    "hide": '<path d="M3.5 12s3-5 8.5-5 8.5 5 8.5 5-3 5-8.5 5-8.5-5-8.5-5Z"/><path d="m5 19 14-14"/>',
    "lock": '<rect x="6" y="10" width="12" height="10" rx="2"/><path d="M9 10V7a3 3 0 0 1 6 0v3"/>',
    "pin": '<path d="m9 4 6 0-1 5 3 3H7l3-3-1-5ZM12 12v8"/>',
    "eye": '<path d="M3.5 12s3-5 8.5-5 8.5 5 8.5 5-3 5-8.5 5-8.5-5-8.5-5Z"/><circle cx="12" cy="12" r="2.5"/>',
    "translate": '<path d="M5 5h8M9 3v2M6 8h6M7 5c.5 3 2 5 5 6M11 5c-.5 3-2 5-5 6M14 13h5M16.5 11l3.5 9M13 20l3.5-9"/>',
    "edit": '<path d="m5 16-1 4 4-1L18.5 8.5l-3-3L5 16ZM14.5 6.5l3 3"/>',
    "opacity": '<path d="M12 3s6 6.4 6 11a6 6 0 0 1-12 0c0-4.6 6-11 6-11Z"/><path d="M8 15h8"/>',
    "font": '<path d="M5 18 10 5h4l5 13M7 14h10"/>',
    "language": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9M12 3c-2.5 2.5-3.5 5.5-3.5 9s1 6.5 3.5 9"/>',
    "check": '<path d="m5 12 4 4 10-10"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
}


def icon_names() -> tuple[str, ...]:
    """Return stable semantic names exposed by the AITrans icon system."""

    return tuple(sorted(_ICON_BODIES))


def _safe_color(value: object) -> str:
    color = QColor(str(value or ""))
    if not color.isValid():
        color = QColor("#F8FAFC")
    return color.name(QColor.NameFormat.HexRgb)


def svg_source(name: object, color: object = "#F8FAFC") -> str:
    """Return a complete local SVG document for one semantic icon."""

    key = str(name or "").strip().lower()
    body = _ICON_BODIES.get(key)
    if body is None:
        raise KeyError(f"Unknown AITrans icon: {key or name!r}")
    safe = _safe_color(color)
    body = body.format(color=safe)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" '
        f'stroke="{safe}" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )


@lru_cache(maxsize=256)
def _render_cached(name: str, color: str, size: int) -> QIcon:
    logical_size = max(ICON.xs, int(size))
    scale = 2
    pixel_size = logical_size * scale
    renderer = QSvgRenderer(QByteArray(svg_source(name, color).encode("utf-8")))
    pixmap = QPixmap(pixel_size, pixel_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(float(scale))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, pixel_size, pixel_size))
    painter.end()
    return QIcon(pixmap)


def svg_icon(name: object, color: object = "#F8FAFC", *, size: int = ICON.md) -> QIcon:
    """Render one theme-colored SVG icon at a DPI-safe logical size."""

    key = str(name or "").strip().lower()
    if key not in _ICON_BODIES:
        raise KeyError(f"Unknown AITrans icon: {key or name!r}")
    safe = _safe_color(color)
    return QIcon(_render_cached(key, safe, max(ICON.xs, int(size))))


__all__ = ["icon_names", "svg_icon", "svg_source"]
