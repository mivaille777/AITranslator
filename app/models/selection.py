"""Selection data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SelectedText:
    """Text selected from the foreground application."""

    text: str
    provider: str = "clipboard"

    @property
    def value(self) -> str:
        """Alias useful to callers that treat the model as a value object."""

        return self.text
