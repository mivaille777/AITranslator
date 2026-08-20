"""Key-free web search and page-reading tools for the desktop Agent."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import ipaddress
import socket
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from app.agent.tools.base import ToolResult


DEFAULT_SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
DEFAULT_WEB_TIMEOUT_SECONDS = 8.0
DEFAULT_WEB_MAX_RESULTS = 5
MAX_WEB_RESULTS = 10
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_PAGE_TEXT_CHARS = 60_000
DEFAULT_WEB_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[WebSearchResult] = []
        self._anchor_url = ""
        self._anchor_parts: list[str] = []
        self._snippet_parts: list[str] = []
        self._in_result_anchor = False
        self._in_snippet = False

    @staticmethod
    def _class_tokens(attrs: list[tuple[str, str | None]]) -> set[str]:
        value = next((value or "" for key, value in attrs if key == "class"), "")
        return {token.strip() for token in value.split() if token.strip()}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = self._class_tokens(attrs)
        if tag == "a" and "result__a" in classes:
            self._in_result_anchor = True
            self._anchor_parts = []
            self._anchor_url = next((value or "" for key, value in attrs if key == "href"), "")
        elif "result__snippet" in classes:
            self._in_snippet = True
            self._snippet_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_anchor:
            title = " ".join("".join(self._anchor_parts).split())
            url = _unwrap_duckduckgo_url(self._anchor_url)
            if title and url:
                self.results.append(WebSearchResult(title=title, url=url))
            self._in_result_anchor = False
            self._anchor_parts = []
            self._anchor_url = ""
        elif self._in_snippet and tag in {"a", "div", "span"}:
            snippet = " ".join("".join(self._snippet_parts).split())
            if snippet and self.results:
                latest = self.results[-1]
                if not latest.snippet:
                    self.results[-1] = WebSearchResult(
                        title=latest.title,
                        url=latest.url,
                        snippet=snippet,
                    )
            self._in_snippet = False
            self._snippet_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_result_anchor:
            self._anchor_parts.append(data)
        if self._in_snippet:
            self._snippet_parts.append(data)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "canvas"}:
            self._ignored_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "canvas"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        self.parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())

    @property
    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line).strip()


def _unwrap_duckduckgo_url(url: str) -> str:
    value = unescape(str(url or "").strip())
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlparse(value)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
        query = parse_qs(parsed.query)
        target = query.get("uddg", [""])[0]
        if target:
            return unquote(target)
    return value if value.startswith(("https://", "http://")) else ""


def _ensure_public_url(url: str) -> str:
    value = str(url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("只支持 http/https 网页地址。")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("不允许 Agent 读取本机或局域网地址。")
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError("无法解析网页主机名。") from exc
    for entry in addresses:
        raw_ip = entry[4][0]
        try:
            ip = ipaddress.ip_address(raw_ip.split("%")[0])
        except ValueError:
            continue
        if any(
            (
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_reserved,
                ip.is_multicast,
                ip.is_unspecified,
            )
        ):
            raise ValueError("不允许 Agent 读取本机、保留地址或局域网地址。")
    return value


class WebTools:
    """Search the public web and extract readable text without an API key."""

    def __init__(
        self,
        *,
        search_endpoint: str = DEFAULT_SEARCH_ENDPOINT,
        timeout_seconds: float = DEFAULT_WEB_TIMEOUT_SECONDS,
        user_agent: str = DEFAULT_WEB_USER_AGENT,
    ) -> None:
        self.search_endpoint = str(search_endpoint).strip() or DEFAULT_SEARCH_ENDPOINT
        self.timeout_seconds = min(30.0, max(1.0, float(timeout_seconds)))
        self.user_agent = str(user_agent).strip() or DEFAULT_WEB_USER_AGENT

    def web_search(self, query: str, max_results: int = DEFAULT_WEB_MAX_RESULTS) -> ToolResult:
        normalized = " ".join(str(query or "").strip().split())
        if not normalized:
            return ToolResult("web_search", False, "Web Search 查询不能为空。")
        limit = min(MAX_WEB_RESULTS, max(1, int(max_results)))
        url = f"{self.search_endpoint}?q={quote_plus(normalized)}"
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = response.read(MAX_PAGE_BYTES)
        except Exception as exc:
            return ToolResult("web_search", False, f"Web Search 请求失败：{type(exc).__name__}")

        parser = _DuckDuckGoParser()
        try:
            parser.feed(payload.decode("utf-8", errors="replace"))
        except Exception as exc:
            return ToolResult("web_search", False, f"Web Search 结果解析失败：{type(exc).__name__}")

        unique: list[WebSearchResult] = []
        seen: set[str] = set()
        for result in parser.results:
            if result.url in seen:
                continue
            seen.add(result.url)
            unique.append(result)
            if len(unique) >= limit:
                break
        if not unique:
            return ToolResult("web_search", False, "没有解析到可用的 Web Search 结果。")

        blocks = []
        for index, result in enumerate(unique, 1):
            snippet = f"\n{result.snippet}" if result.snippet else ""
            blocks.append(f"[{index}] {result.title}\n{result.url}{snippet}")
        return ToolResult(
            "web_search",
            True,
            "\n\n".join(blocks),
            {
                "query": normalized,
                "results": [
                    {"title": item.title, "url": item.url, "snippet": item.snippet}
                    for item in unique
                ],
                "requires_llm": True,
                "instruction": (
                    "请基于 Web Search 工具返回的结果回答用户；区分搜索摘要与已读取网页正文，"
                    "不要把搜索摘要当作已经核验的全文事实。必要时建议继续读取具体网页。"
                ),
            },
        )

    def web_read(self, url: str, max_chars: int = MAX_PAGE_TEXT_CHARS) -> ToolResult:
        try:
            safe_url = _ensure_public_url(url)
        except ValueError as exc:
            return ToolResult("web_read", False, str(exc))
        request = Request(
            safe_url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,text/plain,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content_type = str(response.headers.get("Content-Type", "")).lower()
                payload = response.read(MAX_PAGE_BYTES)
                final_url = str(response.geturl())
        except Exception as exc:
            return ToolResult("web_read", False, f"网页读取失败：{type(exc).__name__}")

        raw = payload.decode("utf-8", errors="replace")
        title = ""
        if "html" in content_type or "<html" in raw[:500].lower():
            parser = _VisibleTextParser()
            try:
                parser.feed(raw)
            except Exception as exc:
                return ToolResult("web_read", False, f"网页正文解析失败：{type(exc).__name__}")
            text = parser.text
            title = parser.title
        else:
            text = raw.strip()
        safe_max = min(MAX_PAGE_TEXT_CHARS, max(2_000, int(max_chars)))
        clipped = text[:safe_max]
        if not clipped.strip():
            return ToolResult("web_read", False, "网页没有提取到可读正文。")
        return ToolResult(
            "web_read",
            True,
            clipped,
            {
                "url": final_url,
                "title": title,
                "returned_chars": len(clipped),
                "truncated": len(clipped) < len(text),
                "requires_llm": True,
                "instruction": (
                    "请仅依据 web_read 工具提取的网页正文回答当前问题；如果正文被截断或信息不足，"
                    "明确说明，不要补造网页中不存在的事实。"
                ),
            },
        )


__all__ = [
    "DEFAULT_SEARCH_ENDPOINT",
    "DEFAULT_WEB_MAX_RESULTS",
    "DEFAULT_WEB_TIMEOUT_SECONDS",
    "MAX_PAGE_TEXT_CHARS",
    "WebSearchResult",
    "WebTools",
]
