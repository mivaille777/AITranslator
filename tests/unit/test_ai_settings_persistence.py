from __future__ import annotations

from pathlib import Path

from app.infrastructure.settings import SettingsManager


def test_ai_provider_settings_persist_but_api_key_is_filtered(tmp_path: Path) -> None:
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    default_path.write_text(
        """
[ai]
provider = "deepseek"
model = "deepseek-v4-flash"
base_url = "https://api.deepseek.com"
""",
        encoding="utf-8",
    )
    manager = SettingsManager(default_path, user_path)

    manager.save(
        {
            "ai": {
                "provider": "openai_compatible",
                "model": "custom-model-v2",
                "base_url": "https://provider.example/v1",
                "api_key": "must-never-be-written",
            }
        }
    )

    saved_text = user_path.read_text(encoding="utf-8")
    assert '[ai]' in saved_text
    assert 'provider = "openai_compatible"' in saved_text
    assert 'model = "custom-model-v2"' in saved_text
    assert 'base_url = "https://provider.example/v1"' in saved_text
    assert "api_key" not in saved_text
    assert "must-never-be-written" not in saved_text

    reloaded = SettingsManager(default_path, user_path)
    assert reloaded.get("ai", "provider") == "openai_compatible"
    assert reloaded.get("ai", "model") == "custom-model-v2"
    assert reloaded.get("ai", "base_url") == "https://provider.example/v1"
