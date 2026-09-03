from __future__ import annotations

import os
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from threading import Lock
from typing import Any

from app.infrastructure.paths import data_root
from app.infrastructure.settings import SettingsManager
from backend.api.rag_model_dependencies import get_rag_model_manager
from backend.rag.chunking import StructureAwareChunker
from backend.rag.config import RagConfig, RagVisualUnderstandingConfig
from backend.rag.embeddings import EmbeddingProvider, create_embedding_provider
from backend.rag.index_manifest import IndexManifest
from backend.rag.index_service import IndexService
from backend.rag.parsers import parse_document
from backend.rag.rerankers import Qwen3RerankerProvider
from backend.rag.retrieval_service import RetrievalService
from backend.rag.semantic_chunking import SemanticStructureAwareChunker
from backend.rag.sparse import BM25SparseRetriever
from backend.rag.stores import QdrantLocalVectorStore
from backend.rag.vision import (
    VisualDescriptionProvider,
    create_visual_description_provider,
)
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
    visual_description_provider: VisualDescriptionProvider | None = None


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


def _env_bool(name: str) -> bool | None:
    value = os.getenv(name, "").strip().casefold()
    if not value:
        return None
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _resolve_visual_understanding_config(
    config: RagVisualUnderstandingConfig,
    settings: dict[str, Any],
) -> RagVisualUnderstandingConfig:
    """Resolve optional VLM settings without coupling RAG to the chat provider."""

    updates: dict[str, Any] = {}
    env_enabled = _env_bool("AITRANS_RAG_VLM_ENABLED")
    if env_enabled is not None:
        updates["enabled"] = env_enabled

    env_model = os.getenv("AITRANS_RAG_VLM_MODEL", "").strip()
    env_base_url = os.getenv("AITRANS_RAG_VLM_BASE_URL", "").strip()
    if env_model:
        updates["model"] = env_model
    if env_base_url:
        updates["base_url"] = env_base_url

    resolved = config.model_copy(update=updates, deep=True)
    if not resolved.enabled or not resolved.inherit_ai_settings:
        return resolved

    ai_settings = settings.get("ai")
    if not isinstance(ai_settings, dict):
        return resolved
    provider = str(ai_settings.get("provider", "") or "").strip().lower().replace("-", "_")
    if provider != "openai_compatible":
        return resolved

    inherited: dict[str, Any] = {}
    if not resolved.model.strip():
        inherited_model = str(ai_settings.get("model", "") or "").strip()
        if inherited_model:
            inherited["model"] = inherited_model
    if not resolved.base_url.strip():
        inherited_base_url = str(ai_settings.get("base_url", "") or "").strip()
        if inherited_base_url:
            inherited["base_url"] = inherited_base_url
    return resolved.model_copy(update=inherited, deep=True)


def _build_runtime() -> RagRuntime:
    settings = SettingsManager().data
    raw_rag = settings.get("rag", {})
    config = RagConfig.model_validate(raw_rag if isinstance(raw_rag, dict) else {})
    visual_config = _resolve_visual_understanding_config(
        config.visual_understanding,
        settings,
    )
    config = config.model_copy(
        update={"visual_understanding": visual_config},
        deep=True,
    )
    visual_provider = create_visual_description_provider(visual_config)

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
    # Index operations are not backed by a durable worker queue. Any persisted
    # parsing/chunking/embedding/indexing state loaded by a fresh backend is an
    # interrupted operation and must not be exposed as permanently active.
    manifest.recover_interrupted_operations()
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
    structural_chunker = StructureAwareChunker(config.chunking)
    chunker = SemanticStructureAwareChunker(
        base_chunker=structural_chunker,
        semantic_config=config.semantic_chunking,
        embedding_provider=embedding,
    )
    index = IndexService(
        chunker=chunker,
        embedding_provider=embedding,
        vector_store=vector_store,
        sparse_retriever=sparse,
        manifest=manifest,
        parser=_build_document_parser(config),
        visual_description_provider=visual_provider,
        visual_understanding_config=visual_config,
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
        visual_description_provider=visual_provider,
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
        close = getattr(runtime.visual_description_provider, "close", None)
        if callable(close):
            close()
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
