from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RagConfigModel(BaseModel):
    """Base model for RAG configuration contracts."""

    model_config = ConfigDict(extra="forbid")


class RagChunkingConfig(RagConfigModel):
    target_tokens: int = Field(default=512, ge=1)
    overlap_tokens: int = Field(default=80, ge=0)
    minimum_tokens: int = Field(default=100, ge=1)

    @model_validator(mode="after")
    def validate_chunk_bounds(self) -> RagChunkingConfig:
        if self.minimum_tokens > self.target_tokens:
            raise ValueError("minimum_tokens must not exceed target_tokens")
        if self.overlap_tokens >= self.target_tokens:
            raise ValueError("overlap_tokens must be smaller than target_tokens")
        return self


class RagEmbeddingConfig(RagConfigModel):
    provider: str = "qwen3"
    model: str = "Qwen/Qwen3-Embedding-0.6B"
    device: str = "auto"
    dimension: int = Field(default=1024, ge=1)
    batch_size: int = Field(default=8, ge=1)
    normalize: bool = True
    max_input_tokens: int = Field(default=2048, ge=1)
    warmup: bool = True
    local_files_only: bool = False
    model_path: str = ""

    @field_validator("device")
    @classmethod
    def validate_device(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"auto", "cuda", "cpu"}:
            raise ValueError("device must be one of: auto, cuda, cpu")
        return normalized


class RagVectorStoreConfig(RagConfigModel):
    provider: str = "qdrant_local"
    collection_name: str = Field(default="aitrans_knowledge", min_length=1)
    distance: str = "cosine"
    storage_path: str = "config/rag/qdrant"


class RagRetrievalConfig(RagConfigModel):
    dense_top_k: int = Field(default=30, ge=1)
    sparse_top_k: int = Field(default=30, ge=1)
    fusion_top_k: int = Field(default=20, ge=1)
    final_top_k: int = Field(default=8, ge=1)
    fusion: str = "rrf"

    @model_validator(mode="after")
    def validate_retrieval_bounds(self) -> RagRetrievalConfig:
        if self.final_top_k > self.fusion_top_k:
            raise ValueError("final_top_k must not exceed fusion_top_k")
        return self


class RagRerankerConfig(RagConfigModel):
    provider: str = "qwen3"
    model: str = "Qwen/Qwen3-Reranker-0.6B"
    device: str = "auto"
    batch_size: int = Field(default=8, ge=1)
    lazy_load: bool = True
    local_files_only: bool = False
    model_path: str = ""

    @field_validator("device")
    @classmethod
    def validate_device(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"auto", "cuda", "cpu"}:
            raise ValueError("device must be one of: auto, cuda, cpu")
        return normalized


class RagConfig(RagConfigModel):
    enabled: bool = True
    chunking: RagChunkingConfig = Field(default_factory=RagChunkingConfig)
    embedding: RagEmbeddingConfig = Field(default_factory=RagEmbeddingConfig)
    vector_store: RagVectorStoreConfig = Field(default_factory=RagVectorStoreConfig)
    retrieval: RagRetrievalConfig = Field(default_factory=RagRetrievalConfig)
    reranker: RagRerankerConfig = Field(default_factory=RagRerankerConfig)


__all__ = [
    "RagChunkingConfig",
    "RagConfig",
    "RagConfigModel",
    "RagEmbeddingConfig",
    "RagRerankerConfig",
    "RagRetrievalConfig",
    "RagVectorStoreConfig",
]
