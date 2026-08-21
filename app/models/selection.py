"""Selection data models."""

from __future__ import annotations

from dataclasses import dataclass, field


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


@dataclass(frozen=True, slots=True)
class DocumentIdentity:
    """Best-effort identity for the document behind a text selection.

    ``resource_path`` is local-only metadata.  It is intentionally kept
    separate from ``resource_url`` so downstream prompt builders can include a
    remote URL without accidentally sending a private local filesystem path to
    an LLM provider.
    """

    source_kind: str = ""
    resource_url: str = ""
    resource_title: str = ""
    resource_path: str = ""
    application: str = ""
    page_number: int | None = None

    @property
    def has_identity(self) -> bool:
        return bool(
            self.source_kind
            or self.resource_url
            or self.resource_title
            or self.resource_path
            or self.application
            or self.page_number is not None
        )

    @property
    def local_locator(self) -> str:
        """Return the local file locator without exposing it as a web URL."""

        return self.resource_path


@dataclass(frozen=True, slots=True)
class ReadingSelection:
    """Selected text plus bounded, source-neutral document context.

    Providers may return this richer model when reliable metadata exists.  The
    legacy :class:`SelectedText` contract remains valid and can always be
    reconstructed through ``selected_text``.
    """

    text: str
    provider: str = "clipboard"
    document: DocumentIdentity = field(default_factory=DocumentIdentity)
    section_heading: str = ""
    context_before: str = ""
    context_after: str = ""

    @property
    def selected_text(self) -> SelectedText:
        return SelectedText(text=self.text, provider=self.provider)

    @property
    def nearby_context(self) -> str:
        parts = (self.context_before, self.text, self.context_after)
        return " ".join(part for part in parts if part).strip()


__all__ = [
    "DocumentIdentity",
    "ReadingSelection",
    "SelectedText",
    "SelectionContext",
]
