"""Resizable production Overlay with responsive header collision avoidance."""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QToolButton

from app.ai.chat_selection_overlay import (
    SelectionCaptureConversationalAIOverlayManager,
    SelectionCaptureConversationalAIOverlayWindow,
)
from app.overlay.context_menu import OVERLAY_THEMES
from app.overlay.language_bar import OverlayLanguageBar, normalize_target_language_code
from app.overlay.positioning import PositionManager, PositionMode
from app.overlay.resize_handles import (
    OverlayResizeHandle,
    RESIZE_CORNER_SIZE,
    RESIZE_EDGE_THICKNESS,
    RESIZE_EDGES,
)
from app.overlay.window import DEFAULT_MIN_WIDTH, OverlayWindow


TRANSLATION_MIN_RESIZE_WIDTH = max(320, DEFAULT_MIN_WIDTH)
CHAT_MIN_RESIZE_WIDTH = 500
MIN_RESIZE_HEIGHT = 180
MIN_DRAG_HANDLE_GAP = 8
MAX_RESIZE_FONT_SIZE = 44
MIN_RESIZE_FONT_SIZE = 8


class ResizableConversationalAIOverlayWindow(
    SelectionCaptureConversationalAIOverlayWindow
):
    """Allow edge resizing while preserving readable, non-overlapping controls."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._manual_size_locked = False
        self._manual_resizing = False
        self._resize_edge = ""
        self._resize_start_geometry = QRect()
        self._resize_start_global = QPoint()
        self._resize_start_font_size = 0
        super().__init__(*args, **kwargs)

        # Replace the legacy combined ``Auto → 中文`` button only in the
        # production Overlay. The old widget remains a private compatibility
        # implementation detail in the base class but is removed from layout.
        self._header_layout.removeWidget(self._language_button)
        self._language_button.hide()
        self._language_bar = OverlayLanguageBar(self._header)
        self._language_bar.source_selected.connect(
            lambda code: self._handle_context_action("source_language", code)
        )
        self._language_bar.target_selected.connect(
            lambda code: self._handle_context_action("target_language", code)
        )
        self._language_bar.swap_requested.connect(
            lambda: self._handle_context_action("swap_languages", None)
        )
        self._header_layout.insertWidget(0, self._language_bar, 0)
        self._language_bar.set_languages(
            self._source_language,
            self._target_language,
        )
        self._language_bar.apply_palette(OVERLAY_THEMES[self._theme_name])

        self._resize_handles: dict[str, OverlayResizeHandle] = {}
        for edge in RESIZE_EDGES:
            handle = OverlayResizeHandle(edge, self)
            handle.installEventFilter(self)
            handle.set_theme_colors(
                OVERLAY_THEMES[self._theme_name]["border"],
                OVERLAY_THEMES[self._theme_name]["accent"],
            )
            handle.show()
            self._resize_handles[edge] = handle
        self._layout_resize_handles()

        stream_signal = getattr(self._chat_panel, "stream_layout_changed", None)
        if stream_signal is not None and callable(getattr(stream_signal, "connect", None)):
            stream_signal.connect(self._on_stream_layout_changed)
        self._chat_panel.set_display_font_size(max(10, round(self._font_size * 0.58)))
        self._apply_responsive_minimum_width()
        self._position_drag_handle()

    @property
    def manual_size_locked(self) -> bool:
        return self._manual_size_locked

    @property
    def language_bar(self) -> OverlayLanguageBar:
        return self._language_bar

    def _update_language_button(self) -> None:
        """Keep the compatibility button and the visible segmented bar in sync."""

        super()._update_language_button()
        bar = getattr(self, "_language_bar", None)
        if bar is not None:
            bar.set_languages(self._source_language, self._target_language)

    def set_target_language(self, target_language: object) -> str:
        """Set a concrete target language; automatic detection is source-only."""

        normalized = normalize_target_language_code(
            target_language,
            fallback=self._target_language if self._target_language != "auto" else "zh-CN",
        )
        self.set_languages(self._source_language, normalized)
        return self._target_language

    def swap_languages(self) -> tuple[str, str]:
        """Swap concrete language directions without ever making target ``auto``."""

        if self._source_language == "auto":
            return self._source_language, self._target_language
        return self.set_languages(self._target_language, self._source_language)

    def _handle_context_action(self, key: str, value: object) -> None:
        if key == "target_language":
            value = self.set_target_language(value)
        elif key == "swap_languages":
            value = self.swap_languages()
        super()._handle_context_action(key, value)

    def _apply_responsive_minimum_width(self) -> None:
        minimum_width = (
            CHAT_MIN_RESIZE_WIDTH if self._chat_open else TRANSLATION_MIN_RESIZE_WIDTH
        )
        self.setMinimumWidth(min(minimum_width, self.maximumWidth()))
        self.setMinimumHeight(min(MIN_RESIZE_HEIGHT, self.maximumHeight()))

    def _position_drag_handle(self) -> None:
        """Center the pill only when it cannot collide with header controls."""

        handle = getattr(self, "_drag_handle", None)
        header = getattr(self, "_header", None)
        language_bar = getattr(self, "_language_bar", None)
        language = getattr(self, "_language_button", None)
        if handle is None or header is None:
            return

        if language_bar is not None and language_bar.isVisible():
            left_limit = language_bar.geometry().right() + MIN_DRAG_HANDLE_GAP
            excluded = {
                language_bar.source_button,
                language_bar.swap_button,
                language_bar.target_button,
            }
        elif language is not None:
            left_limit = language.geometry().right() + MIN_DRAG_HANDLE_GAP
            excluded = {language}
        else:
            left_limit = MIN_DRAG_HANDLE_GAP
            excluded = set()

        right_limit = header.width() - MIN_DRAG_HANDLE_GAP
        right_buttons = [
            button
            for button in header.findChildren(QToolButton)
            if button not in excluded
            and button.parentWidget() is header
            and button.isVisible()
            and button.geometry().left() > left_limit
        ]
        if right_buttons:
            right_limit = min(button.geometry().left() for button in right_buttons)
            right_limit -= MIN_DRAG_HANDLE_GAP

        available = right_limit - left_limit
        if available < handle.width():
            # At very small widths the bar is hidden rather than covering an
            # AI/header action. Header and Chat title dragging remain available.
            handle.hide()
            return

        desired_x = (header.width() - handle.width()) // 2
        x = max(left_limit, min(desired_x, right_limit - handle.width()))
        y = max(0, (header.height() - handle.height()) // 2)
        handle.move(x, y)
        handle.show()
        handle.raise_()

    def _layout_resize_handles(self) -> None:
        handles = getattr(self, "_resize_handles", None)
        if not handles:
            return
        width = self.width()
        height = self.height()
        edge = RESIZE_EDGE_THICKNESS
        corner = RESIZE_CORNER_SIZE

        handles["left"].setGeometry(0, corner, edge, max(1, height - 2 * corner))
        handles["right"].setGeometry(
            max(0, width - edge), corner, edge, max(1, height - 2 * corner)
        )
        handles["top"].setGeometry(corner, 0, max(1, width - 2 * corner), edge)
        handles["bottom"].setGeometry(
            corner, max(0, height - edge), max(1, width - 2 * corner), edge
        )
        handles["top_left"].setGeometry(0, 0, corner, corner)
        handles["top_right"].setGeometry(max(0, width - corner), 0, corner, corner)
        handles["bottom_left"].setGeometry(0, max(0, height - corner), corner, corner)
        handles["bottom_right"].setGeometry(
            max(0, width - corner), max(0, height - corner), corner, corner
        )
        for handle in handles.values():
            handle.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._layout_resize_handles()
        self._position_drag_handle()
        QTimer.singleShot(0, self._position_drag_handle)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt override
        handles = getattr(self, "_resize_handles", {})
        if watched in handles.values():
            edge = getattr(watched, "edge", "")
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._begin_manual_resize(edge, event.globalPosition().toPoint())
                    event.accept()
                    return True
            elif event_type == QEvent.Type.MouseMove:
                if self._manual_resizing and event.buttons() & Qt.MouseButton.LeftButton:
                    self._continue_manual_resize(event.globalPosition().toPoint())
                    event.accept()
                    return True
            elif event_type == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton and self._manual_resizing:
                    self._finish_manual_resize()
                    event.accept()
                    return True
        return super().eventFilter(watched, event)

    def _begin_manual_resize(self, edge: str, global_position: QPoint) -> None:
        if self._is_locked or edge not in RESIZE_EDGES:
            return
        self._stop_resize_animation()
        self._dragging = False
        self._manual_resizing = True
        self._manual_size_locked = True
        self._resize_edge = edge
        self._resize_start_geometry = QRect(self.geometry())
        self._resize_start_global = QPoint(global_position)
        self._resize_start_font_size = int(self._font_size)

    def _continue_manual_resize(self, global_position: QPoint) -> None:
        if not self._manual_resizing or not self._resize_start_geometry.isValid():
            return
        delta = global_position - self._resize_start_global
        start = self._resize_start_geometry
        edge = self._resize_edge
        x, y, width, height = start.x(), start.y(), start.width(), start.height()

        if "left" in edge:
            x += delta.x()
            width -= delta.x()
        if "right" in edge:
            width += delta.x()
        if "top" in edge:
            y += delta.y()
            height -= delta.y()
        if "bottom" in edge:
            height += delta.y()

        minimum_width = CHAT_MIN_RESIZE_WIDTH if self._chat_open else TRANSLATION_MIN_RESIZE_WIDTH
        minimum_width = min(minimum_width, self.maximumWidth())
        minimum_height = min(MIN_RESIZE_HEIGHT, self.maximumHeight())
        maximum_width = self.maximumWidth()
        maximum_height = self.maximumHeight()

        if width < minimum_width:
            if "left" in edge:
                x = start.right() - minimum_width + 1
            width = minimum_width
        elif width > maximum_width:
            if "left" in edge:
                x = start.right() - maximum_width + 1
            width = maximum_width

        if height < minimum_height:
            if "top" in edge:
                y = start.bottom() - minimum_height + 1
            height = minimum_height
        elif height > maximum_height:
            if "top" in edge:
                y = start.bottom() - maximum_height + 1
            height = maximum_height

        screen = QGuiApplication.screenAt(global_position)
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, available.width())
            height = min(height, available.height())

        self.setGeometry(x, y, width, height)
        self._scale_fonts_for_manual_size(QSize(width, height))

    def _scale_fonts_for_manual_size(self, new_size: QSize) -> None:
        start = self._resize_start_geometry.size()
        if start.width() <= 0 or start.height() <= 0:
            return
        start_area = max(1, start.width() * start.height())
        new_area = max(1, new_size.width() * new_size.height())
        ratio = math.sqrt(new_area / start_area)
        target = round(self._resize_start_font_size * ratio)
        target = max(MIN_RESIZE_FONT_SIZE, min(MAX_RESIZE_FONT_SIZE, target))
        if target == self._font_size:
            return
        self._font_size = target
        self._label.setFont(QFont(self._font_family, target))
        self._source_label.setFont(
            QFont(
                self._font_family,
                max(8, min(18, round(target * 0.55))),
            )
        )
        self._chat_panel.set_display_font_size(max(10, round(target * 0.58)))
        self._set_content_maximum_width()
        self._apply_theme(self._theme_name)

    def _finish_manual_resize(self) -> None:
        if not self._manual_resizing:
            return
        self._manual_resizing = False
        self._resize_edge = ""
        self._position_manager.remember_manual_position(self.pos())
        self._position_manager.set_position_mode(PositionMode.CUSTOM_FIXED_POSITION)
        save = getattr(self._chat_config_manager, "save", None)
        if callable(save):
            try:
                save({"overlay": {"font_size": int(self._font_size)}})
            except (OSError, TypeError, ValueError):
                pass
        self._clamp_current_position()
        self._layout_resize_handles()
        self._position_drag_handle()

    def _resize_to_content(
        self,
        *,
        animate: bool = False,
        start_size: QSize | None = None,
    ) -> None:
        if getattr(self, "_manual_size_locked", False):
            self._update_scroll_area_limits()
            self._content_layout.invalidate()
            self._layout.invalidate()
            self._content_layout.activate()
            self._layout.activate()
            self.updateGeometry()
            self._layout_resize_handles()
            return
        super()._resize_to_content(animate=animate, start_size=start_size)

    def _on_stream_layout_changed(self) -> None:
        if not self._chat_open:
            return
        if self._manual_size_locked:
            self._chat_panel.messages_content.updateGeometry()
            self._chat_panel.messages_scroll.updateGeometry()
            self.updateGeometry()
            return
        self._resize_to_content(animate=False)

    def begin_chat_stream(self, request_id: int) -> None:
        self._chat_panel.begin_streaming_reply(request_id)
        self._on_stream_layout_changed()

    def update_chat_stream(self, request_id: int, text: str) -> None:
        if self._chat_panel.update_streaming_reply(request_id, text):
            self._on_stream_layout_changed()

    def finish_chat_stream(self, request_id: int, text: str) -> None:
        if self._chat_panel.finish_streaming_reply(request_id, text):
            self._on_stream_layout_changed()

    def cancel_chat_stream(self, request_id: int | None = None) -> None:
        self._chat_panel.cancel_streaming_reply(request_id)
        self._on_stream_layout_changed()

    def open_chat(self, **kwargs: Any) -> None:
        self._apply_responsive_minimum_width()
        super().open_chat(**kwargs)
        self._apply_responsive_minimum_width()
        self._chat_panel.set_display_font_size(max(10, round(self._font_size * 0.58)))
        self._position_drag_handle()

    def close_chat(self) -> None:
        self.cancel_chat_stream()
        super().close_chat()
        self._apply_responsive_minimum_width()
        self._position_drag_handle()

    def lock_overlay(self) -> bool:
        result = super().lock_overlay()
        for handle in getattr(self, "_resize_handles", {}).values():
            handle.setVisible(not result)
        return result

    def unlock_overlay(self) -> bool:
        result = super().unlock_overlay()
        if result:
            for handle in getattr(self, "_resize_handles", {}).values():
                handle.show()
            self._layout_resize_handles()
        return result

    def _apply_theme(self, theme: str) -> None:
        super()._apply_theme(theme)
        palette = OVERLAY_THEMES[self._theme_name]
        bar = getattr(self, "_language_bar", None)
        if bar is not None:
            bar.apply_palette(palette)
        for handle in getattr(self, "_resize_handles", {}).values():
            handle.set_theme_colors(palette["border"], palette["accent"])


class ResizableConversationalAIOverlayManager(
    SelectionCaptureConversationalAIOverlayManager
):
    """Expose streaming/resizing capabilities through the manager boundary."""

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
            window = ResizableConversationalAIOverlayWindow(
                position_manager=resolved_position_manager,
                config_manager=config_manager,
            )
        super().__init__(window=window)

    def begin_chat_stream(self, request_id: int) -> None:
        callback = getattr(self.window, "begin_chat_stream", None)
        if callable(callback):
            callback(request_id)

    def update_chat_stream(self, request_id: int, text: str) -> None:
        callback = getattr(self.window, "update_chat_stream", None)
        if callable(callback):
            callback(request_id, text)

    def finish_chat_stream(self, request_id: int, text: str) -> None:
        callback = getattr(self.window, "finish_chat_stream", None)
        if callable(callback):
            callback(request_id, text)

    def cancel_chat_stream(self, request_id: int | None = None) -> None:
        callback = getattr(self.window, "cancel_chat_stream", None)
        if callable(callback):
            callback(request_id)


__all__ = [
    "CHAT_MIN_RESIZE_WIDTH",
    "MIN_RESIZE_HEIGHT",
    "ResizableConversationalAIOverlayManager",
    "ResizableConversationalAIOverlayWindow",
    "TRANSLATION_MIN_RESIZE_WIDTH",
]
