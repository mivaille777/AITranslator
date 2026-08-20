from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.selection import SelectionContext
from app.selection.browser_page_bridge import BrowserPageSnapshot, BrowserReadingBridge
from app.selection.errors import SelectionError


@dataclass
class FakeClock:
    value: float = 0.0

    def __call__(self) -> float:
        return self.value


def test_page_payload_is_valid_without_selected_text() -> None:
    clock = FakeClock(10.0)
    bridge = BrowserReadingBridge(clock=clock)

    snapshot = bridge.ingest_payload(
        {
            "version": 1,
            "type": "page",
            "url": "https://example.com/paper",
            "title": "Paper title",
            "heading": "Introduction",
        }
    )

    assert isinstance(snapshot, BrowserPageSnapshot)
    assert bridge.latest_page_snapshot().url == "https://example.com/paper"
    assert bridge.latest_page_snapshot().title == "Paper title"


def test_selection_payload_refreshes_page_and_keeps_selection_contract() -> None:
    clock = FakeClock(20.0)
    bridge = BrowserReadingBridge(clock=clock)

    bridge.ingest_payload(
        {
            "version": 1,
            "type": "selection",
            "text": "selected sentence",
            "url": "https://example.com/new-page",
            "title": "New page",
            "heading": "Methods",
        }
    )

    assert bridge.latest_page_snapshot().title == "New page"
    assert bridge.get_selected_text_with_context(
        SelectionContext(process_name="chrome.exe", captured_at=19.9)
    ).text == "selected sentence"


def test_stale_page_context_is_rejected_independently_of_selection_age() -> None:
    clock = FakeClock(30.0)
    bridge = BrowserReadingBridge(clock=clock, page_max_age_seconds=5.0)
    bridge.ingest_payload(
        {
            "version": 1,
            "type": "page",
            "url": "https://example.com/old",
            "title": "Old page",
        },
        received_at=30.0,
    )

    clock.value = 36.0
    with pytest.raises(SelectionError, match="stale"):
        bridge.latest_page_snapshot()
