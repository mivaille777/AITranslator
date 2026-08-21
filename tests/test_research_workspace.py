from __future__ import annotations

from fastapi.testclient import TestClient

from app.research.notes import ResearchNoteStore
from backend.api.dependencies import get_research_note_service
from backend.main import create_app
from backend.services.research_note_service import ResearchNoteService


def _save(
    service: ResearchNoteService,
    *,
    source_text: str,
    resource_url: str,
    resource_title: str,
    section_heading: str,
    source_kind: str = "browser_selection",
    conversation_id: str = "",
    ai_content: str = "",
    user_note: str = "",
):
    return service.save(
        source_text=source_text,
        translated_text=f"translated:{source_text}",
        resource_url=resource_url,
        resource_title=resource_title,
        section_heading=section_heading,
        source_kind=source_kind,
        conversation_id=conversation_id,
        ai_content=ai_content,
        user_note=user_note,
    ).note


def test_research_workspace_groups_sources_and_counts_linked_conversations(tmp_path) -> None:
    service = ResearchNoteService(
        ResearchNoteStore(storage_path=tmp_path / "research.sqlite3")
    )
    _save(
        service,
        source_text="Selection A",
        resource_url="https://example.org/paper-a#method",
        resource_title="Paper A",
        section_heading="Method",
        conversation_id="chat-1",
        user_note="Compare with baseline.",
    )
    _save(
        service,
        source_text="Selection B",
        resource_url="https://example.org/paper-a#results",
        resource_title="Paper A",
        section_heading="Results",
        conversation_id="chat-1",
        ai_content="The result supports the mechanism.",
    )
    _save(
        service,
        source_text="Selection C",
        resource_url="file:///paper-b.pdf",
        resource_title="Paper B",
        section_heading="Introduction",
        source_kind="pdf",
        conversation_id="chat-2",
    )

    sources = service.list_sources(limit=100)

    assert len(sources) == 2
    paper_a = next(item for item in sources if item.display_title == "Paper A")
    assert paper_a.note_count == 2
    assert paper_a.section_count == 2
    assert paper_a.linked_conversation_count == 1
    assert paper_a.annotation_count == 1
    assert paper_a.ai_evidence_count == 1
    assert paper_a.source_family == "browser"
    assert paper_a.identity_quality == "locator"

    profile = service.get_source(paper_a.source_id, limit=100)
    assert profile is not None
    assert {section.heading for section in profile.sections} == {"Method", "Results"}


def test_research_note_annotation_can_be_updated_and_cleared(tmp_path) -> None:
    service = ResearchNoteService(
        ResearchNoteStore(storage_path=tmp_path / "research.sqlite3")
    )
    note = _save(
        service,
        source_text="Selection A",
        resource_url="https://example.org/paper-a",
        resource_title="Paper A",
        section_heading="Method",
    )

    updated = service.update_user_note(note.note_id, "Compare with baseline M08.")
    assert updated is not None
    assert updated.user_note == "Compare with baseline M08."

    cleared = service.update_user_note(note.note_id, "")
    assert cleared is not None
    assert cleared.user_note == ""


def test_research_workspace_api_supports_source_profile_detail_edit_and_delete(tmp_path) -> None:
    service = ResearchNoteService(
        ResearchNoteStore(storage_path=tmp_path / "research.sqlite3")
    )
    note = _save(
        service,
        source_text="Selection A",
        resource_url="https://example.org/paper-a",
        resource_title="Paper A",
        section_heading="Method",
        conversation_id="chat-1",
    )
    source_id = service.list_sources(limit=100)[0].source_id

    app = create_app()
    app.dependency_overrides[get_research_note_service] = lambda: service

    with TestClient(app) as client:
        workspace = client.get("/api/research/workspace?limit=100")
        source = client.get(f"/api/research/sources/{source_id}")
        detail = client.get(f"/api/research/notes/{note.note_id}")
        updated = client.patch(
            f"/api/research/notes/{note.note_id}",
            json={"user_note": "My synthesis"},
        )
        deleted = client.delete(f"/api/research/notes/{note.note_id}")
        missing = client.get(f"/api/research/notes/{note.note_id}")
        missing_source = client.get(f"/api/research/sources/{source_id}")

    assert workspace.status_code == 200
    assert workspace.json()["total"] == 1
    assert workspace.json()["sources"][0]["note_count"] == 1
    assert workspace.json()["sources"][0]["source_family"] == "browser"
    assert source.status_code == 200
    assert source.json()["source_id"] == source_id
    assert source.json()["sections"][0]["heading"] == "Method"
    assert detail.status_code == 200
    assert detail.json()["conversation_id"] == "chat-1"
    assert updated.status_code == 200
    assert updated.json()["user_note"] == "My synthesis"
    assert deleted.json() == {"deleted": True, "note_id": note.note_id}
    assert missing.status_code == 404
    assert missing_source.status_code == 404
