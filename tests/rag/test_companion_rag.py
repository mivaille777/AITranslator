from __future__ import annotations

from types import SimpleNamespace

from backend.rag.models import DocumentChunk, RetrievalCandidate, RetrievalResult
from backend.services.companion_chat_service import CompanionChatService


class RetrievalStub:
    def __init__(self) -> None:
        self.filters = None

    def retrieve(self, query, *, filters=None):
        self.filters = filters
        return RetrievalResult(
            query=query,
            retrieval_strategy="hybrid",
            candidates=[
                RetrievalCandidate(
                    chunk=DocumentChunk(
                        chunk_id="chunk-1",
                        document_id="doc-1",
                        text="Bounded evidence for the answer.",
                        title="Local Paper",
                        source_uri="file:///C:/papers/local.pdf",
                        section_heading="3.4",
                        page_number=12,
                        chunk_index=0,
                        end_char=32,
                    ),
                    rank=1,
                    rerank_score=0.9,
                )
            ],
        )


class ChatStub:
    prompt_id = "chat.stub@1"

    def __init__(self) -> None:
        self.request = None

    def execute(self, request):
        self.request = request
        return SimpleNamespace(
            session_id=request.session_id,
            user_message=request.user_message,
            output_text="Grounded answer [1]",
            provider="stub",
            model="stub-model",
            request_id=request.request_id,
        )


def test_companion_rag_applies_document_scope_and_returns_verified_contracts() -> None:
    retrieval = RetrievalStub()
    chat = ChatStub()
    service = CompanionChatService(chat_service=chat, retrieval_service=retrieval)

    result = service.send(
        session_id="session-1",
        user_message="What is bounded?",
        context_mode="general",
        knowledge_enabled=True,
        knowledge_document_ids=("doc-1",),
    )

    assert retrieval.filters.document_ids == ["doc-1"]
    assert result.output_text == "Grounded answer [1]"
    assert result.knowledge_enabled is True
    assert result.evidence[0].title == "Local Paper"
    assert result.citations[0].label == "[1]"
    assert chat.request.tool_name == "search_knowledge_base"
    assert "ALLOWED CITATIONS" in chat.request.tool_context


def test_companion_rag_degrades_without_fabricating_evidence() -> None:
    chat = ChatStub()
    service = CompanionChatService(chat_service=chat)

    result = service.send(
        session_id="session-1",
        user_message="Use my knowledge",
        context_mode="general",
        knowledge_enabled=True,
    )

    assert result.evidence == ()
    assert result.citations == ()
    assert result.knowledge_fallback_reason == "retrieval_unavailable"
    assert "do not cite" in chat.request.tool_context
