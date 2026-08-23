from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.rag.index_manifest import IndexStatus


class KnowledgeApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnowledgeDocumentImportRequest(KnowledgeApiModel):
    path: str = Field(min_length=1, max_length=4096)


class KnowledgeDocumentResponse(KnowledgeApiModel):
    document_id: str
    title: str = ""
    source_uri: str = ""
    source_type: str = ""
    status: IndexStatus
    chunk_count: int = Field(default=0, ge=0)
    indexed_at: datetime | None = None
    error: str = ""
    content_hash: str = ""
    parser_version: str = ""
    chunker_version: str = ""
    embedding_model: str = ""
    embedding_dimension: int = Field(default=0, ge=0)


class KnowledgeDocumentListResponse(KnowledgeApiModel):
    total: int = Field(ge=0)
    documents: list[KnowledgeDocumentResponse] = Field(default_factory=list)


class KnowledgeDocumentImportResponse(KnowledgeApiModel):
    document: KnowledgeDocumentResponse
    reused_existing: bool = False
    elapsed_ms: float = Field(default=0.0, ge=0.0)


class KnowledgeDocumentDeleteResponse(KnowledgeApiModel):
    document_id: str
    deleted: bool
    source_file_preserved: bool = True


class KnowledgeDocumentStatusResponse(KnowledgeApiModel):
    document_id: str
    status: IndexStatus
    chunk_count: int = Field(default=0, ge=0)
    indexed_at: datetime | None = None
    error: str = ""


class KnowledgeRuntimeResponse(KnowledgeApiModel):
    enabled: bool
    embedding_provider: str
    embedding_model: str
    embedding_status: str
    device: str
    dimension: int = Field(ge=1)
    vector_store_provider: str
    collection_name: str
    document_count: int = Field(ge=0)
    ready_document_count: int = Field(ge=0)
    indexed_chunk_count: int = Field(ge=0)
    max_file_bytes: int = Field(ge=1)


__all__ = [
    "KnowledgeApiModel",
    "KnowledgeDocumentDeleteResponse",
    "KnowledgeDocumentImportRequest",
    "KnowledgeDocumentImportResponse",
    "KnowledgeDocumentListResponse",
    "KnowledgeDocumentResponse",
    "KnowledgeDocumentStatusResponse",
    "KnowledgeRuntimeResponse",
]
