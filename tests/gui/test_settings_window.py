"""Qt coverage for the Step16 settings dialog."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.settings import SettingsManager
from app.ui.settings import SettingsWindow


def test_settings_window_saves_values_and_emits_overlay_preview(
    qapp,
    qtbot,
    tmp_path: Path,
) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    default_path.write_text(
        """
[translation]
source_language = "auto"
target_language = "zh-CN"

[trigger]
mode = "hotkey"
hotkey = "alt+q"
debounce_ms = 250

[overlay]
position_mode = "desktop_lyrics_bottom"
font_family = "Segoe UI"
font_size = 24
opacity = 1.0
max_width = 900
locked = false

[cache]
enabled = true
max_size = 128
""",
        encoding="utf-8",
    )
    manager = SettingsManager(default_path, user_path)
    window = SettingsWindow(manager)
    qtbot.addWidget(window)

    previews: list[dict[str, object]] = []
    window.preview_requested.connect(previews.append)
    window.target_language_edit.setText("en")
    window.font_size_spin.setValue(36)
    window.opacity_spin.setValue(0.75)
    window.position_mode_combo.setCurrentIndex(3)
    window.hotkey_edit.setText("ctrl+shift+t")
    assert window.save_settings()

    assert manager.translation_target_language == "en"
    assert manager.overlay_font_size == 36
    assert manager.overlay_opacity == 0.75
    assert manager.overlay_position_mode == "mouse_follow"
    assert manager.hotkey == "ctrl+shift+t"
    assert previews
    assert previews[-1]["font_size"] == 36
    assert user_path.exists()
