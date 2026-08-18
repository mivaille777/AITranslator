"""Unit tests for Step16 configuration merging and persistence."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.settings import SettingsManager


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_defaults_and_user_values_are_merged_recursively(tmp_path: Path) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    _write(
        default_path,
        """
[translation]
source_language = "auto"
target_language = "zh-CN"

[overlay]
font_family = "Segoe UI"
font_size = 24
opacity = 1.0
""",
    )
    _write(
        user_path,
        """
[translation]
target_language = "en"

[overlay]
font_size = 32
""",
    )

    manager = SettingsManager(default_path, user_path)

    assert manager.translation_source_language == "auto"
    assert manager.translation_target_language == "en"
    assert manager.overlay_font_family == "Segoe UI"
    assert manager.overlay_font_size == 32
    assert manager.overlay_opacity == 1.0


def test_missing_or_invalid_values_fall_back_without_crashing(tmp_path: Path) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    _write(
        default_path,
        """
[trigger]
hotkey = "alt+q"
mode = "hotkey"
debounce_ms = 250

[overlay]
font_size = 24
opacity = 1.0
max_width = 900

[cache]
enabled = true
max_size = 128
""",
    )
    _write(
        user_path,
        """
[trigger]
hotkey = "not-a-hotkey"
mode = "unsupported"
debounce_ms = "invalid"

[overlay]
font_size = -2
opacity = nan
max_width = -1

[cache]
max_size = "invalid"
""",
    )

    manager = SettingsManager(default_path, user_path)

    assert manager.hotkey == "not-a-hotkey"
    assert manager.trigger_mode == "hotkey"
    assert manager.hotkey_debounce_seconds == 0.25
    assert manager.overlay_font_size == 8
    assert manager.overlay_opacity == 1.0
    assert manager.overlay_max_width == 120
    assert manager.translation_cache_max_size == 128


def test_save_reload_and_sensitive_value_filtering(tmp_path: Path) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    _write(default_path, "[translation]\ntarget_language = \"zh-CN\"\n")
    manager = SettingsManager(default_path, user_path)

    manager.save(
        {
            "translation": {"target_language": "en"},
            "overlay": {"font_size": 30},
            "credentials": {"access_token": "must-not-be-written"},
        }
    )

    saved_text = user_path.read_text(encoding="utf-8")
    assert "credentials" not in saved_text
    assert "must-not-be-written" not in saved_text

    reloaded = SettingsManager(default_path, user_path)
    assert reloaded.translation_target_language == "en"
    assert reloaded.overlay_font_size == 30


def test_malformed_user_toml_uses_defaults(tmp_path: Path) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    _write(default_path, "[translation]\ntarget_language = \"zh-CN\"\n")
    _write(user_path, "[translation\nthis is malformed")

    manager = SettingsManager(default_path, user_path)

    assert manager.translation_target_language == "zh-CN"


def test_legacy_opacity_becomes_background_opacity(tmp_path: Path) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    _write(
        default_path,
        """
[overlay]
opacity = 1.0
background_opacity = 1.0
text_opacity = 1.0
""",
    )
    _write(user_path, "[overlay]\nopacity = 0.35\n")

    manager = SettingsManager(default_path, user_path)

    assert manager.overlay_opacity == 0.35
    assert manager.overlay_background_opacity == 0.35
    assert manager.overlay_text_opacity == 1.0

    # Saving a different field must not silently restore the shipped
    # background default while the legacy user value is still present.
    manager.save({"overlay": {"text_opacity": 0.6}})
    assert manager.overlay_background_opacity == 0.35
