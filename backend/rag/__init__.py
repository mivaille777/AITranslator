"""RAG domain contracts for AITrans knowledge retrieval."""

from backend.rag.config import (
    RagChunkingConfig,
    RagConfig,
    RagEmbeddingConfig,
    RagRetrievalConfig,
    RagVectorStoreConfig,
)
from backend.rag.exceptions import RagConfigurationError, RagError, RagInvariantError
from backend.rag.models import (
    DocumentChunk,
    DocumentPage,
    DocumentSection,
    KnowledgeDocument,
    NormalizedDocument,
    RetrievalCandidate,
    RetrievalResult,
    build_stable_chunk_id,
)

__all__ = [
    "DocumentChunk",
    "DocumentPage",
    "DocumentSection",
    "KnowledgeDocument",
    "NormalizedDocument",
    "RagChunkingConfig",
    "RagConfig",
    "RagConfigurationError",
    "RagEmbeddingConfig",
    "RagError",
    "RagInvariantError",
    "RagRetrievalConfig",
    "RagVectorStoreConfig",
    "RetrievalCandidate",
    "RetrievalResult",
    "build_stable_chunk_id",
]
