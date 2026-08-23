from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RagModelId = Literal[
    "qwen3-embedding-0.6b",
    "qwen3-reranker-0.6b",
]
RagModelState = Literal[
    "not_installed",
    "downloading",
    "installed",
    "invalid",
]


class RagRuntimeContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RagModelStatusResponse(RagRuntimeContract):
    model_id: RagModelId
    display_name: str
    repository_id: str
    state: RagModelState
    installed: bool
    verified: bool
    path: str = ""
    disk_usage_bytes: int = Field(default=0, ge=0)
    error: str = ""


class RagModelListResponse(RagRuntimeContract):
    models_root: str
    models: list[RagModelStatusResponse] = Field(default_factory=list)


class RagModelOperationResponse(RagRuntimeContract):
    model: RagModelStatusResponse
    changed: bool


__all__ = [
    "RagModelId",
    "RagModelListResponse",
    "RagModelOperationResponse",
    "RagModelState",
    "RagModelStatusResponse",
    "RagRuntimeContract",
]
