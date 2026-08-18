"""Secret lookup and Windows Credential Manager persistence for AI providers."""

from __future__ import annotations

from collections.abc import Mapping
import importlib
import os
from typing import Any

from app.ai.errors import AIConfigurationError


CREDENTIAL_TARGET_PREFIX = "AITranslator/ai"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
OPENAI_COMPATIBLE_API_KEY_ENV = "OPENAI_API_KEY"
PROVIDER_ENV_VARS = {
    "deepseek": DEEPSEEK_API_KEY_ENV,
    "openai_compatible": OPENAI_COMPATIBLE_API_KEY_ENV,
}
SUPPORTED_SECRET_PROVIDERS = frozenset(PROVIDER_ENV_VARS)
_WINDOWS_CREDENTIAL_NOT_FOUND = 1168


def normalize_provider_name(provider: object) -> str:
    candidate = str(provider).strip().lower().replace("-", "_")
    if candidate not in SUPPORTED_SECRET_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_SECRET_PROVIDERS))
        raise AIConfigurationError(
            f"Unsupported AI provider credential namespace: {candidate or '<empty>'}. "
            f"Supported providers: {supported}."
        )
    return candidate


def _error_code(exc: BaseException) -> int | None:
    value = getattr(exc, "winerror", None)
    if isinstance(value, int):
        return value
    if exc.args and isinstance(exc.args[0], int):
        return int(exc.args[0])
    return None


def _decode_credential_blob(value: object) -> str:
    if isinstance(value, str):
        return value.rstrip("\x00")
    if isinstance(value, bytes):
        if not value:
            return ""
        try:
            decoded = value.decode("utf-16-le")
            if "\x00" not in decoded:
                return decoded.rstrip("\x00")
        except UnicodeDecodeError:
            pass
        try:
            return value.decode("utf-8").rstrip("\x00")
        except UnicodeDecodeError as exc:
            raise AIConfigurationError(
                "Stored AI credential could not be decoded."
            ) from exc
    return ""


class ProviderCredentialStore:
    """Persist provider API keys in the current user's Windows Credential Manager."""

    def __init__(self, backend: Any | None = None) -> None:
        self._backend = backend

    def _module(self) -> Any:
        if self._backend is not None:
            return self._backend
        try:
            return importlib.import_module("win32cred")
        except Exception as exc:
            raise AIConfigurationError(
                "Windows Credential Manager is unavailable."
            ) from exc

    @staticmethod
    def target_name(provider: object) -> str:
        normalized = normalize_provider_name(provider)
        return f"{CREDENTIAL_TARGET_PREFIX}/{normalized}"

    def get(self, provider: object) -> str | None:
        normalized = normalize_provider_name(provider)
        backend = self._module()
        try:
            credential = backend.CredRead(
                self.target_name(normalized),
                backend.CRED_TYPE_GENERIC,
                0,
            )
        except Exception as exc:
            if _error_code(exc) == _WINDOWS_CREDENTIAL_NOT_FOUND:
                return None
            raise AIConfigurationError(
                "Unable to read the stored AI provider credential."
            ) from exc

        if not isinstance(credential, Mapping):
            return None
        value = _decode_credential_blob(credential.get("CredentialBlob"))
        return value.strip() or None

    def set(self, provider: object, api_key: object) -> None:
        normalized = normalize_provider_name(provider)
        secret = str(api_key).strip()
        if not secret:
            self.delete(normalized)
            return

        backend = self._module()
        credential = {
            "Type": backend.CRED_TYPE_GENERIC,
            "TargetName": self.target_name(normalized),
            "UserName": normalized,
            "CredentialBlob": secret,
            "Comment": "AITranslator AI provider API key",
            "Persist": backend.CRED_PERSIST_LOCAL_MACHINE,
        }
        try:
            backend.CredWrite(credential, 0)
        except Exception as exc:
            raise AIConfigurationError(
                "Unable to save the AI provider credential."
            ) from exc

    def delete(self, provider: object) -> None:
        normalized = normalize_provider_name(provider)
        backend = self._module()
        try:
            backend.CredDelete(
                self.target_name(normalized),
                backend.CRED_TYPE_GENERIC,
                0,
            )
        except Exception as exc:
            if _error_code(exc) == _WINDOWS_CREDENTIAL_NOT_FOUND:
                return
            raise AIConfigurationError(
                "Unable to delete the stored AI provider credential."
            ) from exc


def get_provider_api_key(
    provider: object,
    explicit_api_key: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    credential_store: ProviderCredentialStore | Any | None = None,
) -> str:
    """Resolve an API key without ever writing it to the normal TOML config."""

    normalized = normalize_provider_name(provider)

    if explicit_api_key is not None and str(explicit_api_key).strip():
        return str(explicit_api_key).strip()

    store = credential_store or ProviderCredentialStore()
    try:
        stored = store.get(normalized)
    except AIConfigurationError:
        stored = None
    if isinstance(stored, str) and stored.strip():
        return stored.strip()

    source = os.environ if environ is None else environ
    env_name = PROVIDER_ENV_VARS[normalized]
    value = source.get(env_name, "")
    if isinstance(value, str) and value.strip():
        return value.strip()

    raise AIConfigurationError(
        f"API key for provider '{normalized}' is not configured. "
        "Open Settings -> AI model and API key, or set "
        f"{env_name} for the current process."
    )


def get_deepseek_api_key(
    explicit_api_key: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    credential_store: ProviderCredentialStore | Any | None = None,
) -> str:
    """Compatibility helper for the existing DeepSeek client."""

    return get_provider_api_key(
        "deepseek",
        explicit_api_key,
        environ=environ,
        credential_store=credential_store,
    )


__all__ = [
    "CREDENTIAL_TARGET_PREFIX",
    "DEEPSEEK_API_KEY_ENV",
    "OPENAI_COMPATIBLE_API_KEY_ENV",
    "PROVIDER_ENV_VARS",
    "ProviderCredentialStore",
    "SUPPORTED_SECRET_PROVIDERS",
    "get_deepseek_api_key",
    "get_provider_api_key",
    "normalize_provider_name",
]
