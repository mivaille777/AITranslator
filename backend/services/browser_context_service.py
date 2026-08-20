from __future__ import annotations

from app.selection.browser_bridge import BrowserBridgeStatus, BrowserSelectionSnapshot
from app.selection.browser_page_bridge import BrowserPageSnapshot, BrowserReadingBridge
from app.selection.errors import SelectionError


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

    def latest_page(
        self,
        *,
        max_age_seconds: float = 120.0,
    ) -> BrowserPageSnapshot | None:
        try:
            return self.bridge.latest_page_snapshot(max_age_seconds=max_age_seconds)
        except SelectionError:
            return None
