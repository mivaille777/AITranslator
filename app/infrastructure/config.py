"""Small TOML-backed configuration access layer."""

from __future__ import annotations

import math
import tomllib
from pathlib import Path
from typing import Any

from app.infrastructure.paths import (
    bundled_default_config_path,
    is_frozen_application,
    writable_config_dir,
)

DEFAULT_CONFIG_PATH = bundled_default_config_path()


class ConfigManager:
    """Load application settings and provide typed application defaults."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            with self.path.open("rb") as config_file:
                loaded = tomllib.load(config_file)
        except (OSError, tomllib.TOMLDecodeError):
            loaded = {}
        self._data = loaded if isinstance(loaded, dict) else {}

    def get(
        self,
        section: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Return a setting or its fallback when the setting is unavailable."""

        section_values = self._data.get(section, {})
        if not isinstance(section_values, dict):
            return default
        return section_values.get(key, default)

    def _first_value(
        self,
        candidates: tuple[tuple[str, str], ...],
        default: Any,
    ) -> Any:
        """Return the first configured value, preserving legacy key support."""

        missing = object()
        for section, key in candidates:
            value = self.get(section, key, missing)
            if value is not missing:
                return value
        return default

    @staticmethod
    def _coerce_bool(value: Any, fallback: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            return fallback
        if value is None:
            return fallback
        return bool(value)

    @property
    def hotkey(self) -> str:
        """Return the configured global hotkey in human-readable form."""

        value = self._first_value(
            (("trigger", "hotkey"), ("input", "hotkey")),
            "alt+q",
        )
        return str(value).strip() or "alt+q"

    @property
    def hotkey_debounce_seconds(self) -> float:
        """Return the duplicate-trigger suppression interval."""

        value = self._first_value(
            (("trigger", "debounce_ms"), ("input", "hotkey_debounce_ms")),
            250,
        )
        try:
            milliseconds = max(0.0, float(value))
        except (TypeError, ValueError):
            milliseconds = 250.0
        return milliseconds / 1000.0

    @property
    def auto_selection_enabled(self) -> bool:
        """Return whether mouse drag selection mode starts automatically."""

        legacy_value = self.get("input", "auto_selection_enabled", None)
        legacy_enabled = (
            self._coerce_bool(legacy_value, True)
            if legacy_value is not None
            else True
        )
        mode = self.get("trigger", "mode", None)
        if mode is None:
            return legacy_enabled
        normalized_mode = str(mode).strip().lower()
        if normalized_mode in {"auto", "both"}:
            return True
        if normalized_mode == "hotkey":
            return legacy_enabled
        return legacy_enabled

    @property
    def trigger_mode(self) -> str:
        """Return the safe trigger mode used by the settings page."""

        mode = self.get("trigger", "mode", None)
        if mode is None:
            return "auto" if self.auto_selection_enabled else "hotkey"
        normalized_mode = str(mode).strip().lower()
        if normalized_mode in {"hotkey", "auto", "both"}:
            if normalized_mode == "hotkey" and self._coerce_bool(
                self.get("input", "auto_selection_enabled", False),
                False,
            ):
                return "both"
            return normalized_mode
        return "hotkey"

    @property
    def auto_selection_debounce_seconds(self) -> float:
        """Return the duplicate mouse-selection suppression interval."""

        value = self._first_value(
            (
                ("trigger", "debounce_ms"),
                ("input", "auto_selection_debounce_ms"),
            ),
            250,
        )
        try:
            milliseconds = float(value)
            if not math.isfinite(milliseconds):
                raise ValueError("debounce must be finite")
            milliseconds = max(0.0, milliseconds)
        except (TypeError, ValueError):
            milliseconds = 250.0
        return milliseconds / 1000.0

    @property
    def overlay_position_mode(self) -> str:
        """Return the configured overlay placement mode."""

        value = self.get("overlay", "position_mode", "desktop_lyrics_bottom")
        return str(value).strip().lower() or "desktop_lyrics_bottom"

    @property
    def overlay_font_family(self) -> str:
        """Return the font family used by the translation Overlay."""

        value = self.get("overlay", "font_family", "Segoe UI")
        return str(value).strip() or "Segoe UI"

    @property
    def overlay_font_size(self) -> int:
        """Return a safe Overlay font size in logical pixels."""

        value = self.get("overlay", "font_size", 24)
        try:
            size = int(value)
        except (TypeError, ValueError):
            size = 24
        return min(200, max(8, size))

    @property
    def overlay_opacity(self) -> float:
        """Return the legacy Overlay opacity setting.

        New code should use ``overlay_background_opacity`` and
        ``overlay_text_opacity``. The legacy value is kept so older user
        configuration files and integrations continue to work.
        """

        return self._safe_overlay_opacity(self.get("overlay", "opacity", 1.0))

    @staticmethod
    def _safe_overlay_opacity(value: Any, fallback: float = 1.0) -> float:
        """Clamp an Overlay opacity to the supported range."""

        try:
            opacity = float(value)
            if not math.isfinite(opacity):
                raise ValueError("opacity must be finite")
        except (TypeError, ValueError):
            opacity = fallback
        return min(1.0, max(0.1, opacity))

    @property
    def overlay_background_opacity(self) -> float:
        """Return the independent opacity of the Overlay background."""

        value = self.get("overlay", "background_opacity", None)
        if value is None:
            value = self.overlay_opacity
        return self._safe_overlay_opacity(value)

    @property
    def overlay_text_opacity(self) -> float:
        """Return the independent opacity of the Overlay text."""

        return self._safe_overlay_opacity(
            self.get("overlay", "text_opacity", 1.0)
        )

    @property
    def overlay_max_width(self) -> int:
        """Return the bounded maximum Overlay width."""

        value = self.get("overlay", "max_width", 900)
        try:
            width = int(value)
        except (TypeError, ValueError):
            width = 900
        return min(10000, max(120, width))

    @property
    def overlay_locked(self) -> bool:
        """Return whether the Overlay should start in click-through mode."""

        return self._coerce_bool(self.get("overlay", "locked", False), False)

    @property
    def overlay_theme(self) -> str:
        """Return the safe Overlay palette selected by the user."""

        value = str(self.get("overlay", "theme", "dark")).strip().lower()
        aliases = {
            "dark": "dark",
            "soft": "soft",
            "dark_soft": "soft",
            "contrast": "contrast",
            "high_contrast": "contrast",
        }
        return aliases.get(value, "dark")

    @property
    def overlay_show_original(self) -> bool:
        """Return whether the source text should be visible by default."""

        return self._coerce_bool(
            self.get("overlay", "show_original", False),
            False,
        )

    @property
    def translation_source_language(self) -> str:
        """Return the configured source language or automatic detection."""

        value = self.get("translation", "source_language", "auto")
        return str(value).strip() or "auto"

    @property
    def google_web_enabled(self) -> bool:
        """Return whether the web-compatible backend is enabled."""

        return self._coerce_bool(self.get("google_web", "enabled", True), True)

    @property
    def google_web_endpoint(self) -> str:
        """Return the configurable web-compatible endpoint."""

        value = self.get(
            "google_web",
            "endpoint",
            "https://translate.google.com/translate_a/single",
        )
        endpoint = str(value).strip()
        if endpoint.startswith(("https://", "http://")):
            return endpoint
        return "https://translate.google.com/translate_a/single"

    @property
    def google_web_timeout_seconds(self) -> float:
        """Return the bounded web request timeout."""

        value = self.get("google_web", "timeout_ms", 8000)
        try:
            timeout_ms = float(value)
            if not math.isfinite(timeout_ms):
                raise ValueError("timeout must be finite")
        except (TypeError, ValueError):
            timeout_ms = 8000.0
        return min(60000.0, max(500.0, timeout_ms)) / 1000.0

    @property
    def google_web_max_retries(self) -> int:
        """Return the bounded number of web request retries."""

        value = self.get("google_web", "max_retries", 0)
        try:
            retries = int(value)
        except (TypeError, ValueError):
            retries = 0
        return min(3, max(0, retries))

    @property
    def google_web_min_interval_seconds(self) -> float:
        """Return the minimum interval between web requests."""

        value = self.get("google_web", "min_interval_ms", 0)
        try:
            interval_ms = float(value)
            if not math.isfinite(interval_ms):
                raise ValueError("interval must be finite")
        except (TypeError, ValueError):
            interval_ms = 0.0
        return min(60000.0, max(0.0, interval_ms)) / 1000.0

    @property
    def translation_target_language(self) -> str:
        """Return the configured target language."""

        value = self.get("translation", "target_language", "zh-CN")
        return str(value).strip() or "zh-CN"

    @property
    def overlay_position_margin(self) -> int:
        """Return the nonnegative overlay edge margin."""

        value = self.get("overlay", "margin", 24)
        try:
            margin = float(value)
            if not math.isfinite(margin):
                raise ValueError("margin must be finite")
            return max(0, int(margin))
        except (TypeError, ValueError):
            return 24

    @property
    def overlay_custom_position(self) -> tuple[int, int]:
        """Return the configured fixed overlay position."""

        return (
            self._safe_int(self.get("overlay", "custom_position_x", 80), 80),
            self._safe_int(self.get("overlay", "custom_position_y", 80), 80),
        )

    @property
    def overlay_mouse_offset(self) -> tuple[int, int]:
        """Return the cursor-to-overlay offset for mouse-follow mode."""

        return (
            self._safe_int(self.get("overlay", "mouse_offset_x", 16), 16),
            self._safe_int(self.get("overlay", "mouse_offset_y", 16), 16),
        )

    @staticmethod
    def _safe_int(value: Any, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @property
    def selection_uia_timeout_seconds(self) -> float:
        """Return the bounded UI Automation selection timeout."""

        value = self.get("selection", "uia_timeout_ms", 250)
        try:
            milliseconds = float(value)
            if not math.isfinite(milliseconds):
                raise ValueError("timeout must be finite")
            milliseconds = max(1.0, milliseconds)
        except (TypeError, ValueError):
            milliseconds = 250.0
        return milliseconds / 1000.0

    @property
    def translation_cache_enabled(self) -> bool:
        """Return whether successful translations should be cached."""

        value = self._first_value(
            (("cache", "enabled"), ("translation", "cache_enabled")),
            True,
        )
        return self._coerce_bool(value, True)

    @property
    def translation_cache_max_size(self) -> int:
        """Return the configured positive in-memory cache capacity."""

        value = self._first_value(
            (("cache", "max_size"), ("translation", "cache_max_size")),
            128,
        )
        try:
            size = int(value)
        except (TypeError, ValueError):
            size = 128
        return max(1, size)

    @property
    def translation_sqlite_cache_enabled(self) -> bool:
        """Return whether the optional SQLite L2 cache is enabled."""

        value = self._first_value(
            (
                ("cache", "sqlite_enabled"),
                ("translation", "sqlite_cache_enabled"),
            ),
            True,
        )
        return self._coerce_bool(value, True)

    @property
    def translation_cache_path(self) -> Path:
        """Return a safe path for the local SQLite cache database."""

        if is_frozen_application() or self.path == DEFAULT_CONFIG_PATH:
            default_path = writable_config_dir() / "translation_cache.sqlite3"
        else:
            default_path = self.path.parent / "translation_cache.sqlite3"
        value = self._first_value(
            (("cache", "sqlite_path"), ("translation", "sqlite_cache_path")),
            None,
        )
        if value is None or not str(value).strip():
            return default_path

        configured = Path(str(value).strip()).expanduser()
        if configured.is_absolute():
            return configured

        # The shipped value is workspace-relative (``config/...``), while a
        # custom test/config file conventionally keeps relative state beside
        # that file.  Handle both without ever using the current directory.
        parts = configured.parts
        config_parent = self.path.parent
        if is_frozen_application():
            # A PyInstaller bundle is read-only. Map both the shipped
            # config/cache.sqlite3 form and custom relative paths into
            # the per-user writable config directory.
            if parts and parts[0].lower() == config_parent.name.lower():
                return writable_config_dir().joinpath(*parts[1:])
            return writable_config_dir().joinpath(configured)
        if parts and parts[0].lower() == config_parent.name.lower():
            return config_parent.parent.joinpath(*parts)
        return config_parent.joinpath(configured)

    @property
    def translation_history_enabled(self) -> bool:
        """Return whether full source text may be persisted as history."""

        value = self._first_value(
            (
                ("cache", "history_enabled"),
                ("translation", "history_enabled"),
            ),
            False,
        )
        return self._coerce_bool(value, False)

    @property
    def translation_max_text_length(self) -> int:
        """Return the maximum normalized source text length."""

        value = self.get("translation", "max_text_length", 5000)
        try:
            length = int(value)
        except (TypeError, ValueError):
            length = 5000
        return max(1, length)
