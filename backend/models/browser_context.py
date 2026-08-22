from __future__ import annotations

from pydantic import BaseModel


class BrowserBridgeStatusResponse(BaseModel):
    running: bool
    host: str
    port: int
    endpoint: str
    has_extension_activity: bool
    last_activity_age_seconds: float | None = None
    last_title: str = ""
    last_url: str = ""
    last_heading: str = ""


class BrowserSelectionResponse(BaseModel):
    selection_id: str
    text: str
    url: str = ""
    title: str = ""
    heading: str = ""
    context_before: str = ""
    context_after: str = ""
    frame_url: str = ""
    top_level: bool = True
    captured_at_ms: float | None = None


class BrowserSelectionEnvelope(BaseModel):
    selection: BrowserSelectionResponse | None = None


class BrowserPageResponse(BaseModel):
    page_id: str
    url: str = ""
    title: str = ""
    heading: str = ""
    frame_url: str = ""


class BrowserPageEnvelope(BaseModel):
    page: BrowserPageResponse | None = None
