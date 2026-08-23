"""RAG domain contracts and ingestion boundary for AITrans knowledge retrieval."""

from backend.rag.chunking import CHUNKER_VERSION, StructureAwareChunker, chunk_document
from backend.rag.citation_service import CitationService, build_evidence_citations
from backend.rag.config import (
    RagChunkingConfig,
    RagConfig,
    RagEmbeddingConfig,
    RagRerankerConfig,
    RagRetrievalConfig,
    RagVectorStoreConfig,
)
from backend.rag.embeddings import (
    EmbeddingProvider,
    EmbeddingRuntimeSnapshot,
    EmbeddingRuntimeStatus,
    Qwen3EmbeddingProvider,
    create_embedding_provider,
)
from backend.rag.evidence_builder import build_agent_evidence, build_evidence_item
from backend.rag.exceptions import (
    RagConfigurationError,
    RagEmbeddingError,
    RagError,
    RagInvariantError,
    RagParsingError,
    RagRetrievalError,
    RagVectorStoreError,
    UnsupportedDocumentTypeError,
)
from backend.rag.index_manifest import IndexManifest, IndexManifestRecord, IndexStatus
from backend.rag.index_service import IndexDocumentResult, IndexService
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
from backend.rag.tokenization import (
    HeuristicTokenCounter,
    TokenCounter,
    TransformersTokenCounter,
)

__all__ = [
    "CHUNKER_VERSION",
    "CitationService",
    "DocumentChunk",
    "DocumentPage",
    "DocumentSection",
    "EmbeddingProvider",
    "EmbeddingRuntimeSnapshot",
    "EmbeddingRuntimeStatus",
    "HeuristicTokenCounter",
    "IndexDocumentResult",
    "IndexManifest",
    "IndexManifestRecord",
    "IndexService",
    "IndexStatus",
    "KnowledgeDocument",
    "NormalizedDocument",
    "Qwen3EmbeddingProvider",
    "RagChunkingConfig",
    "RagConfig",
    "RagConfigurationError",
    "RagEmbeddingConfig",
    "RagEmbeddingError",
    "RagError",
    "RagInvariantError",
    "RagParsingError",
    "RagRerankerConfig",
    "RagRetrievalConfig",
    "RagRetrievalError",
    "RagVectorStoreConfig",
    "RagVectorStoreError",
    "RetrievalCandidate",
    "RetrievalResult",
    "StructureAwareChunker",
    "TokenCounter",
    "TransformersTokenCounter",
    "UnsupportedDocumentTypeError",
    "build_agent_evidence",
    "build_evidence_citations",
    "build_evidence_item",
    "build_stable_chunk_id",
    "chunk_document",
    "create_embedding_provider",
    "get_parser_for_path",
    "parse_document",
]
