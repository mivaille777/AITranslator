from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from itertools import pairwise

from backend.rag.chunking import CHUNKER_VERSION, StructureAwareChunker, chunk_document
from backend.rag.config import RagChunkingConfig
from backend.rag.models import (
    DocumentPage,
    DocumentSection,
    KnowledgeDocument,
    NormalizedDocument,
)


def make_document(
    text: str,
    *,
    sections: list[DocumentSection] | None = None,
    pages: list[DocumentPage] | None = None,
    language: str = "unknown",
) -> NormalizedDocument:
    content_hash = sha256(text.encode("utf-8")).hexdigest()
    return NormalizedDocument(
        document=KnowledgeDocument(
            document_id=f"doc_{content_hash[:24]}",
            title="Test Paper",
            source_uri="file:///test-paper.md",
            source_kind="markdown",
            mime_type="text/markdown",
            language=language,
            content_hash=content_hash,
            metadata={"author": "Tester"},
        ),
        text=text,
        sections=sections or [],
        pages=pages or [],
        metadata={"parser_name": "test", "parser_version": "test-v1"},
    )


def make_chunker(
    *,
    target: int = 12,
    overlap: int = 3,
    minimum: int = 4,
) -> StructureAwareChunker:
    return StructureAwareChunker(
        RagChunkingConfig(
            target_tokens=target,
            overlap_tokens=overlap,
            minimum_tokens=minimum,
        )
    )


def section_for(text: str, heading: str, start: int, end: int) -> DocumentSection:
    return DocumentSection(
        heading=heading,
        level=1,
        text=text[start:end],
        start_char=start,
        end_char=end,
        metadata={"kind": "section"},
    )


def test_small_single_section_document_produces_one_chunk() -> None:
    text = "Introduction\n\nGaussian processes guide PID tuning."
    section = section_for(text, "Introduction", 0, len(text))

    chunks = make_chunker(target=30, overlap=4, minimum=5).chunk(
        make_document(text, sections=[section])
    )

    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].section_heading == "Introduction"
    assert chunks[0].chunker_version == CHUNKER_VERSION


def test_heading_stays_with_some_body_text_when_section_requires_splitting() -> None:
    text = "Methods\n\n" + " ".join(f"detail{index}" for index in range(30))
    section = section_for(text, "Methods", 0, len(text))

    chunks = make_chunker(target=8, overlap=2, minimum=1).chunk(
        make_document(text, sections=[section])
    )

    assert chunks[0].text.startswith("Methods\n\n")
    assert chunks[0].text != "Methods"


def test_multiple_sections_are_not_combined() -> None:
    text = "Introduction\n\nShort background.\n\nMethods\n\nShort method."
    methods_start = text.index("Methods")
    sections = [
        section_for(text, "Introduction", 0, methods_start),
        section_for(text, "Methods", methods_start, len(text)),
    ]

    chunks = make_chunker(target=100, overlap=10, minimum=10).chunk(
        make_document(text, sections=sections)
    )

    assert [chunk.section_heading for chunk in chunks] == ["Introduction", "Methods"]
    assert "Methods" not in chunks[0].text
    assert chunks[1].text.startswith("Methods")


def test_long_paragraph_uses_hard_splits_with_bounded_chunks() -> None:
    text = " ".join(f"word{index}" for index in range(80))

    chunks = make_chunker(target=12, overlap=3, minimum=4).chunk(make_document(text))

    assert len(chunks) > 2
    assert all(chunk.token_count <= 12 for chunk in chunks)
    assert chunks[0].start_char == 0
    assert chunks[-1].end_char == len(text)


def test_mixed_chinese_and_english_text_is_split_deterministically() -> None:
    text = "高斯过程用于控制。GP-UCB tunes PID。" * 8
    chunker = make_chunker(target=16, overlap=4, minimum=4)

    first = chunker.chunk(make_document(text, language="mixed"))
    second = chunker.chunk(make_document(text, language="mixed"))

    assert len(first) > 1
    assert [chunk.text for chunk in first] == [chunk.text for chunk in second]
    assert all(chunk.language == "mixed" for chunk in first)


def test_overlap_reuses_a_bounded_suffix_of_previous_chunk() -> None:
    text = " ".join(f"term{index}" for index in range(40))

    chunks = make_chunker(target=10, overlap=3, minimum=3).chunk(make_document(text))

    for previous, current in pairwise(chunks):
        overlap_start = max(previous.start_char, current.start_char)
        overlap_end = min(previous.end_char, current.end_char)
        assert overlap_start < overlap_end
        shared = text[overlap_start:overlap_end].strip()
        assert 0 < make_chunker().token_counter.count(shared) <= 3


