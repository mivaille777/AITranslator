from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.infrastructure.settings import SettingsManager
from backend.rag.chunking import StructureAwareChunker
from backend.rag.config import RagConfig
from backend.rag.embeddings import EmbeddingProvider, create_embedding_provider
from backend.rag.index_manifest import IndexManifest
from backend.rag.index_service import IndexService
from backend.rag.rerankers import Qwen3RerankerProvider
from backend.rag.retrieval_service import RetrievalService
from backend.rag.sparse import BM25SparseRetriever
from backend.rag.stores import QdrantLocalVectorStore
from backend.services.knowledge_library_service import (
    DEFAULT_KNOWLEDGE_MAX_FILE_BYTES,
    KnowledgeLibraryService,
)


@dataclass(slots=True)
class RagRuntime:
    config: RagConfig
    embedding_provider: EmbeddingProvider
    vector_store: QdrantLocalVectorStore
    sparse_retriever: BM25SparseRetriever
    manifest: IndexManifest
    retrieval_service: RetrievalService
    index_service: IndexService
    library_service: KnowledgeLibraryService


_runtime: RagRuntime | None = None
_runtime_lock = Lock()


def _allowed_roots() -> tuple[Path, ...]:
    configured = os.getenv("AITRANS_KNOWLEDGE_ALLOWED_ROOTS", "").strip()
    if not configured:
        return (Path.home().resolve(),)
    roots = tuple(
        Path(item).expanduser().resolve()
        for item in configured.split(os.pathsep)
        if item.strip()
    )
    return roots or (Path.home().resolve(),)


def _max_file_bytes() -> int:
    configured = os.getenv("AITRANS_KNOWLEDGE_MAX_FILE_BYTES", "").strip()
    try:
        return (
            max(1, int(configured)) if configured else DEFAULT_KNOWLEDGE_MAX_FILE_BYTES
        )
    except ValueError:
        return DEFAULT_KNOWLEDGE_MAX_FILE_BYTES


def _build_runtime() -> RagRuntime:
    settings = SettingsManager().data
    raw_rag = settings.get("rag", {})
    config = RagConfig.model_validate(raw_rag if isinstance(raw_rag, dict) else {})
    embedding = create_embedding_provider(config.embedding)
    vector_store = QdrantLocalVectorStore(
        config.vector_store,
        dimension=config.embedding.dimension,
    )
    state_directory = (
        Path(config.vector_store.storage_path).expanduser().resolve().parent
    )
    sparse = BM25SparseRetriever(state_directory / "bm25_index.json")
    manifest = IndexManifest(state_directory / "index_manifest.json")
    retrieval = RetrievalService(
        embedding_provider=embedding,
        vector_store=vector_store,
        sparse_retriever=sparse,
        config=config.retrieval,
        reranker=Qwen3RerankerProvider(config.reranker),
    )
    index = IndexService(
        chunker=StructureAwareChunker(config.chunking),
        embedding_provider=embedding,
        vector_store=vector_store,
        sparse_retriever=sparse,
        manifest=manifest,
    )
    library = KnowledgeLibraryService(
        index_service=index,
        manifest=manifest,
        config=config,
        embedding_provider=embedding,
        allowed_roots=_allowed_roots(),
        max_file_bytes=_max_file_bytes(),
    )
    return RagRuntime(
        config=config,
        embedding_provider=embedding,
        vector_store=vector_store,
        sparse_retriever=sparse,
        manifest=manifest,
        retrieval_service=retrieval,
        index_service=index,
        library_service=library,
    )


def get_rag_runtime() -> RagRuntime:
    global _runtime
    if _runtime is not None:
        return _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = _build_runtime()
        return _runtime


def get_retrieval_service() -> RetrievalService:
    return get_rag_runtime().retrieval_service


def get_knowledge_library_service() -> KnowledgeLibraryService:
    return get_rag_runtime().library_service


def close_rag_runtime() -> None:
    global _runtime
    with _runtime_lock:
        runtime = _runtime
        _runtime = None
    if runtime is not None:
        close = getattr(runtime.vector_store, "close", None)
        if callable(close):
            close()


__all__ = [
    "RagRuntime",
    "close_rag_runtime",
    "get_knowledge_library_service",
    "get_rag_runtime",
    "get_retrieval_service",
]
