from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import create_app


class _FakeSettings:
    values = {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
    }
    saved: list[dict[str, object]] = []

    def get(self, section: str, key: str, default=None):
        assert section == "ai"
        return self.values.get(key, default)

    def save(self, payload: dict[str, dict[str, str]]):
        self.values.update(payload["ai"])
        self.saved.append(payload)
        return {"ai": dict(self.values)}


class _FakeCredentialStore:
    values: dict[str, str] = {}

    def get(self, provider: str) -> str | None:
        return self.values.get(provider)

    def set(self, provider: str, key: str) -> None:
        self.values[provider] = key

    def delete(self, provider: str) -> None:
        self.values.pop(provider, None)


def test_llm_settings_api_persists_non_secret_config_and_hides_key(monkeypatch) -> None:
    from backend.api import llm_settings

    _FakeSettings.values = {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
    }
    _FakeSettings.saved = []
    _FakeCredentialStore.values = {}
    monkeypatch.setattr(llm_settings, "SettingsManager", _FakeSettings)
    monkeypatch.setattr(llm_settings, "ProviderCredentialStore", _FakeCredentialStore)
    monkeypatch.setattr(llm_settings, "_refresh_runtime", lambda: None)
    client = TestClient(create_app())

    response = client.put(
        "/api/settings/llm",
        json={
            "provider": "openai_compatible",
            "model": "gpt-test",
            "base_url": "https://gateway.example/v1/",
            "api_key": "local-secret",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "openai_compatible"
    assert body["model"] == "gpt-test"
    assert body["base_url"] == "https://gateway.example/v1"
    assert body["api_key_configured"] is True
    assert body["credential_storage"] == "credential_manager"
    assert "local-secret" not in response.text
    assert _FakeCredentialStore.values == {"openai_compatible": "local-secret"}
    assert _FakeSettings.saved[-1]["ai"] == {
        "provider": "openai_compatible",
        "model": "gpt-test",
        "base_url": "https://gateway.example/v1",
    }


def test_llm_settings_api_requires_valid_custom_base_url(monkeypatch) -> None:
    from backend.api import llm_settings

    monkeypatch.setattr(llm_settings, "SettingsManager", _FakeSettings)
    monkeypatch.setattr(llm_settings, "ProviderCredentialStore", _FakeCredentialStore)
    monkeypatch.setattr(llm_settings, "_refresh_runtime", lambda: None)
    client = TestClient(create_app())

    response = client.put(
        "/api/settings/llm",
        json={
            "provider": "openai_compatible",
            "model": "gpt-test",
            "base_url": "localhost:11434",
        },
    )

    assert response.status_code == 422
    assert "Base URL" in response.json()["detail"]
