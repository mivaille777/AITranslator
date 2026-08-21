from app.infrastructure.settings import SettingsManager
from app.translation.manager import TranslationManager
from backend.services.translation_service import TranslationService


def test_translation_provider_selection_persists_across_service_restart(tmp_path):
    default_path = tmp_path / "default.toml"
    user_path = tmp_path / "user.toml"
    default_path.write_text(
        """
[translation]
provider = "google_web"
source_language = "auto"
target_language = "zh-CN"

[cache]
enabled = false
sqlite_enabled = false
history_enabled = false
""".strip()
        + "\n",
        encoding="utf-8",
    )

    settings = SettingsManager(default_path=default_path, user_path=user_path)
    manager = TranslationManager(config_manager=settings, sqlite_enabled=False)
    service = TranslationService(manager)

    try:
        assert service.provider_name == "google_web"
        assert service.select_provider("youdao") == "youdao_web"
        assert settings.get("translation", "provider") == "youdao_web"
        assert 'provider = "youdao_web"' in user_path.read_text(encoding="utf-8")
    finally:
        service.close()

    reloaded_settings = SettingsManager(default_path=default_path, user_path=user_path)
    reloaded_manager = TranslationManager(
        config_manager=reloaded_settings,
        sqlite_enabled=False,
    )
    reloaded_service = TranslationService(reloaded_manager)

    try:
        assert reloaded_service.provider_name == "youdao_web"
    finally:
        reloaded_service.close()
