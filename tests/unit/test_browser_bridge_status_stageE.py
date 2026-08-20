from __future__ import annotations

from app.selection.browser_bridge import BrowserSelectionBridge


def test_browser_bridge_status_exposes_runtime_metadata_without_selection_text() -> None:
    now = [10.0]
    bridge = BrowserSelectionBridge(clock=lambda: now[0])
    bridge.ingest_payload(
        {
            "version": 1,
            "type": "selection",
            "text": "secret selected sentence",
            "url": "https://example.org/paper",
            "title": "A Research Paper",
            "heading": "3. Methodology",
        },
        received_at=7.5,
    )

    status = bridge.status_snapshot()

    assert not status.running
    assert status.host == "127.0.0.1"
    assert status.port == 8765
    assert status.has_extension_activity
    assert status.last_activity_age_seconds == 2.5
    assert status.last_title == "A Research Paper"
    assert status.last_url == "https://example.org/paper"
    assert status.last_heading == "3. Methodology"
    assert not hasattr(status, "text")
    assert "secret selected sentence" not in repr(status)
