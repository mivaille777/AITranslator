from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, Field

from backend.agent_tools.base import (
    AgentToolExecutionResult,
    AgentToolInvocationContext,
    AgentToolModel,
    TypedAgentToolDefinition,
    typed_tool_definition,
)
from backend.rag.models import RetrievalCandidate
from backend.rag.stores.base import VectorSearchFilter


class KnowledgeSearchArgs(AgentToolModel):
    query: str = Field(min_length=1, max_length=4_000)
    document_scope: str = Field(default="", max_length=8_000)
    document_ids: list[str] = Field(default_factory=list, max_length=100)
    top_k: int | None = Field(default=None, ge=1, le=50)


class KnowledgeSearchPlannerArgs(AgentToolModel):
    query: str = Field(min_length=1, max_length=4_000)
    document_scope: str = Field(default="", max_length=8_000)


class KnowledgeSearchResultItem(AgentToolModel):
    chunk_id: str
    document_id: str
    text: str
    title: str = ""
    source_uri: str = ""
    section_heading: str = ""
    page_number: int | None = Field(default=None, ge=1)
    rank: int | None = Field(default=None, ge=1)
    dense_score: float | None = None
    sparse_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResultData(AgentToolModel):
    query: str
    retrieval_strategy: str
    results: list[KnowledgeSearchResultItem] = Field(default_factory=list)
    elapsed_ms: float = Field(ge=0.0)
    fallback_reason: str = ""


def _document_ids(args: KnowledgeSearchArgs) -> list[str]:
    scoped = args.document_scope.replace("\n", ",").split(",")
    candidates = [*args.document_ids, *scoped]
    normalized: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        document_id = str(value or "").strip()
        if document_id and document_id not in seen:
            normalized.append(document_id)
            seen.add(document_id)
    return normalized


def _result_item(candidate: RetrievalCandidate) -> dict[str, Any]:
    chunk = candidate.chunk
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "text": chunk.text,
        "title": chunk.title,
        "source_uri": chunk.source_uri,
        "section_heading": chunk.section_heading,
        "page_number": chunk.page_number,
        "rank": candidate.rank,
        "dense_score": candidate.dense_score,
        "sparse_score": candidate.sparse_score,
        "fusion_score": candidate.fusion_score,
        "rerank_score": candidate.rerank_score,
        "metadata": dict(candidate.metadata),
    }


class KnowledgeAgentTools:
    """Agent-facing boundary over local hybrid knowledge retrieval."""

    def __init__(self, *, retrieval_service: Any | None) -> None:
        self._retrieval_service = retrieval_service

    def search_knowledge_base(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        typed = cast(KnowledgeSearchArgs, args)
        if self._retrieval_service is None:
            raise RuntimeError("Knowledge retrieval service is unavailable.")

        document_ids = _document_ids(typed)
        filters = (
            VectorSearchFilter(document_ids=document_ids) if document_ids else None
        )
        try:
            retrieval = self._retrieval_service.retrieve(
                typed.query,
                filters=filters,
            )
        except Exception as exc:
            detail = str(exc) or exc.__class__.__name__
            raise RuntimeError(f"Knowledge retrieval failed: {detail}") from exc

        candidates = retrieval.candidates
        if typed.top_k is not None:
            candidates = candidates[: typed.top_k]
        results = [_result_item(candidate) for candidate in candidates]
        fallback_reason = str(
            retrieval.metadata.get("fallback_reason")
            or retrieval.metadata.get("reranker_fallback_reason")
            or ""
        )
        if results:
            output_text = "Knowledge search results:\n" + "\n".join(
                f"- {item['title'] or item['document_id']}: {item['text']}"
                for item in results
            )
        else:
            output_text = "No matching knowledge found."
        return AgentToolExecutionResult(
            tool_name="search_knowledge_base",
            output_text=output_text,
            effect="read",
            request_id=context.request_id,
            data={
                "query": retrieval.query,
                "retrieval_strategy": retrieval.retrieval_strategy,
                "results": results,
                "elapsed_ms": retrieval.elapsed_ms,
                "fallback_reason": fallback_reason,
            },
        )


def build_knowledge_tool_definitions(
    tools: KnowledgeAgentTools,
) -> tuple[TypedAgentToolDefinition, ...]:
    return (
        typed_tool_definition(
            name="search_knowledge_base",
            title="Search knowledge base",
            description="Search indexed local documents with hybrid dense and sparse retrieval.",
            category="knowledge",
            effect="read",
            requires_reading_context=False,
            requires_confirmation=False,
            args_model=KnowledgeSearchArgs,
            result_model=KnowledgeSearchResultData,
            executor=tools.search_knowledge_base,
            planner_args_model=KnowledgeSearchPlannerArgs,
            retry_policy="safe",
        ),
    )


__all__ = [
    "KnowledgeAgentTools",
    "KnowledgeSearchArgs",
    "KnowledgeSearchPlannerArgs",
    "KnowledgeSearchResultData",
    "KnowledgeSearchResultItem",
    "build_knowledge_tool_definitions",
]
