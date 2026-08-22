"""Versioned prompt registry shared by AITranslator AI services."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Iterable

from app.ai.errors import AIConfigurationError


@dataclass(frozen=True, slots=True)
class PromptSpec:
    name: str
    version: str
    system_prompt: str
    temperature: float
    max_tokens: int

    @property
    def prompt_id(self) -> str:
        return f"{self.name}@{self.version}"


class PromptRegistry:
    """Small immutable-by-default registry for prompt contracts.

    Prompt text remains code-reviewed source, while services address prompts by
    stable name/version. Runtime callers cannot provide arbitrary system prompts.
    """

    def __init__(self, prompts: Iterable[PromptSpec] = ()) -> None:
        self._lock = RLock()
        self._prompts: dict[tuple[str, str], PromptSpec] = {}
        self._latest: dict[str, str] = {}
        for prompt in prompts:
            self.register(prompt)

    def register(self, prompt: PromptSpec) -> None:
        name = str(prompt.name).strip()
        version = str(prompt.version).strip()
        if not name or not version or not str(prompt.system_prompt).strip():
            raise AIConfigurationError("Prompt name, version and system prompt are required.")
        if prompt.max_tokens <= 0:
            raise AIConfigurationError("Prompt max_tokens must be positive.")
        if not 0.0 <= float(prompt.temperature) <= 2.0:
            raise AIConfigurationError("Prompt temperature must be between 0 and 2.")
        key = (name, version)
        with self._lock:
            existing = self._prompts.get(key)
            if existing is not None and existing != prompt:
                raise AIConfigurationError(f"Prompt is already registered with different content: {name}@{version}")
            self._prompts[key] = prompt
            self._latest[name] = version

    def get(self, name: str, version: str | None = None) -> PromptSpec:
        normalized_name = str(name).strip()
        with self._lock:
            selected_version = str(version).strip() if version else self._latest.get(normalized_name, "")
            prompt = self._prompts.get((normalized_name, selected_version))
        if prompt is None:
            suffix = f"@{version}" if version else ""
            raise AIConfigurationError(f"Prompt is not registered: {normalized_name}{suffix}")
        return prompt

    def list_prompts(self) -> tuple[PromptSpec, ...]:
        with self._lock:
            return tuple(sorted(self._prompts.values(), key=lambda item: (item.name, item.version)))


__all__ = ["PromptRegistry", "PromptSpec"]
