from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RagConfigModel(BaseModel):
    """Base model for stable RAG configuration contracts."""

    model_config = ConfigDict(extra="forbid")


class RagChunkingConfig(RagConfigModel):
    # target_tokens is now a soft paragraph-group target. Structural boundaries
    # take precedence and token limits are only used to bound grouping/fallback.
    target_tokens: int = Field(default=512, ge=1)
    preferred_max_tokens: int | None = Field(default=None, ge=1)
    hard_max_tokens: int | None = Field(default=None, ge=1)
    overlap_tokens: int = Field(default=80, ge=0)
    minimum_tokens: int = Field(default=100, ge=1)

    @property
    def effective_preferred_max_tokens(self) -> int:
        return self.preferred_max_tokens or self.target_tokens

    @property
    def effective_hard_max_tokens(self) -> int:
        return self.hard_max_tokens or self.effective_preferred_max_tokens

    @model_validator(mode="after")
    def validate_chunk_bounds(self) -> RagChunkingConfig:
        preferred = self.effective_preferred_max_tokens
        hard = self.effective_hard_max_tokens
        if self.minimum_tokens > self.target_tokens:
            raise ValueError("minimum_tokens must not exceed target_tokens")
        if preferred < self.target_tokens:
            raise ValueError("preferred_max_tokens must not be smaller than target_tokens")
        if hard < preferred:
            raise ValueError("hard_max_tokens must not be smaller than preferred_max_tokens")
        if self.overlap_tokens >= self.target_tokens:
            raise ValueError("overlap_tokens must be smaller than target_tokens")
        return self


class RagAdvancedParsingConfig(RagConfigModel):
    enabled: bool = False
    provider: str = "docling"
    device: str = "cpu"
    layout_enabled: bool = True
    table_enabled: bool = False
    ocr_enabled: bool = False
    formula_enabled: bool = False
    document_timeout_seconds: float = Field(default=120.0, gt=0.0, le=600.0)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "docling":
            raise ValueError("advanced parser provider must be docling")
        return normalized

    @field_validator("device")
    @classmethod
    def validate_device(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"auto", "cpu", "cuda"}:
            raise ValueError("advanced parser device must be one of: auto, cpu, cuda")
        return normalized


class RagEmbeddingConfig(RagConfigModel):
    provider: str = "qwen3"
    model: str = "Qwen/Qwen3-Embedding-0.6B"
    device: str = "auto"
    dimension: int = Field(default=1024, ge=1)
    batch_size: int = Field(default=8, ge=1)
    normalize: bool = True
    max_input_tokens: int = Field(default=2048, ge=1)
    warmup: bool = True
    precision: str = "default"
    local_files_only: bool = False
    model_path: str = ""

    @field_validator("device")
    @classmethod
    def validate_device(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"auto", "cuda", "cpu"}:
            raise ValueError("device must be one of: auto, cuda, cpu")
        return normalized

    @field_validator("precision")
    @classmethod
    def validate_precision(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"default", "fp16", "bf16"}:
            raise ValueError("precision must be one of: default, fp16, bf16")
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
    advanced_parsing: RagAdvancedParsingConfig = Field(
        default_factory=RagAdvancedParsingConfig
    )
    chunking: RagChunkingConfig = Field(default_factory=RagChunkingConfig)
    embedding: RagEmbeddingConfig = Field(default_factory=RagEmbeddingConfig)
    vector_store: RagVectorStoreConfig = Field(default_factory=RagVectorStoreConfig)
    retrieval: RagRetrievalConfig = Field(default_factory=RagRetrievalConfig)
    reranker: RagRerankerConfig = Field(default_factory=RagRerankerConfig)


__all__ = [
    "RagAdvancedParsingConfig",
    "RagChunkingConfig",
    "RagConfig",
    "RagEmbeddingConfig",
    "RagRerankerConfig",
    "RagRetrievalConfig",
    "RagVectorStoreConfig",
]
