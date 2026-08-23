"""RAG domain contracts and ingestion boundary for AITrans knowledge retrieval."""

from backend.rag.chunking import CHUNKER_VERSION, StructureAwareChunker, chunk_document
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
from backend.rag.tokenization import HeuristicTokenCounter, TokenCounter

__all__ = [
    "CHUNKER_VERSION",
    "DocumentChunk",
    "DocumentPage",
    "DocumentSection",
    "HeuristicTokenCounter",
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
    "StructureAwareChunker",
    "TokenCounter",
    "UnsupportedDocumentTypeError",
    "build_stable_chunk_id",
    "chunk_document",
    "get_parser_for_path",
    "parse_document",
]
