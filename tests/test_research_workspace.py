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
):
    return service.save(
        source_text=source_text,
        translated_text=f"translated:{source_text}",
        resource_url=resource_url,
        resource_title=resource_title,
        section_heading=section_heading,
        source_kind=source_kind,
        conversation_id=conversation_id,
    ).note


def test_research_workspace_groups_sources_and_counts_linked_conversations(tmp_path) -> None:
    service = ResearchNoteService(
        ResearchNoteStore(storage_path=tmp_path / "research.sqlite3")
    )
    _save(
        service,
        source_text="Selection A",
        resource_url="https://example.org/paper-a",
        resource_title="Paper A",
        section_heading="Method",
        conversation_id="chat-1",
    )
    _save(
        service,
        source_text="Selection B",
        resource_url="https://example.org/paper-a",
        resource_title="Paper A",
        section_heading="Results",
        conversation_id="chat-1",
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
    assert paper_a.linked_conversation_count == 1


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


def test_research_workspace_api_supports_detail_edit_and_delete(tmp_path) -> None:
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

    app = create_app()
    app.dependency_overrides[get_research_note_service] = lambda: service

    with TestClient(app) as client:
        workspace = client.get("/api/research/workspace?limit=100")
        detail = client.get(f"/api/research/notes/{note.note_id}")
        updated = client.patch(
            f"/api/research/notes/{note.note_id}",
            json={"user_note": "My synthesis"},
        )
        deleted = client.delete(f"/api/research/notes/{note.note_id}")
        missing = client.get(f"/api/research/notes/{note.note_id}")

    assert workspace.status_code == 200
    assert workspace.json()["total"] == 1
    assert workspace.json()["sources"][0]["note_count"] == 1
    assert detail.status_code == 200
    assert detail.json()["conversation_id"] == "chat-1"
    assert updated.status_code == 200
    assert updated.json()["user_note"] == "My synthesis"
    assert deleted.json() == {"deleted": True, "note_id": note.note_id}
    assert missing.status_code == 404
