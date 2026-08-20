"""Offline tests for Agent Web Search / Web Read tools."""

from __future__ import annotations

from io import BytesIO

from app.agent.tools import web as web_module
from app.agent.tools.web import WebTools


class FakeResponse:
    def __init__(self, body: bytes, *, content_type: str = "text/html; charset=utf-8", url: str = "https://example.com/") -> None:
        self._body = BytesIO(body)
        self.headers = {"Content-Type": content_type}
        self._url = url

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_web_search_parses_duckduckgo_results(monkeypatch) -> None:
    html = b"""
    <html><body>
      <a class="result__a" href="https://example.com/a">Example A</a>
      <a class="result__snippet">First search snippet</a>
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fb">Example B</a>
      <a class="result__snippet">Second search snippet</a>
    </body></html>
    """
    monkeypatch.setattr(
        web_module,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(html),
    )

    result = WebTools(timeout_seconds=1).web_search("LangGraph tools")

    assert result.ok
    assert result.metadata["query"] == "LangGraph tools"
    assert len(result.metadata["results"]) == 2
    assert "https://example.com/a" in result.content
    assert "https://example.org/b" in result.content
    assert result.metadata["requires_llm"] is True


def test_web_read_extracts_visible_text(monkeypatch) -> None:
    monkeypatch.setattr(web_module, "_ensure_public_url", lambda url: url)
    html = b"""
    <html><head><title>Agent Docs</title><style>.x{}</style></head>
    <body><h1>LangGraph</h1><p>Stateful agent orchestration.</p><script>ignore()</script></body></html>
    """
    monkeypatch.setattr(
        web_module,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(html, url="https://example.com/docs"),
    )

    result = WebTools(timeout_seconds=1).web_read("https://example.com/docs")

    assert result.ok
    assert result.metadata["title"] == "Agent Docs"
    assert "Stateful agent orchestration." in result.content
    assert "ignore()" not in result.content


def test_web_read_blocks_localhost_before_network() -> None:
    result = WebTools(timeout_seconds=1).web_read("http://localhost:8000/private")

    assert not result.ok
    assert "本机" in result.content or "局域网" in result.content
