"""RAG domain contracts and ingestion boundary for AITrans knowledge retrieval."""

from backend.rag.config import (
    RagChunkingConfig,
    RagConfig,
    RagEmbeddingConfig,
    RagRetrievalConfig,
    RagVectorStoreConfig,
)
from backend.rag.exceptions import (
    RagConfigurationError,
    RagError,
    RagInvariantError,
    RagParsingError,
    UnsupportedDocumentTypeError,
)
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
from backend.rag.parsers import get_parser_for_path, parse_document

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
    "RagParsingError",
    "RagRetrievalConfig",
    "RagVectorStoreConfig",
    "RetrievalCandidate",
    "RetrievalResult",
    "UnsupportedDocumentTypeError",
    "build_stable_chunk_id",
    "get_parser_for_path",
    "parse_document",
]
