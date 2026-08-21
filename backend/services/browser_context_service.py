from __future__ import annotations

from app.ai.chat.models import ReadingContext
from app.models.selection import ReadingSelection
from app.selection.browser_bridge import BrowserBridgeStatus, BrowserSelectionSnapshot
from app.selection.browser_page_bridge import BrowserPageSnapshot, BrowserReadingBridge
from app.selection.errors import SelectionError
from app.selection.reading_context import (
    browser_snapshot_to_reading_selection,
    reading_selection_to_context,
)


class BrowserContextService:
    """Application boundary around the existing browser selection bridge."""

    def __init__(self, bridge: BrowserReadingBridge | None = None) -> None:
        self.bridge = bridge or BrowserReadingBridge()

    def start(self) -> bool:
        return self.bridge.start()

    def close(self) -> None:
        self.bridge.stop()

    def status(self) -> BrowserBridgeStatus:
        return self.bridge.status_snapshot()

    def latest_selection(
        self,
        *,
        max_age_seconds: float = 30.0,
    ) -> BrowserSelectionSnapshot | None:
        try:
            return self.bridge.latest_snapshot(max_age_seconds=max_age_seconds)
        except SelectionError:
            return None

    def latest_reading_selection(
        self,
        *,
        max_age_seconds: float = 30.0,
        process_name: str = "",
    ) -> ReadingSelection | None:
        """Return the latest DOM selection through the Stage 6C rich model."""

        snapshot = self.latest_selection(max_age_seconds=max_age_seconds)
        if snapshot is None:
            return None
        return browser_snapshot_to_reading_selection(
            snapshot,
            process_name=process_name,
        )

    def latest_reading_context(
        self,
        *,
        max_age_seconds: float = 30.0,
        process_name: str = "",
    ) -> ReadingContext | None:
        """Return prompt-safe browser reading metadata when a selection exists."""

        selection = self.latest_reading_selection(
            max_age_seconds=max_age_seconds,
            process_name=process_name,
        )
        if selection is None:
            return None
        return reading_selection_to_context(selection)

    def latest_page(
        self,
        *,
        max_age_seconds: float = 120.0,
    ) -> BrowserPageSnapshot | None:
        try:
            return self.bridge.latest_page_snapshot(max_age_seconds=max_age_seconds)
        except SelectionError:
            return None
