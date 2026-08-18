"""Optional automatic translation trigger based on mouse text selection."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from enum import Enum
from threading import Lock
from time import monotonic
from typing import Any

from PySide6.QtCore import QObject, Signal
from pynput import mouse

from app.infrastructure.config import ConfigManager
from app.models.events import TranslationTriggerEvent

DEFAULT_AUTO_SELECTION_DEBOUNCE_SECONDS = 0.25
DEFAULT_DRAG_THRESHOLD_PIXELS = 4
MOUSE_SELECTION_SOURCE = "mouse_selection"
LOGGER_NAME = "desktop_translator"


class MouseSelectionState(str, Enum):
    """States used while recognizing one left-button selection gesture."""

    IDLE = "idle"
    MOUSE_DOWN = "mouse_down"
    DRAGGING = "dragging"
    WAITING_DEBOUNCE = "waiting_debounce"
    CAPTURE_SELECTION = "capture_selection"


class MouseSelectionManager(QObject):
    """Emit one trigger after a left-button drag and release.

    The pynput listener owns its own background thread. Its callback performs
    only small state transitions and emits a Qt signal; selection capture and
    translation remain in the existing application/controller path.
    """

    triggered = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        config_manager: ConfigManager | Any | None = None,
        listener_factory: Callable[..., Any] | None = None,
        clock: Callable[[], float] | None = None,
        debounce_seconds: float | None = None,
        drag_threshold_pixels: int = DEFAULT_DRAG_THRESHOLD_PIXELS,
        overlay_hit_test: Callable[[int, int], bool] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(parent)

        self.config_manager = config_manager or ConfigManager()
        configured_debounce = (
            debounce_seconds
            if debounce_seconds is not None
            else getattr(
                self.config_manager,
                "auto_selection_debounce_seconds",
                DEFAULT_AUTO_SELECTION_DEBOUNCE_SECONDS,
            )
        )
        self._debounce_seconds = self._coerce_debounce(configured_debounce)
        self._drag_threshold_pixels = max(1, int(drag_threshold_pixels))
        self._listener_factory = listener_factory or mouse.Listener
        self._clock = clock or monotonic
        self.logger = logger or logging.getLogger(LOGGER_NAME)
        self._overlay_hit_test = (
            overlay_hit_test
            if overlay_hit_test is not None
            else lambda _x, _y: False
        )

        self._lock = Lock()
        self._listener: Any | None = None
        self._state = MouseSelectionState.IDLE
        self._button_down = False
        self._ignored_gesture = False
        self._dragging = False
        self._press_position: tuple[int, int] | None = None
        self._last_trigger_at: float | None = None

    @staticmethod
    def _coerce_debounce(value: object) -> float:
        try:
            seconds = float(value)
            if not math.isfinite(seconds):
                raise ValueError("debounce must be finite")
        except (TypeError, ValueError):
            seconds = DEFAULT_AUTO_SELECTION_DEBOUNCE_SECONDS
        return max(0.0, seconds)

    def reconfigure(self, debounce_seconds: float | None = None) -> bool:
        """Apply the duplicate-selection interval for future gestures."""

        value = (
            debounce_seconds
            if debounce_seconds is not None
            else getattr(
                self.config_manager,
                "auto_selection_debounce_seconds",
                DEFAULT_AUTO_SELECTION_DEBOUNCE_SECONDS,
            )
        )
        try:
            self._debounce_seconds = self._coerce_debounce(value)
        except Exception:
            return False
        return True

    @property
    def debounce_seconds(self) -> float:
        """Return the configured leading-edge debounce interval."""

        return self._debounce_seconds

    @property
    def is_running(self) -> bool:
        """Whether the global mouse listener is active."""

        with self._lock:
            return self._listener is not None

    @property
    def state(self) -> MouseSelectionState:
        """Return the current gesture-recognition state."""

        with self._lock:
            return self._state

    def start(self) -> bool:
        """Start the listener once; return whether automatic mode is active."""

        with self._lock:
            if self._listener is not None:
                return True

        listener = self._listener_factory(
            on_click=self._on_click,
            on_move=self._on_move,
        )
        with self._lock:
            self._listener = listener
            self._reset_gesture_locked()
            self._last_trigger_at = None

        try:
            listener.start()
        except Exception:
            with self._lock:
                self._listener = None
                self._reset_gesture_locked()
            stop = getattr(listener, "stop", None)
            if callable(stop):
                try:
                    stop()
                except Exception:
                    pass
            raise
        return True

    def stop(self) -> None:
        """Stop the listener and discard any partially completed gesture."""

        with self._lock:
            listener = self._listener
            self._listener = None
            self._reset_gesture_locked()
            self._last_trigger_at = None

        if listener is None:
            return

        stop = getattr(listener, "stop", None)
        if callable(stop):
            stop()

        join = getattr(listener, "join", None)
        if callable(join):
            try:
                join(1.0)
            except TypeError:
                join()

    def ensure_running(self) -> bool:
        """Recover a listener that died after startup or system resume."""

        with self._lock:
            listener = self._listener
        if listener is None:
            return False
        is_alive = getattr(listener, "is_alive", None)
        if not callable(is_alive):
            return True
        try:
            alive = bool(is_alive())
        except Exception as exc:
            self.logger.error(
                "mouse_selection_health_check_failed error_type=%s",
                type(exc).__name__,
                exc_info=self._safe_exception_info(exc),
            )
            return False
        if alive:
            return True

        with self._lock:
            if self._listener is listener:
                self._listener = None
                self._reset_gesture_locked()
                self._last_trigger_at = None
        try:
            self.start()
        except Exception as exc:
            self.logger.error(
                "mouse_selection_recovery_failed error_type=%s",
                type(exc).__name__,
                exc_info=self._safe_exception_info(exc),
            )
            return False
        self.logger.info("mouse_selection_recovered")
        return True

    def _on_move(self, x: int, y: int) -> None:
        """Mark a gesture as dragging after it crosses the movement threshold."""

        with self._lock:
            if (
                self._listener is None
                or not self._button_down
                or self._ignored_gesture
            ):
                return
            if self._has_moved_locked(x, y):
                self._dragging = True
                self._state = MouseSelectionState.DRAGGING

    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        """Handle only left-button press/release events from MouseListener."""

        if button != mouse.Button.left:
            return

        try:
            if pressed:
                self._handle_left_press(x, y)
            else:
                self._handle_left_release(x, y)
        except Exception as exc:
            # A listener callback must not terminate the global pynput thread.
            with self._lock:
                self._reset_gesture_locked()
            self.logger.error(
                "mouse_selection_callback_failed error_type=%s",
                type(exc).__name__,
                exc_info=self._safe_exception_info(exc),
            )

    def _handle_left_press(self, x: int, y: int) -> None:
        ignored = self._is_overlay_point(x, y)
        with self._lock:
            if self._listener is None:
                return
            self._button_down = True
            self._ignored_gesture = ignored
            self._dragging = False
            self._press_position = (int(x), int(y))
            self._state = (
                MouseSelectionState.IDLE
                if ignored
                else MouseSelectionState.MOUSE_DOWN
            )

    def _handle_left_release(self, x: int, y: int) -> None:
        with self._lock:
            if self._listener is None or not self._button_down:
                return

            # Qt and pynput receive the same physical release independently.
            # If the Overlay was being dragged, the callback can miss the
            # initial hit test but still see the cursor over the Overlay at
            # release time. Treat that release as an Overlay gesture so it
            # cannot trigger translation and hide the displayed result.
            ignored = self._ignored_gesture or self._is_overlay_point(x, y)
            dragged = self._dragging or self._has_moved_locked(x, y)
            self._button_down = False
            self._ignored_gesture = False
            self._dragging = False
            self._press_position = None

            if ignored or not dragged:
                self._state = MouseSelectionState.IDLE
                return

            now = self._clock()
            if (
                self._last_trigger_at is not None
                and now - self._last_trigger_at < self._debounce_seconds
            ):
                self._state = MouseSelectionState.IDLE
                return

            self._last_trigger_at = now
            self._state = MouseSelectionState.WAITING_DEBOUNCE
            self._state = MouseSelectionState.CAPTURE_SELECTION
            event = TranslationTriggerEvent(
                hotkey=MOUSE_SELECTION_SOURCE,
                source=MOUSE_SELECTION_SOURCE,
            )

        self.triggered.emit(event)
        with self._lock:
            if self._state == MouseSelectionState.CAPTURE_SELECTION:
                self._state = MouseSelectionState.IDLE

    def _has_moved_locked(self, x: int, y: int) -> bool:
        if self._press_position is None:
            return False
        return (
            abs(int(x) - self._press_position[0]) >= self._drag_threshold_pixels
            or abs(int(y) - self._press_position[1]) >= self._drag_threshold_pixels
        )

    def _is_overlay_point(self, x: int, y: int) -> bool:
        try:
            return bool(self._overlay_hit_test(int(x), int(y)))
        except Exception:
            # A failed hit test should not terminate mouse monitoring. The
            # overlay itself remains non-triggering when its hit test works.
            return False

    def _reset_gesture_locked(self) -> None:
        self._state = MouseSelectionState.IDLE
        self._button_down = False
        self._ignored_gesture = False
        self._dragging = False
        self._press_position = None

    @staticmethod
    def _safe_exception_info(exc: BaseException):
        try:
            safe_exception = type(exc)(type(exc).__name__)
        except Exception:
            safe_exception = RuntimeError(type(exc).__name__)
        return type(safe_exception), safe_exception, exc.__traceback__


__all__ = [
    "DEFAULT_AUTO_SELECTION_DEBOUNCE_SECONDS",
    "DEFAULT_DRAG_THRESHOLD_PIXELS",
    "MOUSE_SELECTION_SOURCE",
    "MouseSelectionManager",
    "MouseSelectionState",
]
