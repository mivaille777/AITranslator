from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class DocumentSourceType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    BROWSER = "browser"
    SELECTION = "selection"


class DocumentSource(BaseModel):
    """Normalized input representation for every reading source.

    This model intentionally does not encode retrieval concerns. It is the
    stable boundary between Reading Context and later chunk/index services.
    """

    source_id: str
    source_type: DocumentSourceType
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}
