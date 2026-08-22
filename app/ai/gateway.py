"""Code-owned LLM routing for AITranslator AI workloads."""

from __future__ import annotations

from dataclasses import dataclass
import os
from threading import RLock
from typing import Any

from app.ai.client import DeepSeekClient, DEFAULT_DEEPSEEK_MODEL, SUPPORTED_DEEPSEEK_MODELS
from app.ai.errors import AIConfigurationError
from app.ai.models import AITextRequest, AITextResult
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


class RoutedAITextService:
    """Lazy AITextService facade bound to one immutable LLM route."""

    def __init__(self, route: LLMRoute) -> None:
        self.route = route
        self._service: AITextService | None = None
        self._lock = RLock()

    def _ensure(self) -> AITextService:
        if self._service is not None:
            return self._service
        with self._lock:
            if self._service is None:
                client = DeepSeekClient(
                    model=self.route.model,
                    thinking_enabled=self.route.thinking_enabled,
                )
                self._service = AITextService(DeepSeekTextProvider(client=client))
            return self._service

    @property
    def provider_name(self) -> str:
        return self.route.provider

    @property
    def model(self) -> str:
        return self.route.model

    @property
    def provider(self) -> Any:
        return self._ensure().provider

    def execute(self, request: AITextRequest) -> AITextResult:
        return self._ensure().execute(request)

    def translate(self, *args: Any, **kwargs: Any) -> AITextResult:
        return self._ensure().translate(*args, **kwargs)

    def polish(self, *args: Any, **kwargs: Any) -> AITextResult:
        return self._ensure().polish(*args, **kwargs)

    def close(self) -> None:
        with self._lock:
            service = self._service
            self._service = None
        if service is not None:
            service.close()


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

    def create_text_service(self, role: str) -> RoutedAITextService:
        return RoutedAITextService(self.route(role))

    def describe_routes(self) -> tuple[LLMRoute, ...]:
        return tuple(self.route(role) for role in _DEFAULT_MODELS)


__all__ = ["LLMGateway", "LLMRoute", "RoutedAITextService"]
