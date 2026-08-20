from __future__ import annotations

from app.agent.desktop_tool_runtime import DesktopAgentToolCoordinator
from app.agent.tools.browser_context import BrowserContextTools
from app.agent.tools.desktop_web import DesktopWebTools
from app.agent.tools.base import ToolResult
import app.agent.tools.desktop_web as desktop_web_module


class _Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _Response:
    def __init__(self, url: str, body: bytes) -> None:
        self._url = url
        self._body = body
        self.headers = _Headers({"Content-Type": "text/html; charset=utf-8"})

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self) -> str:
        return self._url

    def read(self, _limit: int) -> bytes:
        return self._body


def test_public_hostname_is_not_rejected_due_to_dns_policy(monkeypatch) -> None:
    monkeypatch.setattr(
        desktop_web_module,
        "urlopen",
        lambda request, timeout: _Response(
            request.full_url,
            b"<html><title>Example</title><body><p>Public page content</p></body></html>",
        ),
    )
    tools = DesktopWebTools()
    result = tools.web_read("https://example.com/article")
    assert result.ok
    assert "Public page content" in result.content
    assert result.metadata["scope"] == "public"


def test_literal_localhost_requires_one_session_grant(monkeypatch) -> None:
    monkeypatch.setattr(
        desktop_web_module,
        "urlopen",
        lambda request, timeout: _Response(
            request.full_url,
            b"<html><body><p>Local dashboard</p></body></html>",
        ),
    )
    tools = DesktopWebTools()
    blocked = tools.web_read("http://127.0.0.1:8000")
    assert not blocked.ok
    assert blocked.metadata["permission_required"] == "local_network"

    tools.grant_local_host("127.0.0.1")
    allowed = tools.web_read("http://127.0.0.1:8000")
    assert allowed.ok
    assert "Local dashboard" in allowed.content


def test_current_page_intent_uses_browser_context() -> None:
    class FakeWeb(DesktopWebTools):
        def web_read(self, url: str, max_chars: int = 60_000) -> ToolResult:
            del max_chars
            return ToolResult(
                "web_read",
                True,
                "Article body from " + url,
                {"url": url, "instruction": "summarize", "requires_llm": True},
            )

    browser = BrowserContextTools(
        reader=lambda: ("https://example.com/current", "Current Article")
    )
    coordinator = DesktopAgentToolCoordinator(web_tools=FakeWeb(), browser_tools=browser)
    plan = coordinator.plan_message("总结这个网页")
    assert plan.tool_name == "active_web_read"

    outcome = coordinator.execute_message("总结这个网页")
    assert outcome.requires_llm
    assert "Current Article" in outcome.tool_context
    assert "Article body" in outcome.tool_context
