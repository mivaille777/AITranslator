from __future__ import annotations

import os
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from threading import Lock

from app.infrastructure.paths import data_root
from app.infrastructure.settings import SettingsManager
from backend.api.rag_model_dependencies import get_rag_model_manager
from backend.rag.chunking import StructureAwareChunker
from backend.rag.config import RagConfig
from backend.rag.embeddings import EmbeddingProvider, create_embedding_provider
from backend.rag.index_manifest import IndexManifest
from backend.rag.index_service import IndexService
from backend.rag.parsers import parse_document
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


def _resolve_runtime_storage_path(configured_path: str | Path) -> Path:
    """Resolve RAG state independently of the process working directory.

    Development launches the backend from ``apps/desktop`` while packaged
    builds can start from arbitrary working directories. Relative RAG paths
    therefore belong under the application's writable data root, not cwd.
    """

    candidate = Path(configured_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (data_root() / candidate).resolve()


def _build_document_parser(config: RagConfig):
    """Bind document parsing to the immutable runtime parsing profile.

    ``parse_document`` keeps safe library defaults, while the product runtime can
    opt into Docling for PDF layout/section recovery. A deep copy prevents later
    settings mutation from changing an active indexing run halfway through.
    """

    advanced_config = config.advanced_parsing.model_copy(deep=True)
    return partial(parse_document, advanced_config=advanced_config)


def _build_runtime() -> RagRuntime:
    settings = SettingsManager().data
    raw_rag = settings.get("rag", {})
    config = RagConfig.model_validate(raw_rag if isinstance(raw_rag, dict) else {})
    model_manager = get_rag_model_manager()
    embedding = create_embedding_provider(
        config.embedding,
        model_manager=model_manager,
    )
    resolved_storage_path = _resolve_runtime_storage_path(
        config.vector_store.storage_path
    )
    vector_store_config = config.vector_store.model_copy(
        update={"storage_path": str(resolved_storage_path)}
    )
    vector_store = QdrantLocalVectorStore(
        vector_store_config,
        dimension=config.embedding.dimension,
    )
    state_directory = resolved_storage_path.parent
    sparse = BM25SparseRetriever(state_directory / "bm25_index.json")
    manifest = IndexManifest(state_directory / "index_manifest.json")
    retrieval = RetrievalService(
        embedding_provider=embedding,
        vector_store=vector_store,
        sparse_retriever=sparse,
        config=config.retrieval,
        reranker=Qwen3RerankerProvider(
            config.reranker,
            model_manager=model_manager,
        ),
    )
    index = IndexService(
        chunker=StructureAwareChunker(config.chunking),
        embedding_provider=embedding,
        vector_store=vector_store,
        sparse_retriever=sparse,
        manifest=manifest,
        parser=_build_document_parser(config),
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
