"""Provider interface and DeepSeek implementation for AI text operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Any

from app.ai.chunking import DEFAULT_CHUNK_SIZE, merge_chunks, split_text
from app.ai.client import DeepSeekClient
from app.ai.errors import AIConfigurationError, AIResponseError
from app.ai.models import AITextAction, AITextRequest, AITextResult
from app.ai.output_guard import validate_model_output
from app.ai.prompts import (
    build_polish_prompt,
    build_strict_retry_prompt,
    build_translate_prompt,
    normalize_polish_style,
)


TRANSLATE_TEMPERATURE = 0.1
POLISH_TEMPERATURE = 0.3
STRICT_RETRY_TEMPERATURE = 0.0
DEFAULT_AI_MAX_TOKENS = 4096


class AITextProvider(ABC):
    @abstractmethod
    def execute(self, request: AITextRequest) -> AITextResult:
        """Execute one AI text request."""


class DeepSeekTextProvider(AITextProvider):
    """Translate or polish text through :class:`DeepSeekClient`."""

    name = "deepseek"

    def __init__(
        self,
        client: DeepSeekClient | Any | None = None,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_tokens: int = DEFAULT_AI_MAX_TOKENS,
    ) -> None:
        self.client = client if client is not None else DeepSeekClient()
        self.chunk_size = int(chunk_size)
        self.max_tokens = int(max_tokens)

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

    def _prompts_for(self, request: AITextRequest) -> tuple[str, str, float, str]:
        if request.action is AITextAction.TRANSLATE:
            system_prompt, user_prompt = build_translate_prompt(request)
            return system_prompt, user_prompt, TRANSLATE_TEMPERATURE, request.style or "general"
        if request.action is AITextAction.POLISH:
            style = normalize_polish_style(request.style)
            system_prompt, user_prompt = build_polish_prompt(request)
            return system_prompt, user_prompt, POLISH_TEMPERATURE, style
        raise AIConfigurationError(f"Unsupported AI text action: {request.action!s}.")

    def _complete_once(self, request: AITextRequest) -> str:
        system_prompt, user_prompt, temperature, _style = self._prompts_for(request)
        raw = self.client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=self.max_tokens,
        )
        validation = validate_model_output(
            raw,
            source_text=request.source_text,
            action=request.action,
        )
        if validation.valid:
            return validation.text

        strict_system, strict_user = build_strict_retry_prompt(
            request,
            previous_failure=validation.reason,
        )
        retry_raw = self.client.complete(
            system_prompt=strict_system,
            user_prompt=strict_user,
            temperature=STRICT_RETRY_TEMPERATURE,
            max_tokens=self.max_tokens,
        )
        retry_validation = validate_model_output(
            retry_raw,
            source_text=request.source_text,
            action=request.action,
        )
        if retry_validation.valid:
            return retry_validation.text
        raise AIResponseError(
            f"DeepSeek provider returned unusable content after strict retry ({retry_validation.reason})."
        )

    def execute(self, request: AITextRequest) -> AITextResult:
        validated = self._validate_request(request)
        _system, _user, _temperature, style = self._prompts_for(validated)

        chunks = split_text(validated.source_text, max_chars=self.chunk_size)
        if not chunks:
            raise AIResponseError("DeepSeek provider received no usable text chunks.")

        outputs: list[str] = []
        for chunk in chunks:
            chunk_request = replace(validated, source_text=chunk)
            outputs.append(self._complete_once(chunk_request))

        output = merge_chunks(outputs)
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


__all__ = [
    "AITextProvider",
    "DEFAULT_AI_MAX_TOKENS",
    "DeepSeekTextProvider",
    "POLISH_TEMPERATURE",
    "STRICT_RETRY_TEMPERATURE",
    "TRANSLATE_TEMPERATURE",
]
