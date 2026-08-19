"""Best-effort foreground browser context for the Windows Desktop Agent."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any
from urllib.parse import urlparse

from app.agent.tools.base import ToolResult


_ADDRESS_NAMES = (
    "address and search bar",
    "search or enter web address",
    "address bar",
    "地址和搜索栏",
    "地址栏",
)


def _normalize_candidate(value: object) -> str:
    text = str(value or "").strip()
    if not text or " " in text[:12]:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    if "." in text and not text.startswith(("edge://", "chrome://", "about:")):
        return "https://" + text
    return ""


def _read_foreground_browser() -> tuple[str, str]:
    try:
        import uiautomation as auto
    except Exception:
        return "", ""
    try:
        root = auto.GetForegroundControl()
    except Exception:
        return "", ""
    if root is None:
        return "", ""
    title = str(getattr(root, "Name", "") or "").strip()
    queue: list[tuple[Any, int]] = [(root, 0)]
    visited = 0
    while queue and visited < 240:
        control, depth = queue.pop(0)
        visited += 1
        name = str(getattr(control, "Name", "") or "").strip().lower()
        likely_address = any(item in name for item in _ADDRESS_NAMES)
        if likely_address:
            values: list[object] = []
            try:
                pattern = control.GetValuePattern()
                values.append(getattr(pattern, "Value", ""))
            except Exception:
                pass
            values.append(getattr(control, "Value", ""))
            for value in values:
                candidate = _normalize_candidate(value)
                if candidate:
                    parsed = urlparse(candidate)
                    if parsed.hostname:
                        return candidate, title
        if depth >= 8:
            continue
        try:
            children = control.GetChildren()
        except Exception:
            children = ()
        for child in children or ():
            queue.append((child, depth + 1))
    return "", title


class BrowserContextTools:
    """Capture the last external browser before the Agent window takes focus."""

    def __init__(
        self,
        *,
        reader: Callable[[], tuple[str, str]] | None = None,
    ) -> None:
        self._reader = reader or _read_foreground_browser
        self._lock = RLock()
        self._last_url = ""
        self._last_title = ""

    def capture_foreground(self) -> ToolResult:
        try:
            url, title = self._reader()
        except Exception as exc:
            return ToolResult(
                "get_active_browser_context",
                False,
                f"读取当前浏览器上下文失败：{type(exc).__name__}",
            )
        if not url:
            return ToolResult(
                "get_active_browser_context",
                False,
                "当前前台窗口没有可读取的网页地址。",
            )
        with self._lock:
            self._last_url = url
            self._last_title = title
        return ToolResult(
            "get_active_browser_context",
            True,
            url,
            {"url": url, "title": title, "cached": False},
        )

    def get_active_browser_context(self) -> ToolResult:
        captured = self.capture_foreground()
        if captured.ok:
            return captured
        with self._lock:
            url = self._last_url
            title = self._last_title
        if url:
            return ToolResult(
                "get_active_browser_context",
                True,
                url,
                {"url": url, "title": title, "cached": True},
            )
        return ToolResult(
            "get_active_browser_context",
            False,
            "没有保存到当前网页地址。请先切换到 Chrome/Edge 页面再打开 AI，或直接提供 URL。",
        )


__all__ = ["BrowserContextTools"]
