from app.documents.models import DocumentSource, DocumentSourceType


def test_document_source_serialization():
    source = DocumentSource(
        source_id="doc-1",
        source_type=DocumentSourceType.PDF,
        title="paper",
        content="hello",
        metadata={"page": 1},
    )

    data = source.model_dump()

    assert data["source_id"] == "doc-1"
    assert data["metadata"]["page"] == 1


def test_document_source_accepts_reading_metadata():
    source = DocumentSource(
        source_id="selection-1",
        source_type=DocumentSourceType.SELECTION,
        title="selection",
        content="selected text",
        metadata={"document_id": "paper", "section": "method"},
    )

    assert source.metadata["section"] == "method"
