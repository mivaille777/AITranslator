"""Shared icon-button behavior for AITrans QWidget surfaces.

The helpers keep hit targets, icon sizes, pressed/hover states and menu
chevrons consistent without coupling product surfaces to one concrete widget
subclass. They are intentionally small so future QML controls can mirror the
same three size variants.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtWidgets import QLabel, QToolButton

from app.ui.design_tokens import CONTROL, ICON, RADIUS, SPACING
from app.ui.svg_icons import svg_icon


@dataclass(frozen=True, slots=True)
class IconButtonMetrics:
    name: str
    button_size: int
    icon_size: int


ICON_BUTTON_COMPACT = IconButtonMetrics(
    "compact",
    CONTROL.compact_height,
    ICON.sm,
)
ICON_BUTTON_TOOLBAR = IconButtonMetrics(
    "toolbar",
    CONTROL.icon_button,
    ICON.md,
)
ICON_BUTTON_COMPOSER = IconButtonMetrics(
    "composer",
    CONTROL.large_height,
    ICON.md,
)


def configure_icon_button(
    button: QToolButton,
    metrics: IconButtonMetrics = ICON_BUTTON_TOOLBAR,
) -> None:
    """Apply one semantic icon-button size contract."""

    button.setText("")
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    button.setIconSize(QSize(metrics.icon_size, metrics.icon_size))
    button.setFixedSize(metrics.button_size, metrics.button_size)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setProperty("aiTransIconButtonVariant", metrics.name)


def icon_button_stylesheet(
    palette: dict[str, str],
    *,
    radius: int = RADIUS.sm,
) -> str:
    """Return the shared chrome states for one icon-only QToolButton."""

    background = palette.get("chrome_background", palette["menu_background"])
    border = palette.get("chrome_border", palette["border"])
    hover = palette.get("chrome_hover", palette["hover"])
    text = palette.get("chrome_text", palette["text"])
    muted = palette.get("chrome_muted_text", palette["muted_text"])
    accent = palette["accent"]
    pressed = palette.get("accent_muted", hover)
    return f"""
        QToolButton {{
            color: {text};
            background-color: {background};
            border: 1px solid {border};
            border-radius: {radius}px;
            padding: 0px;
        }}
        QToolButton:hover:enabled {{
            background-color: {hover};
            border-color: {accent};
        }}
        QToolButton:pressed:enabled,
        QToolButton:checked:enabled {{
            background-color: {pressed};
            border-color: {accent};
        }}
        QToolButton:disabled {{
            color: {muted};
            background-color: {background};
            border-color: {border};
        }}
        QToolButton::menu-indicator {{
            image: none;
            width: 0px;
            height: 0px;
        }}
    """


def apply_icon_button_palette(
    button: QToolButton,
    palette: dict[str, str],
    *,
    radius: int = RADIUS.sm,
) -> None:
    button.setStyleSheet(icon_button_stylesheet(palette, radius=radius))


class _MenuChevronOverlay(QObject):
    """Paint a right-side SVG chevron over an existing text QToolButton.

    Existing managed-chat controls are already QToolButtons. Keeping them in
    place preserves all menus/signals while removing both the legacy ``▾`` text
    suffix and Qt's platform-dependent native menu indicator. The overlay is a
    decoration only: it must never change the width contract owned by the
    parent header layout.
    """

    def __init__(
        self,
        button: QToolButton,
        *,
        color: str,
        disabled_color: str,
        size: int = ICON.xs,
    ) -> None:
        super().__init__(button)
        self._button = button
        self._color = str(color)
        self._disabled_color = str(disabled_color)
        self._size = max(ICON.xs, int(size))
        self._label = QLabel(button)
        self._label.setObjectName("AITransMenuChevron")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._label.setFixedSize(self._size, self._size)
        self._label.show()
        button.installEventFilter(self)
        button.setProperty("aiTransMenuChevron", True)

        # QSS padding participates in Qt's size hint calculation. Preserve the
        # existing min/max width budget so adding a visual chevron cannot turn
        # a 76px font control into a wider toolbar item.
        minimum_width = button.minimumWidth()
        maximum_width = button.maximumWidth()
        button.setStyleSheet(
            button.styleSheet()
            + f"""
            QToolButton {{
                padding-right: {self._size + SPACING.md}px;
            }}
            QToolButton::menu-indicator {{
                image: none;
                width: 0px;
                height: 0px;
            }}
            """
        )
        button.setMinimumWidth(minimum_width)
        button.setMaximumWidth(maximum_width)
        self._strip_legacy_suffix()
        self._refresh()

    def set_colors(self, color: str, disabled_color: str) -> None:
        self._color = str(color)
        self._disabled_color = str(disabled_color)
        self._strip_legacy_suffix()
        self._refresh()

    def normalize_text(self) -> None:
        """Remove any legacy dropdown glyph reintroduced by product text sync."""

        self._strip_legacy_suffix()
        self._refresh()

    def _strip_legacy_suffix(self) -> None:
        text = self._button.text().rstrip()
        changed = False
        while text.endswith(("▾", "⌄", "▼")):
            text = text[:-1].rstrip()
            changed = True
        if changed:
            self._button.setText(text)

    def _refresh(self) -> None:
        color = self._color if self._button.isEnabled() else self._disabled_color
        icon = svg_icon("chevron_down", color, size=self._size)
        self._label.setPixmap(icon.pixmap(QSize(self._size, self._size)))
        x = max(0, self._button.width() - SPACING.sm - self._size)
        y = max(0, (self._button.height() - self._size) // 2)
        self._label.move(x, y)
        self._label.raise_()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override
        if watched is self._button:
            if event.type() == QEvent.Type.Paint:
                self._strip_legacy_suffix()
            if event.type() in {
                QEvent.Type.Paint,
                QEvent.Type.Resize,
                QEvent.Type.Show,
                QEvent.Type.EnabledChange,
                QEvent.Type.StyleChange,
            }:
                self._refresh()
        return False


def attach_menu_chevron(
    button: QToolButton,
    *,
    color: str,
    disabled_color: str,
    size: int = ICON.xs,
) -> None:
    """Attach or recolor the shared SVG dropdown affordance."""

    existing = getattr(button, "_aitrans_menu_chevron", None)
    if isinstance(existing, _MenuChevronOverlay):
        existing.set_colors(color, disabled_color)
        return
    overlay = _MenuChevronOverlay(
        button,
        color=color,
        disabled_color=disabled_color,
        size=size,
    )
    button._aitrans_menu_chevron = overlay  # type: ignore[attr-defined]


def normalize_menu_chevron(button: QToolButton) -> None:
    """Normalize text after a model/font label update without touching layout."""

    existing = getattr(button, "_aitrans_menu_chevron", None)
    if isinstance(existing, _MenuChevronOverlay):
        existing.normalize_text()


__all__ = [
    "ICON_BUTTON_COMPACT",
    "ICON_BUTTON_COMPOSER",
    "ICON_BUTTON_TOOLBAR",
    "IconButtonMetrics",
    "apply_icon_button_palette",
    "attach_menu_chevron",
    "configure_icon_button",
    "icon_button_stylesheet",
    "normalize_menu_chevron",
]
