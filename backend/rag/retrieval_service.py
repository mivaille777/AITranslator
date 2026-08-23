from __future__ import annotations

from time import perf_counter

from backend.rag.config import RagRetrievalConfig
from backend.rag.embeddings.base import EmbeddingProvider
from backend.rag.exceptions import RagRetrievalError
from backend.rag.fusion import rrf_fuse
from backend.rag.models import RetrievalResult
from backend.rag.sparse.store import SparseRetriever
from backend.rag.stores.base import VectorSearchFilter, VectorStore


class RetrievalService:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        sparse_retriever: SparseRetriever,
        config: RagRetrievalConfig | None = None,
    ) -> None:
        self._embedding = embedding_provider
        self._vector_store = vector_store
        self._sparse = sparse_retriever
        self._config = config or RagRetrievalConfig()

    def retrieve(
        self,
        query: str,
        *,
        filters: VectorSearchFilter | None = None,
    ) -> RetrievalResult:
        if not query or not query.strip():
            raise RagRetrievalError("retrieval query must not be empty")
        started = perf_counter()
        dense_started = perf_counter()
        dense = []
        sparse = []
        dense_error = ""
        sparse_error = ""
        try:
            vector = self._embedding.embed_query(query)
            dense = self._vector_store.search(
                vector,
                top_k=self._config.dense_top_k,
                filters=filters,
            )
        except Exception as exc:  # noqa: BLE001 - intentional degraded retrieval
            dense_error = str(exc) or exc.__class__.__name__
        dense_ms = (perf_counter() - dense_started) * 1000

        sparse_started = perf_counter()
        try:
            sparse = self._sparse.search(
                query,
                self._config.sparse_top_k,
                filters,
            )
        except Exception as exc:  # noqa: BLE001 - intentional degraded retrieval
            sparse_error = str(exc) or exc.__class__.__name__
        sparse_ms = (perf_counter() - sparse_started) * 1000

        if dense_error and sparse_error:
            raise RagRetrievalError(
                f"dense and sparse retrieval failed: dense={dense_error}; sparse={sparse_error}"
            )
        fusion_started = perf_counter()
        candidates = rrf_fuse(
            [ranked for ranked in (dense, sparse) if ranked],
            limit=self._config.fusion_top_k,
        )
        fusion_ms = (perf_counter() - fusion_started) * 1000
        strategy = (
            "sparse-only" if dense_error else "dense-only" if sparse_error else "hybrid"
        )
        fallback_reason = dense_error or sparse_error
        return RetrievalResult(
            query=query,
            candidates=candidates,
            retrieval_strategy=strategy,
            elapsed_ms=(perf_counter() - started) * 1000,
            metadata={
                "dense_count": len(dense),
                "sparse_count": len(sparse),
                "fusion_count": len(candidates),
                "dense_search_ms": dense_ms,
                "sparse_search_ms": sparse_ms,
                "fusion_ms": fusion_ms,
                "fallback_reason": fallback_reason,
            },
        )


__all__ = ["RetrievalService"]
