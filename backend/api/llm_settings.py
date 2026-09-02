"""Local-only API for configuring the active LLM provider and credential."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, status

from app.ai.client import SUPPORTED_DEEPSEEK_MODELS
from app.ai.errors import AIConfigurationError
from app.ai.factory import (
    AI_PROVIDER_LABELS,
    DEFAULT_AI_PROVIDER,
    OPENAI_COMPATIBLE_PROVIDER,
    SUPPORTED_AI_PROVIDERS,
    provider_defaults,
)
from app.ai.secrets import PROVIDER_ENV_VARS, ProviderCredentialStore
from app.infrastructure.settings import SettingsManager
from backend.api.dependencies import (
    close_agent_tool_registry,
    close_companion_chat_service,
    close_product_agent_service,
    close_quick_action_service,
)
from backend.api.llm_dependencies import reset_llm_dependencies
from backend.models.llm_settings import (
    LLMProviderOption,
    LLMSettingsResponse,
    LLMSettingsUpdateRequest,
)


router = APIRouter(prefix="/api/settings/llm", tags=["settings"])


def _config_value(settings: SettingsManager, key: str, default: str) -> str:
    return str(settings.get("ai", key, default) or default).strip()


def _credential_state(provider: str) -> tuple[bool, str]:
    try:
        if ProviderCredentialStore().get(provider):
            return True, "credential_manager"
    except AIConfigurationError:
        pass
    if os.getenv(PROVIDER_ENV_VARS[provider], "").strip():
        return True, "environment"
    return False, "not_configured"


def _provider_options() -> list[LLMProviderOption]:
    options: list[LLMProviderOption] = []
    for provider in SUPPORTED_AI_PROVIDERS:
        model, base_url = provider_defaults(provider)
        options.append(
            LLMProviderOption(
                id=provider,
                label=AI_PROVIDER_LABELS[provider],
                requires_base_url=provider == OPENAI_COMPATIBLE_PROVIDER,
                default_model=model,
                default_base_url=base_url,
            )
        )
    return options


def _response(settings: SettingsManager) -> LLMSettingsResponse:
    provider = _config_value(settings, "provider", DEFAULT_AI_PROVIDER)
    if provider not in SUPPORTED_AI_PROVIDERS:
        provider = DEFAULT_AI_PROVIDER
    default_model, default_base_url = provider_defaults(provider)
    configured, storage = _credential_state(provider)
    return LLMSettingsResponse(
        provider=provider,
        model=_config_value(settings, "model", default_model),
        base_url=_config_value(settings, "base_url", default_base_url),
        api_key_configured=configured,
        credential_storage=storage,
        providers=_provider_options(),
    )


def _validate(payload: LLMSettingsUpdateRequest) -> tuple[str, str, str]:
    provider = payload.provider
    model = payload.model.strip()
    base_url = payload.base_url.strip()
    if provider == DEFAULT_AI_PROVIDER:
        if model not in SUPPORTED_DEEPSEEK_MODELS:
            raise ValueError("请选择受支持的 DeepSeek 模型。")
        _, default_base_url = provider_defaults(provider)
        return provider, model, base_url or default_base_url
    if not base_url:
        raise ValueError("自定义 OpenAI-compatible 供应商需要 Base URL。")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Base URL 必须是完整的 http:// 或 https:// 地址。")
    return provider, model, base_url.rstrip("/")


def _refresh_runtime() -> None:
    # All affected factories are recreated lazily for the next request. This
    # avoids a backend restart while never exposing a credential to the client.
    close_product_agent_service()
    close_agent_tool_registry()
    close_quick_action_service()
    close_companion_chat_service()
    reset_llm_dependencies()


@router.get("", response_model=LLMSettingsResponse)
def get_llm_settings() -> LLMSettingsResponse:
    return _response(SettingsManager())


@router.put("", response_model=LLMSettingsResponse)
def update_llm_settings(payload: LLMSettingsUpdateRequest) -> LLMSettingsResponse:
    try:
        provider, model, base_url = _validate(payload)
        if payload.api_key is not None and not payload.api_key.strip() and not payload.clear_api_key:
            raise ValueError("API Key 不能为空；如需移除，请使用“清除已保存的 Key”。")

        settings = SettingsManager()
        settings.save({"ai": {"provider": provider, "model": model, "base_url": base_url}})

        credential_store = ProviderCredentialStore()
        if payload.clear_api_key:
            credential_store.delete(provider)
        elif payload.api_key is not None:
            credential_store.set(provider, payload.api_key)

        _refresh_runtime()
        return _response(SettingsManager())
    except (AIConfigurationError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


__all__ = ["router"]
