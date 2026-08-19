"""Optional automatic translation trigger based on mouse text selection."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from enum import Enum
from threading import Lock
from time import monotonic
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from pynput import mouse

from app.infrastructure.config import ConfigManager
from app.models.events import TranslationTriggerEvent
from app.models.selection import SelectionContext

DEFAULT_AUTO_SELECTION_DEBOUNCE_SECONDS = 0.25
DEFAULT_SELECTION_SETTLE_SECONDS = 0.08
DEFAULT_DRAG_THRESHOLD_PIXELS = 4
MOUSE_SELECTION_SOURCE = "mouse_selection"
LOGGER_NAME = "desktop_translator"
SCREEN_CAPTURE_PROCESS_NAMES = frozenset(
    {
        "screenclippinghost.exe",
        "screensketch.exe",
        "snippingtool.exe",
    }
)


def _read_foreground_executable_name() -> str | None:
    """Read the foreground process name without coupling startup to Win32."""

    try:
        from app.selection.foreground import ForegroundApplicationDetector

        return ForegroundApplicationDetector().executable_name()
    except Exception:
        return None


def _read_foreground_snapshot() -> tuple[int | None, str | None]:
    """Capture foreground HWND/process metadata from one native window sample."""

    try:
        from app.selection.foreground import ForegroundApplicationDetector

        detector = ForegroundApplicationDetector()
        snapshot = getattr(detector, "snapshot", None)
        if callable(snapshot):
            hwnd, process_name = snapshot()
            return hwnd, process_name
        return detector.window_handle(), detector.executable_name()
    except Exception:
        return None, None


class MouseSelectionState(str, Enum):
    """States used while recognizing one left-button selection gesture."""

    IDLE = "idle"
    MOUSE_DOWN = "mouse_down"
    DRAGGING = "dragging"
    WAITING_DEBOUNCE = "waiting_debounce"
    CAPTURE_SELECTION = "capture_selection"


class MouseSelectionManager(QObject):
    """Emit one trigger after a stable left-button drag selection.

    The pynput listener owns its own background thread. Its callback performs
    only small state transitions. The foreground HWND/process and gesture
    coordinates are frozen at physical mouse-up, before Qt can show/hide any
    AITranslator window. A real settle interval is then scheduled on the Qt
    thread so Chromium/Electron/rich-text controls can commit their selection.
    """

    triggered = Signal(object)
    _capture_requested = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        config_manager: ConfigManager | Any | None = None,
        listener_factory: Callable[..., Any] | None = None,
        clock: Callable[[], float] | None = None,
        debounce_seconds: float | None = None,
        settle_seconds: float | None = None,
        drag_threshold_pixels: int = DEFAULT_DRAG_THRESHOLD_PIXELS,
        overlay_hit_test: Callable[[int, int], bool] | None = None,
        foreground_executable_reader: Callable[[], str | None] | None = None,
        foreground_snapshot_reader: Callable[
            [], tuple[int | None, str | None]
        ] | None = None,
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
        configured_settle = (
            settle_seconds
            if settle_seconds is not None
            else getattr(
                self.config_manager,
                "auto_selection_settle_seconds",
                DEFAULT_SELECTION_SETTLE_SECONDS,
            )
        )
        self._debounce_seconds = self._coerce_seconds(
            configured_debounce,
            DEFAULT_AUTO_SELECTION_DEBOUNCE_SECONDS,
        )
        self._settle_seconds = self._coerce_seconds(
            configured_settle,
            DEFAULT_SELECTION_SETTLE_SECONDS,
        )
        self._drag_threshold_pixels = max(1, int(drag_threshold_pixels))
        self._listener_factory = listener_factory or mouse.Listener
        self._clock = clock or monotonic
        self.logger = logger or logging.getLogger(LOGGER_NAME)
        self._overlay_hit_test = (
            overlay_hit_test
            if overlay_hit_test is not None
            else lambda _x, _y: False
        )
        self._foreground_executable_reader = (
            foreground_executable_reader or _read_foreground_executable_name
        )
        self._foreground_snapshot_reader = (
            foreground_snapshot_reader or _read_foreground_snapshot
        )

        self._lock = Lock()
        self._listener: Any | None = None
        self._state = MouseSelectionState.IDLE
        self._button_down = False
        self._ignored_gesture = False
        self._dragging = False
        self._press_position: tuple[int, int] | None = None
        self._last_trigger_at: float | None = None
        self._last_gesture_signature: tuple[int, int, int, int] | None = None
        self._capture_generation = 0
        self._capture_requested.connect(self._schedule_capture)

    @staticmethod
    def _coerce_seconds(value: object, fallback: float) -> float:
        try:
            seconds = float(value)
            if not math.isfinite(seconds):
                raise ValueError("seconds must be finite")
        except (TypeError, ValueError):
            seconds = fallback
        return max(0.0, seconds)

    @staticmethod
    def _coerce_debounce(value: object) -> float:
        """Compatibility wrapper retained for existing integrations/tests."""

        return MouseSelectionManager._coerce_seconds(
            value,
            DEFAULT_AUTO_SELECTION_DEBOUNCE_SECONDS,
        )

    def reconfigure(self, debounce_seconds: float | None = None) -> bool:
        """Apply the duplicate-event interval for future gestures."""

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
        """Return the configured duplicate-event suppression interval."""

        return self._debounce_seconds

    @property
    def settle_seconds(self) -> float:
        """Return the mouse-up selection stabilization interval."""

        return self._settle_seconds

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
            self._capture_generation += 1
            self._reset_gesture_locked()
            self._last_trigger_at = None
            self._last_gesture_signature = None

        try:
            listener.start()
        except Exception:
            with self._lock:
                self._listener = None
                self._capture_generation += 1
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
        """Stop the listener and discard pending/partial gestures."""

        with self._lock:
            listener = self._listener
            self._listener = None
            self._capture_generation += 1
            self._reset_gesture_locked()
            self._last_trigger_at = None
            self._last_gesture_signature = None

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
                self._capture_generation += 1
                self._reset_gesture_locked()
                self._last_trigger_at = None
                self._last_gesture_signature = None
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
                self._capture_generation += 1
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
            # A new physical selection supersedes a previous reply that is
            # still inside the short settle window.
            self._capture_generation += 1
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
        capture_payload: tuple[TranslationTriggerEvent, int] | None = None
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
            press_position = self._press_position
            self._button_down = False
            self._ignored_gesture = False
            self._dragging = False
            self._press_position = None

            if ignored or not dragged or press_position is None:
                self._state = MouseSelectionState.IDLE
                return

            now = self._clock()
            context = self._capture_selection_context(
                press_position,
                int(x),
                int(y),
                captured_at=now,
            )
            screen_capture_process = self._screen_capture_process_name(
                context.process_name
            )
            if screen_capture_process is not None:
                self._state = MouseSelectionState.IDLE
                self.logger.info(
                    "auto_selection_ignored screen_capture process=%s",
                    screen_capture_process,
                )
                return

            gesture_signature = (
                int(press_position[0]),
                int(press_position[1]),
                int(x),
                int(y),
            )
            # pynput/Windows can occasionally deliver a duplicate gesture
            # callback. Suppress only an *identical* gesture inside the
            # configured window. A fast drag over a different piece of text is
            # a new user action and must not be dropped merely because it
            # happened within 250 ms.
            if (
                self._last_trigger_at is not None
                and self._last_gesture_signature == gesture_signature
                and now - self._last_trigger_at < self._debounce_seconds
            ):
                self._state = MouseSelectionState.IDLE
                return

            self._last_trigger_at = now
            self._last_gesture_signature = gesture_signature
            self._capture_generation += 1
            generation = self._capture_generation
            self._state = MouseSelectionState.WAITING_DEBOUNCE
            event = TranslationTriggerEvent(
                hotkey=MOUSE_SELECTION_SOURCE,
                source=MOUSE_SELECTION_SOURCE,
                selection_context=context,
            )
            capture_payload = (event, generation)

        if capture_payload is None:
            return
        if self._settle_seconds <= 0:
            self._emit_settled_capture(*capture_payload)
            return
        # Emitting from pynput's thread to this QObject schedules the receiver
        # on the Qt thread, where QTimer is safe and tied to the GUI lifecycle.
        self._capture_requested.emit(capture_payload)

    def _capture_selection_context(
        self,
        press_position: tuple[int, int],
        release_x: int,
        release_y: int,
        *,
        captured_at: float,
    ) -> SelectionContext:
        """Freeze gesture/window routing metadata at the physical release."""

        hwnd: int | None = None
        process_name: str | None = None
        try:
            snapshot = self._foreground_snapshot_reader()
            if isinstance(snapshot, tuple) and len(snapshot) >= 2:
                raw_hwnd, raw_process = snapshot[0], snapshot[1]
                if raw_hwnd:
                    try:
                        hwnd = int(raw_hwnd)
                    except (TypeError, ValueError, OverflowError):
                        hwnd = None
                if raw_process:
                    process_name = str(raw_process)
        except Exception:
            pass

        # Preserve the older injectable executable reader for tests and
        # unusual platforms where only process-name detection is available.
        if not process_name:
            try:
                fallback_process = self._foreground_executable_reader()
            except Exception:
                fallback_process = None
            if fallback_process:
                process_name = str(fallback_process)

        return SelectionContext(
            press_x=int(press_position[0]),
            press_y=int(press_position[1]),
            release_x=int(release_x),
            release_y=int(release_y),
            foreground_hwnd=hwnd,
            process_name=process_name,
            captured_at=float(captured_at),
        )

    def _schedule_capture(self, payload: object) -> None:
        """Schedule selection capture after mouse-up state has settled."""

        try:
            event, generation = payload  # type: ignore[misc]
        except (TypeError, ValueError):
            return
        if not isinstance(event, TranslationTriggerEvent):
            return
        try:
            generation_value = int(generation)
        except (TypeError, ValueError):
            return
        delay_ms = max(0, round(self._settle_seconds * 1000))
        QTimer.singleShot(
            delay_ms,
            lambda current=event, token=generation_value: self._emit_settled_capture(
                current,
                token,
            ),
        )

    def _emit_settled_capture(
        self,
        event: TranslationTriggerEvent,
        generation: int,
    ) -> None:
        """Emit only if no newer mouse gesture invalidated this selection."""

        with self._lock:
            if (
                self._listener is None
                or generation != self._capture_generation
                or self._state != MouseSelectionState.WAITING_DEBOUNCE
            ):
                return
            self._state = MouseSelectionState.CAPTURE_SELECTION

        try:
            self.triggered.emit(event)
        finally:
            with self._lock:
                if (
                    generation == self._capture_generation
                    and self._state == MouseSelectionState.CAPTURE_SELECTION
                ):
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

    def _screen_capture_process_name(
        self,
        process_name: str | None = None,
    ) -> str | None:
        """Return a known Windows screen-capture foreground process name."""

        value = process_name
        if not value:
            try:
                value = self._foreground_executable_reader()
            except Exception:
                return None
        if not value:
            return None
        normalized = str(value).replace("\\", "/").rsplit("/", 1)[-1].casefold()
        if normalized in SCREEN_CAPTURE_PROCESS_NAMES:
            return normalized
        return None

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
    "DEFAULT_SELECTION_SETTLE_SECONDS",
    "MOUSE_SELECTION_SOURCE",
    "MouseSelectionManager",
    "MouseSelectionState",
    "SCREEN_CAPTURE_PROCESS_NAMES",
]
