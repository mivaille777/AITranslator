"""Provider interface and DeepSeek implementation for AI text operations."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from app.ai.client import DeepSeekClient
from app.ai.errors import AIConfigurationError, AIResponseError
from app.ai.models import AITextAction, AITextRequest, AITextResult
from app.ai.prompts import build_polish_prompt, build_translate_prompt, normalize_polish_style


TRANSLATE_TEMPERATURE = 0.1
POLISH_TEMPERATURE = 0.3


class AITextProvider(ABC):
    @abstractmethod
    def execute(self, request: AITextRequest) -> AITextResult:
        """Execute one AI text request."""


def _clean_model_output(content: str) -> str:
    """Remove common LLM wrapper artifacts before displaying user output."""

    text = content.strip()

    # Models occasionally return JSON envelopes even when asked for plain text.
    if text.startswith("{") and text.endswith("}"):
        import json
        try:
            data = json.loads(text)
            for key in ("translated_text", "translation", "output", "result", "text"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    break
        except Exception:
            pass

    # Remove markdown fences accidentally added by the model.
    text = re.sub(r"^```(?:text|json|markdown)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    return text.strip()


class DeepSeekTextProvider(AITextProvider):
    """Translate or polish text through :class:`DeepSeekClient`."""

    name = "deepseek"

    def __init__(self, client: DeepSeekClient | Any | None = None) -> None:
        self.client = client if client is not None else DeepSeekClient()

    @property
    def model(self) -> str:
        return str(getattr(self.client, "model", "unknown")).strip() or "unknown"

    @staticmethod
    def _validate_request(request: object) -> AITextRequest:
        if not isinstance(request, AITextRequest):
            raise AIConfigurationError("AI provider requires an AITextRequest.")
        if not request.source_text.strip():
            raise AIConfigurationError("AI source text must not be empty.")
        if not isinstance(request.action, AITextAction):
            raise AIConfigurationError("Unsupported AI text action.")
        return request

    def execute(self, request: AITextRequest) -> AITextResult:
        validated = self._validate_request(request)

        if validated.action is AITextAction.TRANSLATE:
            system_prompt, user_prompt = build_translate_prompt(validated)
            temperature = TRANSLATE_TEMPERATURE
            style = validated.style or "general"
        elif validated.action is AITextAction.POLISH:
            style = normalize_polish_style(validated.style)
            system_prompt, user_prompt = build_polish_prompt(validated)
            temperature = POLISH_TEMPERATURE
        else:
            raise AIConfigurationError(f"Unsupported AI text action: {validated.action!s}.")

        output = _clean_model_output(
            self.client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
        )
        if not output:
            raise AIResponseError("DeepSeek provider returned empty content.")

        return AITextResult(
            source_text=validated.source_text,
            output_text=output,
            action=validated.action,
            provider=self.name,
            model=self.model,
            source_language=validated.source_language,
            target_language=validated.target_language,
            style=style,
            request_id=validated.request_id,
        )

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()


__all__ = ["AITextProvider", "DeepSeekTextProvider", "POLISH_TEMPERATURE", "TRANSLATE_TEMPERATURE"]
