"""Small orchestration wrapper around the overlay window."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint
from PySide6.QtGui import QScreen

from app.infrastructure.config import ConfigManager
from app.overlay.window import OverlayWindow
from app.overlay.positioning import PositionManager


class OverlayManager:
    """Keep future application/controller code independent of QWidget details."""

    def __init__(
        self,
        window: OverlayWindow | None = None,
        *,
        position_manager: PositionManager | None = None,
        config_manager: ConfigManager | Any | None = None,
    ) -> None:
        if window is not None:
            self.window = window
            self.position_manager = window.position_manager
        else:
            self.position_manager = position_manager or PositionManager(
                config_manager=config_manager,
            )
            self.window = OverlayWindow(
                position_manager=self.position_manager,
                config_manager=config_manager,
            )

    def show_text(self, text: object | None) -> None:
        self.window.show_text(text)

    def show_loading(
        self,
        source_text: object | None,
        source_language: object = "auto",
        target_language: object = "zh-CN",
    ) -> None:
        """Show the provider-loading state when the window supports it."""

        show_loading = getattr(self.window, "show_loading", None)
        if callable(show_loading):
            show_loading(source_text, source_language, target_language)
            return
        # Keep custom/injected legacy windows usable during the transition.
        self.window.show_text("翻译中")

    def show_copy_feedback(self) -> bool:
        """Show the short copy acknowledgement on the managed window."""

        show_feedback = getattr(self.window, "show_copy_feedback", None)
        if not callable(show_feedback):
            return False
        return bool(show_feedback())

    def show_translation(
        self,
        source_text: object | None,
        translated_text: object | None,
        source_language: object = "auto",
        target_language: object = "zh-CN",
    ) -> None:
        """Show a translated result with source context when supported."""

        show_translation = getattr(self.window, "show_translation", None)
        if callable(show_translation):
            show_translation(
                source_text,
                translated_text,
                source_language,
                target_language,
            )
            return
        self.window.show_text(translated_text)

    def show_overlay(self) -> None:
        self.window.show_overlay()

    def hide_overlay(self) -> None:
        self.window.hide_overlay()

    def connect_context_menu(self, callback) -> bool:
        """Connect semantic context-menu events from the real Overlay window."""

        signal = getattr(self.window, "context_action", None)
        if signal is None or not callable(getattr(signal, "connect", None)):
            return False
        signal.connect(callback)
        return True

    def set_languages(
        self,
        source_language: object = "auto",
        target_language: object = "zh-CN",
    ) -> tuple[str, str] | None:
        """Update the language direction displayed by the real Overlay."""

        setter = getattr(self.window, "set_languages", None)
        if not callable(setter):
            return None
        return setter(source_language, target_language)

    def set_original_visible(self, visible: bool) -> bool | None:
        """Toggle source-text visibility on the managed Overlay."""

        setter = getattr(self.window, "set_original_visible", None)
        if not callable(setter):
            return None
        return bool(setter(visible))

    @property
    def context_menu(self):
        """Return the styled Overlay context menu when the window provides it."""

        return getattr(self.window, "context_menu", None)

    def contains_global_point(self, x: int, y: int) -> bool:
        """Return whether a visible Overlay occupies the global point."""

        if not self.window.isVisible():
            return False
        point = QPoint(int(x), int(y))
        # Qt receives the enter event on the GUI thread while pynput may
        # query the native frame a few milliseconds earlier/later. Prefer
        # this state when the pointer is visibly inside the card.
        if bool(getattr(self.window, "is_hovered", False)):
            return True
        # During a drag the window follows the cursor. The native global
        # mouse callback may run while Qt is between move/release events, so
        # the point can briefly be outside the last frame geometry even
        # though the gesture belongs to the Overlay.
        if bool(getattr(self.window, "is_dragging", False)):
            return True
        if self.window.frameGeometry().contains(point):
            return True

        # A QMenu is a separate native popup window. Its click must also be
        # ignored by automatic mouse selection; otherwise clicking a menu
        # action (including 置顶显示) can emit a new selection event after the
        # menu closes and hide the Overlay immediately afterwards.
        context_menu = getattr(self.window, "context_menu", None)
        if context_menu is None:
            return False
        menus = [context_menu]
        find_children = getattr(context_menu, "findChildren", None)
        if callable(find_children):
            try:
                menus.extend(find_children(type(context_menu)))
            except Exception:
                pass
        for menu in menus:
            try:
                if menu.isVisible() and menu.frameGeometry().contains(point):
                    return True
            except Exception:
                continue
        return False

    @property
    def position_mode(self) -> str:
        """Return the active overlay placement mode."""

        return self.position_manager.position_mode

    def set_position_mode(self, mode: str) -> str:
        """Change the managed overlay placement mode."""

        return self.window.set_position_mode(mode)

    def set_custom_position(self, position: QPoint | tuple[int, int]) -> QPoint:
        """Remember the managed overlay's custom fixed position."""

        return self.window.set_custom_position(position)

    def apply_style(
        self,
        *,
        font_family: str | None = None,
        font_size: int | None = None,
        opacity: float | None = None,
        background_opacity: float | None = None,
        text_opacity: float | None = None,
        max_width: int | None = None,
    ) -> None:
        """Apply settings-page visual values without exposing QWidget details."""

        self.window.apply_style(
            font_family=font_family,
            font_size=font_size,
            opacity=opacity,
            background_opacity=background_opacity,
            text_opacity=text_opacity,
            max_width=max_width,
        )

    @property
    def font_size(self) -> int:
        """Return the current Overlay font size."""

        return self.window.font_size

    @property
    def opacity(self) -> float:
        """Return the legacy opacity alias mapped to the background."""

        return self.window.opacity

    @property
    def background_opacity(self) -> float:
        """Return the current Overlay background opacity."""

        return self.window.background_opacity

    @property
    def text_opacity(self) -> float:
        """Return the current Overlay text opacity."""

        return self.window.text_opacity

    @property
    def original_visible(self) -> bool:
        """Return whether source text is displayed on the Overlay."""

        return bool(getattr(self.window, "original_visible", False))

    @property
    def source_language(self) -> str:
        """Return the Overlay source-language code."""

        return str(getattr(self.window, "source_language", "auto"))

    @property
    def target_language(self) -> str:
        """Return the Overlay target-language code."""

        return str(getattr(self.window, "target_language", "zh-CN"))

    @property
    def theme_name(self) -> str:
        """Return the current Overlay theme identifier."""

        return self.window.theme_name

    @property
    def always_on_top(self) -> bool:
        """Return whether the Overlay requests topmost presentation."""

        return self.window.always_on_top

    def set_theme(self, theme: str) -> str:
        """Apply a theme through the managed window."""

        return self.window.set_theme(theme)

    def set_always_on_top(self, enabled: bool) -> bool:
        """Toggle topmost presentation through the managed window."""

        return self.window.set_always_on_top(enabled)

    @property
    def is_locked(self) -> bool:
        """Return the overlay lock state."""

        return self.window.is_locked

    def lock_overlay(self) -> bool:
        """Lock the managed overlay and enable click-through behavior."""

        return self.window.lock_overlay()

    def unlock_overlay(self) -> bool:
        """Unlock the managed overlay and enable drag behavior."""

        return self.window.unlock_overlay()

    def move_clamped(
        self,
        position: QPoint | tuple[int, int],
        *,
        screen: QScreen | None = None,
    ) -> None:
        self.window.move_clamped(position, screen=screen)

    def center_on_screen(self, screen: QScreen | None = None) -> None:
        self.window.center_on_screen(screen)
