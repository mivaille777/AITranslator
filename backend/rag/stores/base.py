from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from backend.rag.models import DocumentChunk, RetrievalCandidate


class VectorSearchFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_ids: list[str] = Field(default_factory=list)
    source_kind: str | None = None
    language: str | None = None
    metadata: dict[str, str | int | bool] = Field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    def ensure_collection(self) -> None: ...

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
    ) -> None: ...

    def search(
        self,
        vector: list[float],
        *,
        top_k: int,
        filters: VectorSearchFilter | None = None,
    ) -> list[RetrievalCandidate]: ...

    def delete_document(self, document_id: str) -> None: ...

    def delete_chunks(self, chunk_ids: list[str]) -> None: ...

    def get_chunk(self, chunk_id: str) -> DocumentChunk | None: ...


__all__ = ["VectorSearchFilter", "VectorStore"]
