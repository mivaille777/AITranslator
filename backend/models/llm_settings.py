"""Safe request and response contracts for local LLM configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AIProviderName = Literal["deepseek", "openai_compatible"]
CredentialStorage = Literal["credential_manager", "environment", "not_configured"]


class LLMProviderOption(BaseModel):
    id: AIProviderName
    label: str
    requires_base_url: bool
    default_model: str
    default_base_url: str


class LLMSettingsResponse(BaseModel):
    provider: AIProviderName
    model: str
    base_url: str
    api_key_configured: bool
    credential_storage: CredentialStorage
    providers: list[LLMProviderOption] = Field(default_factory=list)


class LLMSettingsUpdateRequest(BaseModel):
    provider: AIProviderName
    model: str = Field(min_length=1, max_length=256)
    base_url: str = Field(default="", max_length=2048)
    # Write-only: responses, logs and TOML configuration never include it.
    api_key: str | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False


__all__ = [
    "AIProviderName",
    "CredentialStorage",
    "LLMProviderOption",
    "LLMSettingsResponse",
    "LLMSettingsUpdateRequest",
]
