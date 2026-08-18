"""Global hotkey input isolated from application and overlay behavior."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
import math
from time import monotonic
from typing import Any

from PySide6.QtCore import QObject, Signal
from pynput import keyboard

from app.infrastructure.config import ConfigManager
from app.models.events import TranslationTriggerEvent

DEFAULT_HOTKEY = "alt+q"
DEFAULT_DEBOUNCE_SECONDS = 0.25
RESERVED_COPY_HOTKEY = "ctrl+c"
LOGGER_NAME = "desktop_translator"

_MODIFIER_KEYS = {
    "alt": "<alt>",
    "alt_l": "<alt_l>",
    "alt_r": "<alt_r>",
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "ctrl_l": "<ctrl_l>",
    "ctrl_r": "<ctrl_r>",
    "shift": "<shift>",
    "shift_l": "<shift_l>",
    "shift_r": "<shift_r>",
    "cmd": "<cmd>",
    "cmd_l": "<cmd_l>",
    "cmd_r": "<cmd_r>",
    "win": "<cmd>",
}

_SPECIAL_KEYS = {
    "space": "<space>",
    "enter": "<enter>",
    "return": "<enter>",
    "tab": "<tab>",
    "esc": "<esc>",
    "escape": "<esc>",
    "backspace": "<backspace>",
    "delete": "<delete>",
}

_CONTROL_NAMES = {
    "ctrl",
    "control",
    "ctrl_l",
    "ctrl_r",
    "<ctrl>",
    "<ctrl_l>",
    "<ctrl_r>",
}


def is_reserved_copy_hotkey(value: object) -> bool:
    """Return whether ``value`` is the standard Ctrl+C copy chord."""

    parts = [part.strip().lower() for part in str(value).split("+") if part.strip()]
    if len(parts) != 2:
        return False
    return any(part in _CONTROL_NAMES for part in parts) and "c" in parts


def normalize_pynput_hotkey(value: str) -> str:
    """Convert ``alt+q``-style configuration into pynput notation."""

    parts = [part.strip().lower() for part in str(value).split("+") if part.strip()]
    if len(parts) < 2:
        raise ValueError("hotkey must contain at least a modifier and a key")
    if is_reserved_copy_hotkey(value):
        raise ValueError("Ctrl+C is reserved for the native copy shortcut")

    normalized: list[str] = []
    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            normalized.append(part)
        elif part in _MODIFIER_KEYS:
            normalized.append(_MODIFIER_KEYS[part])
        elif part in _SPECIAL_KEYS:
            normalized.append(_SPECIAL_KEYS[part])
        elif len(part) == 1:
            normalized.append(part)
        else:
            normalized.append(f"<{part}>")
    return "+".join(normalized)


class GlobalHotkeyManager(QObject):
    """Create one translation trigger for each configured hotkey action."""

    triggered = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        config_manager: ConfigManager | Any | None = None,
        listener_factory: Callable[[Mapping[str, Callable[[], None]]], Any]
        | None = None,
        clock: Callable[[], float] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(parent)

        self.config_manager = config_manager or ConfigManager()
        configured_hotkey = str(
            getattr(self.config_manager, "hotkey", DEFAULT_HOTKEY)
        ).strip() or DEFAULT_HOTKEY
        try:
            normalized_hotkey = normalize_pynput_hotkey(configured_hotkey)
        except (TypeError, ValueError):
            # Reserved/malformed user settings must never steal the native
            # Ctrl+C copy shortcut or prevent the tray app from starting.
            configured_hotkey = DEFAULT_HOTKEY
            normalized_hotkey = normalize_pynput_hotkey(configured_hotkey)
        self._configured_hotkey = configured_hotkey
        self._pynput_hotkey = normalized_hotkey
        self._debounce_seconds = self._read_debounce_seconds()
        self._listener_factory = listener_factory or keyboard.GlobalHotKeys
        self._clock = clock or monotonic
        self.logger = logger or logging.getLogger(LOGGER_NAME)
        self._listener: Any | None = None
        self._last_trigger_at: float | None = None

    @property
    def hotkey(self) -> str:
        """Return the configured hotkey string."""

        return self._configured_hotkey

    @property
    def pynput_hotkey(self) -> str:
        """Return the normalized pynput hotkey string."""

        return self._pynput_hotkey

    @property
    def is_running(self) -> bool:
        """Whether a listener is currently owned by this manager."""

        return self._listener is not None

    def _read_debounce_seconds(self) -> float:
        value = getattr(
            self.config_manager,
            "hotkey_debounce_seconds",
            DEFAULT_DEBOUNCE_SECONDS,
        )
        try:
            seconds = float(value)
            if not math.isfinite(seconds):
                raise ValueError("debounce must be finite")
            return max(0.0, seconds)
        except (TypeError, ValueError):
            return DEFAULT_DEBOUNCE_SECONDS

    def reconfigure(
        self,
        *,
        hotkey: str | None = None,
        debounce_seconds: float | None = None,
    ) -> bool:
        """Apply a new hotkey safely, restarting the listener when needed."""

        requested_hotkey = (
            str(
                getattr(
                    self.config_manager,
                    "hotkey",
                    self._configured_hotkey,
                )
            ).strip()
            if hotkey is None
            else str(hotkey).strip()
        ) or DEFAULT_HOTKEY
        try:
            normalized_hotkey = normalize_pynput_hotkey(requested_hotkey)
        except (TypeError, ValueError):
            return False

        if debounce_seconds is None:
            next_debounce = self._read_debounce_seconds()
        else:
            try:
                next_debounce = float(debounce_seconds)
                if not math.isfinite(next_debounce):
                    raise ValueError("debounce must be finite")
                next_debounce = max(0.0, next_debounce)
            except (TypeError, ValueError):
                return False

        previous = (
            self._configured_hotkey,
            self._pynput_hotkey,
            self._debounce_seconds,
        )
        was_running = self.is_running
        if was_running:
            self.stop()

        self._configured_hotkey = requested_hotkey
        self._pynput_hotkey = normalized_hotkey
        self._debounce_seconds = next_debounce
        if not was_running:
            return True

        try:
            self.start()
        except Exception:
            self._configured_hotkey, self._pynput_hotkey, self._debounce_seconds = previous
            try:
                self.start()
            except Exception:
                pass
            return False
        return True

    def start(self) -> bool:
        """Start the global listener once and return whether it is active."""

        if self._listener is not None:
            return True

        listener = self._listener_factory({self._pynput_hotkey: self._on_hotkey})
        try:
            listener.start()
        except Exception:
            stop = getattr(listener, "stop", None)
            if callable(stop):
                stop()
            raise

        self._listener = listener
        self._last_trigger_at = None
        return True

    def stop(self) -> None:
        """Stop and release the global listener; safe to call repeatedly."""

        listener = self._listener
        self._listener = None
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

        listener = self._listener
        if listener is None:
            return False
        is_alive = getattr(listener, "is_alive", None)
        if not callable(is_alive):
            # Lightweight fakes and older pynput-compatible adapters do not
            # expose an is_alive method; ownership is enough for them.
            return True
        try:
            alive = bool(is_alive())
        except Exception as exc:
            self.logger.error(
                "global_hotkey_health_check_failed error_type=%s",
                type(exc).__name__,
                exc_info=self._safe_exception_info(exc),
            )
            return False
        if alive:
            return True

        self._listener = None
        self._last_trigger_at = None
        try:
            self.start()
        except Exception as exc:
            self.logger.error(
                "global_hotkey_recovery_failed error_type=%s",
                type(exc).__name__,
                exc_info=self._safe_exception_info(exc),
            )
            return False
        self.logger.info("global_hotkey_recovered hotkey=%s", self.hotkey)
        return True

    def _on_hotkey(self) -> None:
        try:
            now = self._clock()
            if (
                self._last_trigger_at is not None
                and now - self._last_trigger_at < self._debounce_seconds
            ):
                return

            self._last_trigger_at = now
            self.triggered.emit(
                TranslationTriggerEvent(
                    hotkey=self._configured_hotkey,
                )
            )
        except Exception as exc:
            # Never allow a callback exception to terminate pynput's hook
            # thread or take down the Qt application.
            self.logger.error(
                "global_hotkey_callback_failed error_type=%s",
                type(exc).__name__,
                exc_info=self._safe_exception_info(exc),
            )

    @staticmethod
    def _safe_exception_info(exc: BaseException):
        try:
            safe_exception = type(exc)(type(exc).__name__)
        except Exception:
            safe_exception = RuntimeError(type(exc).__name__)
        return type(safe_exception), safe_exception, exc.__traceback__


__all__ = [
    "DEFAULT_DEBOUNCE_SECONDS",
    "DEFAULT_HOTKEY",
    "GlobalHotkeyManager",
    "RESERVED_COPY_HOTKEY",
    "is_reserved_copy_hotkey",
    "normalize_pynput_hotkey",
]
