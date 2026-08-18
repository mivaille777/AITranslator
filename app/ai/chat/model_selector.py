"""Runtime chat model switching abstraction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatModelOption:
    provider: str
    model: str
    label: str


class ChatModelSelector:
    """Available model registry used by the Overlay model switcher."""

    def __init__(self, options: list[ChatModelOption] | None = None) -> None:
        self.options = options or []
        self.current: ChatModelOption | None = self.options[0] if self.options else None

    def select(self, provider: str, model: str) -> bool:
        for option in self.options:
            if option.provider == provider and option.model == model:
                self.current = option
                return True
        return False

    def add(self, option: ChatModelOption) -> None:
        self.options.append(option)


__all__ = ["ChatModelOption", "ChatModelSelector"]
