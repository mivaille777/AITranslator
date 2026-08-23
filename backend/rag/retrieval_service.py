from __future__ import annotations

from time import perf_counter

from backend.rag.config import RagRetrievalConfig
from backend.rag.embeddings.base import EmbeddingProvider
from backend.rag.exceptions import RagRetrievalError
from backend.rag.fusion import rrf_fuse
from backend.rag.models import RetrievalResult
from backend.rag.rerankers.base import RerankerProvider
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
        reranker: RerankerProvider | None = None,
    ) -> None:
        self._embedding = embedding_provider
        self._vector_store = vector_store
        self._sparse = sparse_retriever
        self._config = config or RagRetrievalConfig()
        self._reranker = reranker

    def retrieve(
        self,
        query: str,
        *,
        filters: VectorSearchFilter | None = None,
    ) -> RetrievalResult:
        if not query or not query.strip():
            raise RagRetrievalError("retrieval query must not be empty")
        started = perf_counter()
        dense = []
        sparse = []
        dense_error = ""
        sparse_error = ""
        embedding_ms = 0.0
        dense_ms = 0.0
        try:
            embedding_started = perf_counter()
            vector = self._embedding.embed_query(query)
            embedding_ms = (perf_counter() - embedding_started) * 1000
            dense_started = perf_counter()
            dense = self._vector_store.search(
                vector,
                top_k=self._config.dense_top_k,
                filters=filters,
            )
            dense_ms = (perf_counter() - dense_started) * 1000
        except Exception as exc:  # noqa: BLE001 - intentional degraded retrieval
            dense_error = str(exc) or exc.__class__.__name__

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
        fusion_count = len(candidates)
        strategy = (
            "sparse-only" if dense_error else "dense-only" if sparse_error else "hybrid"
        )
        fallback_reason = dense_error or sparse_error
        reranker_applied = False
        reranker_fallback_reason = ""
        rerank_ms = 0.0
        if self._reranker is not None:
            rerank_started = perf_counter()
            try:
                candidates = self._reranker.rerank(
                    query, candidates, top_k=self._config.final_top_k
                )
                reranker_applied = True
            except Exception as exc:  # noqa: BLE001 - RRF fallback is intentional
                reranker_fallback_reason = str(exc) or exc.__class__.__name__
                candidates = candidates[: self._config.final_top_k]
            rerank_ms = (perf_counter() - rerank_started) * 1000
        else:
            candidates = candidates[: self._config.final_top_k]
        return RetrievalResult(
            query=query,
            candidates=candidates,
            retrieval_strategy=strategy,
            elapsed_ms=(perf_counter() - started) * 1000,
            metadata={
                "dense_count": len(dense),
                "sparse_count": len(sparse),
                "fusion_count": fusion_count,
                "final_count": len(candidates),
                "embedding_ms": embedding_ms,
                "dense_search_ms": dense_ms,
                "sparse_search_ms": sparse_ms,
                "fusion_ms": fusion_ms,
                "rerank_ms": rerank_ms,
                "fallback_reason": fallback_reason,
                "reranker_applied": reranker_applied,
                "reranker_fallback_reason": reranker_fallback_reason,
            },
        )


__all__ = ["RetrievalService"]
