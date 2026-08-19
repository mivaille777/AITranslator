from __future__ import annotations

from app.agent.tools.browser_context import BrowserContextTools


def test_browser_bridge_context_is_reused_when_live_capture_is_unavailable() -> None:
    tools = BrowserContextTools(reader=lambda: ("", ""))

    remembered = tools.remember_context(
        "https://example.com/paper",
        "Paper Title",
        source="selection_bridge",
    )

    assert remembered.ok
    assert remembered.metadata["source"] == "selection_bridge"

    current = tools.get_active_browser_context()
    assert current.ok
    assert current.content == "https://example.com/paper"
    assert current.metadata == {
        "url": "https://example.com/paper",
        "title": "Paper Title",
        "cached": True,
    }


def test_browser_bridge_context_rejects_non_web_urls() -> None:
    tools = BrowserContextTools(reader=lambda: ("", ""))

    result = tools.remember_context("chrome://extensions", "Extensions")

    assert not result.ok
