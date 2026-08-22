from __future__ import annotations

from pydantic import BaseModel, Field


class ReadingSelectionResponse(BaseModel):
    selection_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=20_000)
    provider: str = Field(default="", max_length=128)
    source_kind: str = Field(default="", max_length=128)
    resource_url: str = Field(default="", max_length=4096)
    resource_title: str = Field(default="", max_length=1024)
    local_locator: str = Field(default="", max_length=4096)
    application: str = Field(default="", max_length=512)
    page_number: int | None = Field(default=None, ge=1)
    section_heading: str = Field(default="", max_length=1024)
    context_before: str = Field(default="", max_length=4000)
    context_after: str = Field(default="", max_length=4000)


class ReadingSelectionEnvelope(BaseModel):
    selection: ReadingSelectionResponse | None = None


__all__ = ["ReadingSelectionEnvelope", "ReadingSelectionResponse"]
