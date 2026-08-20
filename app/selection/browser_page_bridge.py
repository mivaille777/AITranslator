"""Browser bridge extension that also remembers page-level reading context."""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable

from app.selection.browser_bridge import BrowserSelectionBridge, BrowserSelectionSnapshot
from app.selection.errors import SelectionError


DEFAULT_BROWSER_PAGE_MAX_AGE_SECONDS = 120.0


def _bounded(value: object, limit: int) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:limit]


@dataclass(frozen=True, slots=True)
class BrowserPageSnapshot:
    """Last browser document/tab context reported by the companion extension."""

    url: str = ""
    title: str = ""
    heading: str = ""
    frame_url: str = ""
    received_at: float = 0.0


class BrowserReadingBridge(BrowserSelectionBridge):
    """Accept page pings without weakening the existing selection protocol."""

    def __init__(
        self,
        *args: Any,
        page_max_age_seconds: float = DEFAULT_BROWSER_PAGE_MAX_AGE_SECONDS,
        clock: Callable[[], float] | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_clock = clock or monotonic
        super().__init__(*args, clock=resolved_clock, **kwargs)
        try:
            age = float(page_max_age_seconds)
            if not math.isfinite(age):
                raise ValueError("page age must be finite")
        except (TypeError, ValueError):
            age = DEFAULT_BROWSER_PAGE_MAX_AGE_SECONDS
        self.page_max_age_seconds = max(1.0, age)
        self._latest_page: BrowserPageSnapshot | None = None

    def _remember_page(
        self,
        *,
        url: object = "",
        title: object = "",
        heading: object = "",
        frame_url: object = "",
        received_at: float | None = None,
    ) -> BrowserPageSnapshot:
        snapshot = BrowserPageSnapshot(
            url=_bounded(url, 4096),
            title=_bounded(title, 1024),
            heading=_bounded(heading, 1024),
            frame_url=_bounded(frame_url, 4096),
            received_at=self._clock() if received_at is None else float(received_at),
        )
        if not snapshot.url and not snapshot.title:
            raise SelectionError("browser page context is empty")
        with self._lock:
            self._latest_page = snapshot
        self.logger.debug(
            "browser_page_context_received has_url=%s has_title=%s",
            bool(snapshot.url),
            bool(snapshot.title),
        )
        return snapshot

    def ingest_payload(
        self,
        payload: dict[str, Any],
        *,
        received_at: float | None = None,
    ) -> BrowserSelectionSnapshot | BrowserPageSnapshot:
        payload_type = str(payload.get("type", "selection") or "selection").casefold()
        if payload_type == "page":
            try:
                version = int(payload.get("version", 1))
            except (TypeError, ValueError):
                raise SelectionError("browser page protocol is invalid")
            if version != 1:
                raise SelectionError("browser page protocol is unsupported")
            return self._remember_page(
                url=payload.get("url"),
                title=payload.get("title"),
                heading=payload.get("heading"),
                frame_url=payload.get("frame_url"),
                received_at=received_at,
            )

        snapshot = super().ingest_payload(payload, received_at=received_at)
        if snapshot.url or snapshot.title:
            self._remember_page(
                url=snapshot.url,
                title=snapshot.title,
                heading=snapshot.heading,
                frame_url=snapshot.frame_url,
                received_at=snapshot.received_at,
            )
        return snapshot

    def latest_page_snapshot(
        self,
        *,
        max_age_seconds: float | None = None,
    ) -> BrowserPageSnapshot:
        with self._lock:
            snapshot = self._latest_page
        if snapshot is None:
            raise SelectionError("browser bridge has no page context")
        try:
            limit = (
                self.page_max_age_seconds
                if max_age_seconds is None
                else max(0.0, float(max_age_seconds))
            )
        except (TypeError, ValueError):
            limit = self.page_max_age_seconds
        if self._clock() - snapshot.received_at > limit:
            raise SelectionError("browser page context is stale")
        return snapshot


__all__ = [
    "BrowserPageSnapshot",
    "BrowserReadingBridge",
    "DEFAULT_BROWSER_PAGE_MAX_AGE_SECONDS",
]
