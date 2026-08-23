from __future__ import annotations

import json
from types import SimpleNamespace

from backend.rag.models import DocumentChunk, RetrievalCandidate, RetrievalResult
from backend.rag.query_planner import (
    MAX_RAG_SUBQUERIES,
    RagQueryPlan,
    RagQueryPlanner,
    merge_query_results,
)


class Client:
    def __init__(self, response: str = "", failure: Exception | None = None) -> None:
        self.response = response
        self.failure = failure
        self.calls: list[dict] = []

    def complete(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.failure is not None:
            raise self.failure
        return self.response


def _planner(client: Client) -> RagQueryPlanner:
    return RagQueryPlanner(
        text_service=SimpleNamespace(
            provider=SimpleNamespace(client=client),
            provider_name="fake",
            model="planner-model",
        )
    )


def _candidate(chunk_id: str, rank: int) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk=DocumentChunk(
            chunk_id=chunk_id,
            document_id=f"doc-{chunk_id}",
            text=f"Evidence for {chunk_id}",
            chunk_index=rank - 1,
            start_char=0,
            end_char=20,
        ),
        rerank_score=1.0 / rank,
        rank=rank,
    )


def test_complex_query_returns_typed_bounded_plan() -> None:
    client = Client(
        json.dumps(
            {
                "original_query": "model supplied value is ignored",
                "rewritten_query": "M10 and C8 comparison",
                "subqueries": [
                    "M10 mechanism",
                    "C8 mechanism",
                    "M10 vs C8 results",
                    "must be truncated",
                ],
            }
        )
    )
    planner = _planner(client)

    plan = planner.plan("论文里为什么 M10 比 C8 好？")

    assert isinstance(plan, RagQueryPlan)
    assert plan.original_query == "论文里为什么 M10 比 C8 好？"
    assert plan.rewritten_query == "M10 and C8 comparison"
    assert plan.subqueries == [
        "M10 mechanism",
        "C8 mechanism",
        "M10 vs C8 results",
    ]
    assert len(plan.subqueries) == MAX_RAG_SUBQUERIES
    assert len(client.calls) == 1
    prompt = json.loads(client.calls[0]["user_prompt"])
    assert prompt["policy"]["recursive_decomposition"] is False


def test_simple_query_uses_original_without_calling_planner() -> None:
    client = Client(failure=AssertionError("must not be called"))

    plan = _planner(client).plan("What is M10?")

    assert plan == RagQueryPlan(
        original_query="What is M10?",
        rewritten_query="What is M10?",
        subqueries=[],
    )
    assert plan.retrieval_queries == ("What is M10?",)
    assert client.calls == []


def test_planner_failure_and_malformed_output_fall_back_to_original_query() -> None:
    query = "Compare M10 versus C8"

    failed = _planner(Client(failure=OSError("planner unavailable"))).plan(query)
    malformed = _planner(Client(response="not-json")).plan(query)

    for plan in (failed, malformed):
        assert plan.original_query == query
        assert plan.rewritten_query == query
        assert plan.subqueries == []
        assert plan.retrieval_queries == (query,)


def test_multi_query_merge_dedupes_chunks_and_applies_result_limit() -> None:
    results = [
        RetrievalResult(
            query="M10",
            candidates=[_candidate("shared", 1), _candidate("m10", 2)],
            retrieval_strategy="hybrid",
            elapsed_ms=2.0,
        ),
        RetrievalResult(
            query="C8",
            candidates=[_candidate("shared", 1), _candidate("c8", 2)],
            retrieval_strategy="hybrid",
            elapsed_ms=3.0,
        ),
    ]

    merged = merge_query_results("M10 versus C8", results, limit=2)

    assert merged.query == "M10 versus C8"
    assert merged.retrieval_strategy == "multi-query"
    assert [item.chunk.chunk_id for item in merged.candidates] == ["shared", "c8"]
    assert len({item.chunk.chunk_id for item in merged.candidates}) == 2
    assert merged.metadata["retrieval_queries"] == ["M10", "C8"]
    assert merged.metadata["multi_query_fusion"] is True
