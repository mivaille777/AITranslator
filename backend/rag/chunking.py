from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass

from backend.rag.config import RagChunkingConfig
from backend.rag.document_tree import (
    DocumentParagraphNode,
    DocumentSectionNode,
    DocumentTreeBuilder,
)
from backend.rag.exceptions import RagInvariantError
from backend.rag.models import DocumentChunk, DocumentPage, NormalizedDocument, build_stable_chunk_id
from backend.rag.tokenization import HeuristicTokenCounter, TokenCounter

CHUNKER_VERSION = "hierarchical-structure-v2"

_SENTENCE_BREAK = re.compile(r"(?:[.!?。！？；;]+[\"'”’）)】》]*)(?=\s|$)|\n+")


@dataclass(frozen=True, slots=True)
class _ChunkSpan:
    start: int
    end: int
    section: DocumentSectionNode
    paragraph_start_index: int | None
    paragraph_end_index: int | None
    boundary_strategy: str


class StructureAwareChunker:
    """Hierarchy-first chunker for academic and structured documents.

    The chunker traverses section regions and groups complete paragraphs first.
    Token counts are soft/preferred/hard bounds rather than the primary source
    boundary. Sentence/token overlap is only used when one semantic paragraph
    exceeds the hard limit.
    """

    def __init__(
        self,
        config: RagChunkingConfig | None = None,
        token_counter: TokenCounter | None = None,
    ) -> None:
        self._config = config or RagChunkingConfig()
        self._token_counter = token_counter or HeuristicTokenCounter()

    @property
    def config(self) -> RagChunkingConfig:
        return self._config

    @property
    def token_counter(self) -> TokenCounter:
        return self._token_counter

    def chunk(self, document: NormalizedDocument) -> list[DocumentChunk]:
        text = document.text
        if not text or not text.strip():
            return []
        if not document.document.content_hash:
            raise RagInvariantError(
                "normalized document content_hash must not be empty"
            )

        tree = DocumentTreeBuilder.build(document)
        spans: list[_ChunkSpan] = []
        for section in tree.sections:
            spans.extend(self._chunk_section(text, section))

        chunks: list[DocumentChunk] = []
        for chunk_index, span in enumerate(spans):
            chunk_text = text[span.start : span.end]
            pages = self._intersecting_pages(span.start, span.end, document.pages)
            page_number = pages[0].page_number if pages else None
            metadata = self._build_metadata(document, span, pages)
            chunks.append(
                DocumentChunk(
                    chunk_id=build_stable_chunk_id(
                        document_hash=document.document.content_hash,
                        section_heading=span.section.heading,
                        chunk_index=chunk_index,
                        text=chunk_text,
                    ),
                    document_id=document.document.document_id,
                    text=chunk_text,
                    title=document.document.title,
                    section_heading=span.section.heading,
                    section_path=list(span.section.section_path),
                    hierarchy_level=span.section.level,
                    parent_section_id=span.section.parent_section_id or "",
                    chunk_type="paragraph_group",
                    page_number=page_number,
                    chunk_index=chunk_index,
                    paragraph_index=span.paragraph_start_index,
                    paragraph_end_index=span.paragraph_end_index,
                    start_char=span.start,
                    end_char=span.end,
                    token_count=self._token_counter.count(chunk_text),
                    language=document.document.language,
                    source_uri=document.document.source_uri,
                    document_hash=document.document.content_hash,
                    parser_version=str(document.metadata.get("parser_version", "")),
                    chunker_version=CHUNKER_VERSION,
                    metadata=metadata,
                )
            )
        return chunks

    def _chunk_section(
        self,
        text: str,
        section: DocumentSectionNode,
    ) -> list[_ChunkSpan]:
        paragraphs = list(section.paragraphs)
        if not paragraphs:
            return []

        spans: list[_ChunkSpan] = []
        buffer: list[DocumentParagraphNode] = []
        hard_limit = self._config.effective_hard_max_tokens

        for paragraph in paragraphs:
            paragraph_tokens = self._token_counter.count(paragraph.text)
            if paragraph_tokens > hard_limit:
                if buffer and self._buffer_tokens(text, buffer) <= self._config.minimum_tokens:
                    start = buffer[0].start_char
                    paragraph_start_index = buffer[0].paragraph_index
                    buffer = []
                    spans.extend(
                        self._split_oversized_range(
                            text,
                            section,
                            start=start,
                            end=paragraph.end_char,
                            paragraph_start_index=paragraph_start_index,
                            paragraph_end_index=paragraph.paragraph_index,
                        )
                    )
                else:
                    self._flush_buffer(spans, section, buffer)
                    buffer = []
                    spans.extend(
                        self._split_oversized_range(
                            text,
                            section,
                            start=paragraph.start_char,
                            end=paragraph.end_char,
                            paragraph_start_index=paragraph.paragraph_index,
                            paragraph_end_index=paragraph.paragraph_index,
                        )
                    )
                continue

            if not buffer:
                buffer.append(paragraph)
                continue

            combined_tokens = self._token_counter.count(
                text[buffer[0].start_char : paragraph.end_char]
            )
            current_tokens = self._buffer_tokens(text, buffer)
            if self._should_keep_paragraph_group(
                current_tokens=current_tokens,
                combined_tokens=combined_tokens,
            ):
                buffer.append(paragraph)
                continue

            self._flush_buffer(spans, section, buffer)
            buffer = [paragraph]

        self._flush_buffer(spans, section, buffer)
        return spans

    def _should_keep_paragraph_group(
        self,
        *,
        current_tokens: int,
        combined_tokens: int,
    ) -> bool:
        preferred = self._config.effective_preferred_max_tokens
        hard = self._config.effective_hard_max_tokens
        if combined_tokens > hard:
            return False
        if current_tokens < self._config.target_tokens and combined_tokens <= preferred:
            return True
        # Keep a short heading/lead paragraph attached to its first substantive
        # paragraph even when the combined unit exceeds the preferred target.
        return current_tokens <= self._config.minimum_tokens and combined_tokens <= hard

    def _split_oversized_range(
        self,
        text: str,
        section: DocumentSectionNode,
        *,
        start: int,
        end: int,
        paragraph_start_index: int,
        paragraph_end_index: int,
    ) -> list[_ChunkSpan]:
        start, end = self._trim_span(text, start, end)
        spans: list[_ChunkSpan] = []
        cursor = start
        while cursor < end:
            chunk_end = self._choose_fallback_end(text, cursor, end)
            chunk_start, chunk_end = self._trim_span(text, cursor, chunk_end)
            if chunk_start >= chunk_end:
                break
            spans.append(
                _ChunkSpan(
                    start=chunk_start,
                    end=chunk_end,
                    section=section,
                    paragraph_start_index=paragraph_start_index,
                    paragraph_end_index=paragraph_end_index,
                    boundary_strategy="sentence_fallback",
                )
            )
            if chunk_end >= end:
                break
            next_start = self._fallback_overlap_start(text, chunk_start, chunk_end)
            next_start, _ = self._trim_span(text, next_start, end)
            if next_start <= chunk_start:
                next_start = chunk_end
            cursor = next_start
        return spans

    def _choose_fallback_end(self, text: str, start: int, end: int) -> int:
        hard = self._config.effective_hard_max_tokens
        preferred = self._config.effective_preferred_max_tokens
        if self._token_counter.count(text[start:end]) <= hard:
            return end

        hard_end = self._largest_prefix_end(text, start, end, hard)
        preferred_end = self._largest_prefix_end(
            text,
            start,
            hard_end,
            min(preferred, hard),
        )
        sentence_boundaries = [
            match.end()
            for match in _SENTENCE_BREAK.finditer(text, start, hard_end)
            if start < match.end() <= hard_end
        ]
        before_preferred = [
            boundary for boundary in sentence_boundaries if boundary <= preferred_end
        ]
        if before_preferred:
            return before_preferred[-1]
        after_preferred = [
            boundary for boundary in sentence_boundaries if boundary > preferred_end
        ]
        if after_preferred:
            return after_preferred[0]
        return self._prefer_word_boundary(text, start, hard_end)

    def _fallback_overlap_start(self, text: str, chunk_start: int, chunk_end: int) -> int:
        if self._config.overlap_tokens == 0:
            return chunk_end

        low = chunk_start
        high = chunk_end
        while low < high:
            middle = (low + high) // 2
            if (
                self._token_counter.count(text[middle:chunk_end])
                <= self._config.overlap_tokens
            ):
                high = middle
            else:
                low = middle + 1
        overlap_start = low

        sentence_starts = [
            match.end()
            for match in _SENTENCE_BREAK.finditer(text, overlap_start, chunk_end)
            if match.end() < chunk_end
        ]
        if sentence_starts:
            return sentence_starts[0]
        return self._advance_to_token_boundary(text, overlap_start, chunk_end)

    def _buffer_tokens(
        self,
        text: str,
        buffer: list[DocumentParagraphNode],
    ) -> int:
        if not buffer:
            return 0
        return self._token_counter.count(
            text[buffer[0].start_char : buffer[-1].end_char]
        )

    @staticmethod
    def _flush_buffer(
        spans: list[_ChunkSpan],
        section: DocumentSectionNode,
        buffer: list[DocumentParagraphNode],
    ) -> None:
        if not buffer:
            return
        spans.append(
            _ChunkSpan(
                start=buffer[0].start_char,
                end=buffer[-1].end_char,
                section=section,
                paragraph_start_index=buffer[0].paragraph_index,
                paragraph_end_index=buffer[-1].paragraph_index,
                boundary_strategy="paragraph_group",
            )
        )

    def _largest_prefix_end(
        self,
        text: str,
        start: int,
        limit: int,
        token_limit: int,
    ) -> int:
        low = start + 1
        high = limit
        best = start
        while low <= high:
            middle = (low + high) // 2
            if self._token_counter.count(text[start:middle]) <= token_limit:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        return max(best, min(start + 1, limit))

    @staticmethod
    def _prefer_word_boundary(text: str, start: int, end: int) -> int:
        candidate = end
        while candidate > start and not text[candidate - 1].isspace():
            candidate -= 1
        return candidate if candidate > start else end

    @staticmethod
    def _advance_to_token_boundary(text: str, start: int, end: int) -> int:
        if start <= 0 or start >= end:
            return start
        if not (
            StructureAwareChunker._is_latin_word_char(text[start - 1])
            and StructureAwareChunker._is_latin_word_char(text[start])
        ):
            return start
        while start < end and StructureAwareChunker._is_latin_word_char(text[start]):
            start += 1
        return start

    @staticmethod
    def _is_latin_word_char(character: str) -> bool:
        return character.isascii() and (character.isalnum() or character in "_-'’")

    @staticmethod
    def _intersecting_pages(
        start: int,
        end: int,
        pages: list[DocumentPage],
    ) -> list[DocumentPage]:
        return sorted(
            (page for page in pages if start < page.end_char and end > page.start_char),
            key=lambda page: page.page_number,
        )

    @staticmethod
    def _build_metadata(
        document: NormalizedDocument,
        span: _ChunkSpan,
        pages: list[DocumentPage],
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            "source_kind": document.document.source_kind,
            "mime_type": document.document.mime_type,
            "boundary_strategy": span.boundary_strategy,
            "section_path": list(span.section.section_path),
            "hierarchy_level": span.section.level,
            "parent_section_id": span.section.parent_section_id or "",
            "paragraph_start": span.paragraph_start_index,
            "paragraph_end": span.paragraph_end_index,
        }
        if document.document.metadata:
            metadata["document_metadata"] = deepcopy(document.document.metadata)
        if document.metadata:
            metadata["normalized_document_metadata"] = deepcopy(document.metadata)
        if span.section.metadata:
            metadata["section_metadata"] = deepcopy(span.section.metadata)
        if pages:
            metadata["page_start"] = pages[0].page_number
            metadata["page_end"] = pages[-1].page_number
        return metadata

    @staticmethod
    def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end


def chunk_document(
    document: NormalizedDocument,
    *,
    config: RagChunkingConfig | None = None,
    token_counter: TokenCounter | None = None,
) -> list[DocumentChunk]:
    return StructureAwareChunker(config=config, token_counter=token_counter).chunk(
        document
    )


__all__ = ["CHUNKER_VERSION", "StructureAwareChunker", "chunk_document"]
