"""Selection data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SelectionContext:
    """Immutable context captured around one external text-selection gesture.

    The context deliberately contains only non-sensitive routing metadata. It
    lets native providers resolve the exact window/control involved in the
    gesture without manufacturing keyboard input or relying solely on whatever
    control happens to own focus a few milliseconds later.
    """

    release_x: int | None = None
    release_y: int | None = None
    foreground_hwnd: int | None = None
    process_name: str | None = None

    @property
    def release_point(self) -> tuple[int, int] | None:
        """Return the global mouse-release point when both coordinates exist."""

        if self.release_x is None or self.release_y is None:
            return None
        return int(self.release_x), int(self.release_y)


@dataclass(frozen=True, slots=True)
class SelectedText:
    """Text selected from the foreground application."""

    text: str
    provider: str = "clipboard"

    @property
    def value(self) -> str:
        """Alias useful to callers that treat the model as a value object."""

        return self.text


__all__ = ["SelectedText", "SelectionContext"]
