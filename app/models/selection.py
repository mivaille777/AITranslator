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

    press_x: int | None = None
    press_y: int | None = None
    release_x: int | None = None
    release_y: int | None = None
    foreground_hwnd: int | None = None
    process_name: str | None = None
    captured_at: float | None = None

    @property
    def press_point(self) -> tuple[int, int] | None:
        """Return the global mouse-press point when both coordinates exist."""

        if self.press_x is None or self.press_y is None:
            return None
        return int(self.press_x), int(self.press_y)

    @property
    def release_point(self) -> tuple[int, int] | None:
        """Return the global mouse-release point when both coordinates exist."""

        if self.release_x is None or self.release_y is None:
            return None
        return int(self.release_x), int(self.release_y)

    @property
    def drag_bounds(self) -> tuple[int, int, int, int] | None:
        """Return normalized global bounds for the drag gesture when available."""

        start = self.press_point
        end = self.release_point
        if start is None or end is None:
            return None
        return (
            min(start[0], end[0]),
            min(start[1], end[1]),
            max(start[0], end[0]),
            max(start[1], end[1]),
        )


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
