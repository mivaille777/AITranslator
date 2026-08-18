"""Secret lookup helpers for AI providers.

Secrets are intentionally read from process-local sources instead of the normal
TOML settings layer. Persistent credential storage is added in a later stage.
"""

from __future__ import annotations

from collections.abc import Mapping
import os

from app.ai.errors import AIConfigurationError


DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"


def get_deepseek_api_key(
    explicit_api_key: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return a DeepSeek API key without persisting or logging it."""

    if explicit_api_key is not None and str(explicit_api_key).strip():
        return str(explicit_api_key).strip()

    source = os.environ if environ is None else environ
    value = source.get(DEEPSEEK_API_KEY_ENV, "")
    if isinstance(value, str) and value.strip():
        return value.strip()

    raise AIConfigurationError(
        f"DeepSeek API key is not configured; set {DEEPSEEK_API_KEY_ENV}."
    )


__all__ = ["DEEPSEEK_API_KEY_ENV", "get_deepseek_api_key"]
