"""Runtime model selection state for conversational Overlay UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatModelOption:
    provider: str
    model: str
    base_url: str = ""


class ChatModelSwitcher:
    def __init__(self, models: list[ChatModelOption] | None = None) -> None:
        self._models = list(models or [])
        self._current: ChatModelOption | None = self._models[0] if self._models else None

    @property
    def models(self) -> tuple[ChatModelOption, ...]:
        return tuple(self._models)

    @property
    def current(self) -> ChatModelOption | None:
        return self._current

    def set_models(self, models: list[ChatModelOption]) -> None:
        self._models = list(models)
        self._current = self._models[0] if self._models else None

    def select(self, provider: str, model: str) -> bool:
        for item in self._models:
            if item.provider == provider and item.model == model:
                self._current = item
                return True
        return False


__all__ = ["ChatModelOption", "ChatModelSwitcher"]
