"""Code-owned LLM routing for AITranslator AI workloads."""

from __future__ import annotations

from dataclasses import dataclass
import os

from app.ai.client import DeepSeekClient, DEFAULT_DEEPSEEK_MODEL, SUPPORTED_DEEPSEEK_MODELS
from app.ai.errors import AIConfigurationError
from app.ai.provider import DeepSeekTextProvider
from app.ai.service import AITextService


@dataclass(frozen=True, slots=True)
class LLMRoute:
    role: str
    provider: str
    model: str
    thinking_enabled: bool = False


_DEFAULT_MODELS = {
    "planner": "deepseek-v4-flash",
    "agent_synthesis": "deepseek-v4-pro",
    "reading": "deepseek-v4-pro",
    "translation_ai": DEFAULT_DEEPSEEK_MODEL,
    "polish": DEFAULT_DEEPSEEK_MODEL,
}
_ENV_BY_ROLE = {
    "planner": "AITRANS_MODEL_PLANNER",
    "agent_synthesis": "AITRANS_MODEL_AGENT_SYNTHESIS",
    "reading": "AITRANS_MODEL_READING",
    "translation_ai": "AITRANS_MODEL_TRANSLATION_AI",
    "polish": "AITRANS_MODEL_POLISH",
}


class LLMGateway:
    """Resolve model routes from a code-side allowlist.

    The current implementation intentionally supports only the existing
    DeepSeek provider. The boundary is role-based so additional providers can
    be added later without allowing prompts or model output to choose a route.
    """

    def route(self, role: str) -> LLMRoute:
        normalized = str(role or "").strip().lower()
        if normalized not in _DEFAULT_MODELS:
            raise AIConfigurationError(f"Unsupported LLM route role: {normalized or '<empty>'}.")
        configured = os.getenv(_ENV_BY_ROLE[normalized], "").strip()
        model = configured or _DEFAULT_MODELS[normalized]
        if model not in SUPPORTED_DEEPSEEK_MODELS:
            supported = ", ".join(sorted(SUPPORTED_DEEPSEEK_MODELS))
            raise AIConfigurationError(
                f"Unsupported model for LLM route {normalized}: {model}. Supported models: {supported}."
            )
        return LLMRoute(
            role=normalized,
            provider="deepseek",
            model=model,
            thinking_enabled=False,
        )

    def create_text_service(self, role: str) -> AITextService:
        route = self.route(role)
        client = DeepSeekClient(
            model=route.model,
            thinking_enabled=route.thinking_enabled,
        )
        return AITextService(DeepSeekTextProvider(client=client))

    def describe_routes(self) -> tuple[LLMRoute, ...]:
        return tuple(self.route(role) for role in _DEFAULT_MODELS)


__all__ = ["LLMGateway", "LLMRoute"]
