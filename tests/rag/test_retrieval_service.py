from __future__ import annotations

import pytest

from backend.rag.config import RagRetrievalConfig
from backend.rag.exceptions import RagRetrievalError
from backend.rag.models import DocumentChunk, RetrievalCandidate
from backend.rag.retrieval_service import RetrievalService
from backend.rag.stores.base import VectorSearchFilter


def item(chunk_id: str, *, dense=False, sparse=False, rank=1, document_id="doc"):
    return RetrievalCandidate(
        chunk=DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            text=chunk_id,
            chunk_index=0,
        ),
        dense_score=0.8 if dense else None,
        sparse_score=3.0 if sparse else None,
        rank=rank,
    )


class Embedding:
    model_name = "fake"
    dimension = 2

    def __init__(self, fail=False):
        self.fail = fail

    def embed_query(self, _text):
        if self.fail:
            raise RuntimeError("dense failed")
        return [1.0, 0.0]

    def embed_documents(self, _texts):
        return []


class VectorStore:
    def __init__(self, results=None, fail=False):
        self.results = results or []
        self.fail = fail
        self.filters = None

    def search(self, _vector, *, top_k, filters=None):
        self.filters = filters
        if self.fail:
            raise RuntimeError("dense failed")
        return self.results[:top_k]


class Sparse:
    def __init__(self, results=None, fail=False):
        self.results = results or []
        self.fail = fail
        self.filters = None

    def search(self, _query, top_k, filters=None):
        self.filters = filters
        if self.fail:
            raise RuntimeError("sparse failed")
        return self.results[:top_k]


def service(*, dense=None, sparse=None, dense_fail=False, sparse_fail=False):
    vector_store = VectorStore(dense, dense_fail)
    sparse_store = Sparse(sparse, sparse_fail)
    return (
        RetrievalService(
            embedding_provider=Embedding(),
            vector_store=vector_store,
            sparse_retriever=sparse_store,
            config=RagRetrievalConfig(
                dense_top_k=30,
                sparse_top_k=30,
                fusion_top_k=20,
                final_top_k=8,
            ),
        ),
        vector_store,
        sparse_store,
    )


def test_hybrid_retrieval_fuses_and_deduplicates() -> None:
    retrieval, *_ = service(
        dense=[item("shared", dense=True), item("dense", dense=True, rank=2)],
        sparse=[item("shared", sparse=True), item("sparse", sparse=True, rank=2)],
    )

    result = retrieval.retrieve("query")

    assert result.retrieval_strategy == "hybrid"
    assert [candidate.chunk.chunk_id for candidate in result.candidates] == [
        "shared",
        "dense",
        "sparse",
    ]
    assert result.metadata["fusion_count"] == 3


def test_filters_are_pushed_to_both_stores() -> None:
    retrieval, vector, sparse = service()
    filters = VectorSearchFilter(document_ids=["doc"], language="en")

    retrieval.retrieve("query", filters=filters)

    assert vector.filters is filters
    assert sparse.filters is filters


def test_dense_failure_degrades_to_sparse_only() -> None:
    retrieval, *_ = service(
        sparse=[item("sparse", sparse=True)],
        dense_fail=True,
    )

    result = retrieval.retrieve("query")

    assert result.retrieval_strategy == "sparse-only"
    assert result.candidates[0].chunk.chunk_id == "sparse"
    assert result.metadata["fallback_reason"] == "dense failed"


def test_sparse_failure_degrades_to_dense_only() -> None:
    retrieval, *_ = service(
        dense=[item("dense", dense=True)],
        sparse_fail=True,
    )

    result = retrieval.retrieve("query")

    assert result.retrieval_strategy == "dense-only"
    assert result.candidates[0].chunk.chunk_id == "dense"


def test_both_fail_raise_explicit_retrieval_error() -> None:
    retrieval, *_ = service(dense_fail=True, sparse_fail=True)

    with pytest.raises(RagRetrievalError, match="dense and sparse"):
        retrieval.retrieve("query")


def test_latency_and_count_metadata_are_present() -> None:
    retrieval, *_ = service(
        dense=[item("dense", dense=True)],
        sparse=[item("sparse", sparse=True)],
    )

    result = retrieval.retrieve("query")

    assert result.elapsed_ms >= 0
    assert result.metadata["dense_count"] == 1
    assert result.metadata["sparse_count"] == 1
    assert result.metadata["dense_search_ms"] >= 0
    assert result.metadata["sparse_search_ms"] >= 0
    assert result.metadata["fusion_ms"] >= 0
    assert result.metadata["embedding_ms"] >= 0
    assert result.metadata["rerank_ms"] >= 0
    assert result.metadata["final_count"] == 2


def test_reranker_is_applied_and_failure_falls_back_to_rrf() -> None:
    class Reranker:
        def __init__(self, fail=False):
            self.fail = fail

        def rerank(self, _query, candidates, *, top_k):
            if self.fail:
                raise RuntimeError("rerank failed")
            return list(reversed(candidates))[:top_k]

    dense = [item("first", dense=True), item("second", dense=True, rank=2)]
    retrieval, *_ = service(dense=dense)
    retrieval._reranker = Reranker()
    applied = retrieval.retrieve("query")
    assert applied.metadata["reranker_applied"] is True
    assert applied.candidates[0].chunk.chunk_id == "second"

    retrieval._reranker = Reranker(fail=True)
    fallback = retrieval.retrieve("query")
    assert fallback.metadata["reranker_applied"] is False
    assert fallback.metadata["reranker_fallback_reason"] == "rerank failed"
