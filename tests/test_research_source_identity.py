from app.research.source_identity import (
    build_research_source_identity,
    canonical_resource_locator,
    normalize_source_family,
)


def test_browser_fragments_share_one_stable_source_locator() -> None:
    first = build_research_source_identity(
        resource_url="https://Example.org/paper?id=7#method",
        resource_title="Paper",
        source_kind="browser_selection",
        fallback_key="n1",
    )
    second = build_research_source_identity(
        resource_url="https://example.org/paper?id=7#results",
        resource_title="Paper",
        source_kind="browser_page",
        fallback_key="n2",
    )

    assert first.source_family == "browser"
    assert first.identity_quality == "locator"
    assert first.resource_locator == "https://example.org/paper?id=7"
    assert first.source_id == second.source_id


def test_pdf_and_word_provider_names_are_normalized_without_claiming_missing_locators() -> None:
    pdf = build_research_source_identity(
        resource_title="Control Paper.pdf",
        source_kind="browser_pdf_uia",
        fallback_key="pdf-note",
    )
    word = build_research_source_identity(
        resource_title="Draft Manuscript.docx",
        source_kind="word",
        fallback_key="word-note",
    )

    assert pdf.source_family == "pdf"
    assert word.source_family == "word"
    assert pdf.identity_quality == "title"
    assert word.identity_quality == "title"
    assert not pdf.resource_locator
    assert not word.resource_locator


def test_windows_paths_are_canonicalized_as_file_locators() -> None:
    locator = canonical_resource_locator(r"C:\Research\Paper.PDF")
    assert locator == "file:///c:/research/paper.pdf"


def test_unknown_sources_fall_back_to_note_local_identity() -> None:
    first = build_research_source_identity(source_kind="", fallback_key="note-a")
    second = build_research_source_identity(source_kind="", fallback_key="note-b")

    assert first.source_family == "other"
    assert first.identity_quality == "note"
    assert first.source_id != second.source_id


def test_source_family_normalization_is_small_and_provider_neutral() -> None:
    assert normalize_source_family("browser_selection") == "browser"
    assert normalize_source_family("browser_pdf_uia") == "pdf"
    assert normalize_source_family("word_com") == "word"
    assert normalize_source_family("windows_uia") == "desktop"