def test_overlap_is_retained_for_chinese_text_without_spaces() -> None:
    text = "甲乙丙丁戊己庚辛壬癸" * 4

    chunks = make_chunker(target=10, overlap=3, minimum=3).chunk(make_document(text))

    assert len(chunks) > 1
    for previous, current in pairwise(chunks):
        assert current.start_char < previous.end_char
        shared = text[current.start_char : previous.end_char]
        assert 0 < make_chunker().token_counter.count(shared) <= 3


def test_small_final_chunk_merges_with_compatible_previous_chunk() -> None:
    text = " ".join(f"word{index}" for index in range(13))

    chunks = make_chunker(target=10, overlap=1, minimum=5).chunk(make_document(text))

    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].token_count == 13


def test_page_number_is_inherited_from_chunk_start() -> None:
    first = "one two three four five six"
    second = "seven eight nine ten eleven twelve"
    text = f"{first}\n\n{second}"
    pages = [
        DocumentPage(page_number=1, text=first, start_char=0, end_char=len(first)),
        DocumentPage(
            page_number=2,
            text=second,
            start_char=len(first) + 2,
            end_char=len(text),
        ),
    ]

    chunks = make_chunker(target=6, overlap=1, minimum=2).chunk(
        make_document(text, pages=pages)
    )

    assert chunks[0].page_number == 1
    assert chunks[-1].page_number == 2


def test_cross_page_chunk_records_page_range_metadata() -> None:
    first = "Page one content."
    second = "Page two content."
    text = f"{first}\n\n{second}"
    pages = [
        DocumentPage(page_number=1, text=first, start_char=0, end_char=len(first)),
        DocumentPage(
            page_number=2,
            text=second,
            start_char=len(first) + 2,
            end_char=len(text),
        ),
    ]

    chunk = make_chunker(target=30, overlap=3, minimum=3).chunk(
        make_document(text, pages=pages)
    )[0]

    assert chunk.page_number == 1
    assert chunk.metadata["page_start"] == 1
    assert chunk.metadata["page_end"] == 2


def test_character_offsets_slice_the_original_text_exactly() -> None:
    text = "Alpha paragraph.\n\nBeta paragraph has more words.\n\nGamma paragraph."

    chunks = make_chunker(target=8, overlap=2, minimum=2).chunk(make_document(text))

    assert all(
        text[chunk.start_char : chunk.end_char] == chunk.text for chunk in chunks
    )
    assert [chunk.start_char for chunk in chunks] == sorted(
        chunk.start_char for chunk in chunks
    )


def test_chunk_ids_are_stable_and_change_with_content() -> None:
    text = "Stable chunk input with enough words for a deterministic identifier."
    chunker = make_chunker(target=30, overlap=3, minimum=3)

    first = chunker.chunk(make_document(text))
    repeated = chunker.chunk(make_document(text))
    changed = chunker.chunk(make_document(f"{text} Changed."))

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in repeated]
    assert first[0].chunk_id != changed[0].chunk_id


def test_same_input_is_fully_deterministic() -> None:
    text = "One sentence. Two sentence. 三个句子。四个句子。" * 5
    document = make_document(text)
    chunker = make_chunker(target=10, overlap=2, minimum=3)

    first = chunker.chunk(document)
    second = chunker.chunk(document)

    assert [chunk.model_dump() for chunk in first] == [
        chunk.model_dump() for chunk in second
    ]


def test_empty_document_returns_empty_list() -> None:
    document = make_document("")

    assert chunk_document(document) == []


def test_chunking_does_not_modify_normalized_document() -> None:
    text = "Heading\n\nFirst paragraph.\n\nSecond paragraph with more content."
    document = make_document(
        text,
        sections=[section_for(text, "Heading", 0, len(text))],
    )
    original = deepcopy(document).model_dump()

    make_chunker(target=7, overlap=2, minimum=2).chunk(document)

    assert document.model_dump() == original


def test_paragraph_index_tracks_the_chunk_start() -> None:
    text = "First paragraph words.\n\nSecond paragraph words.\n\nThird paragraph words."

    chunks = make_chunker(target=4, overlap=0, minimum=2).chunk(make_document(text))

    assert [chunk.paragraph_index for chunk in chunks] == [0, 1, 2]


def test_source_and_parser_metadata_are_preserved() -> None:
    text = "A compact source metadata example."

    chunk = make_chunker(target=20, overlap=2, minimum=2).chunk(make_document(text))[0]

    assert chunk.document_hash == sha256(text.encode("utf-8")).hexdigest()
    assert chunk.parser_version == "test-v1"
    assert chunk.metadata["source_kind"] == "markdown"
    assert chunk.metadata["document_metadata"] == {"author": "Tester"}
