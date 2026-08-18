from __future__ import annotations

from pathlib import Path

from app.infrastructure.settings import SettingsManager
from app.ui.settings import SettingsWindow


class FakeCredentialStore:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = dict(values or {})

    def get(self, provider: str):
        return self.values.get(provider)

    def set(self, provider: str, api_key: str) -> None:
        if api_key:
            self.values[provider] = api_key
        else:
            self.values.pop(provider, None)


def _manager(tmp_path: Path) -> SettingsManager:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    default_path.write_text(
        """
[translation]
source_language = "auto"
target_language = "zh-CN"

[ai]
provider = "deepseek"
model = "deepseek-v4-flash"
base_url = "https://api.deepseek.com"

[trigger]
mode = "hotkey"
hotkey = "alt+q"
debounce_ms = 250

[overlay]
position_mode = "desktop_lyrics_bottom"
font_family = "Segoe UI"
font_size = 24
opacity = 1.0
background_opacity = 1.0
text_opacity = 1.0
max_width = 900
locked = false
show_original = false

[cache]
enabled = true
max_size = 128
sqlite_enabled = false
history_enabled = false
""",
        encoding="utf-8",
    )
    return SettingsManager(default_path, user_path)


def test_settings_window_persists_provider_and_secure_api_key(
    qapp,
    qtbot,
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path)
    store = FakeCredentialStore({"deepseek": "deepseek-saved"})
    window = SettingsWindow(manager, credential_store=store)
    qtbot.addWidget(window)

    assert window.ai_provider_combo.currentData() == "deepseek"
    assert window.ai_api_key_edit.text() == "deepseek-saved"
    assert window.ai_api_key_edit.echoMode() == window.ai_api_key_edit.EchoMode.Password

    index = window.ai_provider_combo.findData("openai_compatible")
    window.ai_provider_combo.setCurrentIndex(index)
    window.ai_model_combo.setCurrentText("custom-model-v3")
    window.ai_base_url_edit.setText("https://provider.example/v1")
    window.ai_api_key_edit.setText("custom-secret")

    assert window.save_settings()

    assert manager.get("ai", "provider") == "openai_compatible"
    assert manager.get("ai", "model") == "custom-model-v3"
    assert manager.get("ai", "base_url") == "https://provider.example/v1"
    assert store.values["openai_compatible"] == "custom-secret"

    saved_text = manager.user_path.read_text(encoding="utf-8")
    assert "custom-secret" not in saved_text
    assert "api_key" not in saved_text

    reloaded = SettingsManager(manager.default_path, manager.user_path)
    second = SettingsWindow(reloaded, credential_store=store)
    qtbot.addWidget(second)

    assert second.ai_provider_combo.currentData() == "openai_compatible"
    assert second.ai_model_combo.currentText() == "custom-model-v3"
    assert second.ai_base_url_edit.text() == "https://provider.example/v1"
    assert second.ai_api_key_edit.text() == "custom-secret"
