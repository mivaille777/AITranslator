from __future__ import annotations

import re
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass

from backend.rag.config import RagChunkingConfig
from backend.rag.exceptions import RagInvariantError
from backend.rag.models import (
    DocumentChunk,
    DocumentPage,
    DocumentSection,
    NormalizedDocument,
    build_stable_chunk_id,
)
from backend.rag.tokenization import HeuristicTokenCounter, TokenCounter

CHUNKER_VERSION = "structure-aware-v1"

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n+")
_SENTENCE_BREAK = re.compile(r"(?:[.!?。！？；;]+[\"'”’）)】》]*)(?=\s|$)|\n+")


@dataclass(frozen=True, slots=True)
class _Region:
    start: int
    end: int
    heading: str = ""
    metadata: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class _ChunkSpan:
    start: int
    end: int
    heading: str
    section_metadata: dict[str, object] | None


class StructureAwareChunker:
    """Split normalized documents while retaining structure and source offsets."""

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

        spans: list[_ChunkSpan] = []
        for region in self._build_regions(text, document.sections):
            spans.extend(self._chunk_region(text, region))

        paragraph_spans = self._paragraph_spans(text, 0, len(text))
        chunks: list[DocumentChunk] = []
        for chunk_index, span in enumerate(spans):
            chunk_text = text[span.start : span.end]
            pages = self._intersecting_pages(span.start, span.end, document.pages)
            metadata = self._build_metadata(document, span, pages)
            page_number = pages[0].page_number if pages else None
            chunks.append(
                DocumentChunk(
                    chunk_id=build_stable_chunk_id(
                        document_hash=document.document.content_hash,
                        section_heading=span.heading,
                        chunk_index=chunk_index,
                        text=chunk_text,
                    ),
                    document_id=document.document.document_id,
                    text=chunk_text,
                    title=document.document.title,
                    section_heading=span.heading,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    paragraph_index=self._paragraph_index(span.start, paragraph_spans),
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

    def _chunk_region(self, text: str, region: _Region) -> list[_ChunkSpan]:
        region_start, region_end = self._trim_span(text, region.start, region.end)
        if region_start >= region_end:
            return []

        spans: list[_ChunkSpan] = []
        start = region_start
        while start < region_end:
            protected_prefix_end: int | None = None
            if (
                start == region_start
                and region.heading
                and text.startswith(region.heading, start)
            ):
                heading_end = start + len(region.heading)
                if (
                    self._token_counter.count(text[start:heading_end])
                    < self._config.target_tokens
                ):
                    body_start = heading_end
                    while body_start < region_end and text[body_start].isspace():
                        body_start += 1
                    protected_prefix_end = (
                        body_start if body_start < region_end else None
                    )
            end = self._choose_chunk_end(
                text,
                start,
                region_end,
                protected_prefix_end=protected_prefix_end,
            )
            start, end = self._trim_span(text, start, end)
            if start >= end:
                break
            spans.append(_ChunkSpan(start, end, region.heading, region.metadata))
            if end >= region_end:
                break
            next_start = self._choose_overlap_start(text, start, end)
            next_start, _ = self._trim_span(text, next_start, region_end)
            if next_start <= start:
                next_start = end
            start = next_start

        if (
            len(spans) >= 2
            and self._token_counter.count(text[spans[-1].start : spans[-1].end])
            < self._config.minimum_tokens
        ):
            previous = spans[-2]
            final = spans[-1]
            spans[-2:] = [
                _ChunkSpan(
                    previous.start,
                    final.end,
                    region.heading,
                    region.metadata,
                )
            ]
        return spans

    def _choose_chunk_end(
        self,
        text: str,
        start: int,
        limit: int,
        *,
        protected_prefix_end: int | None = None,
    ) -> int:
        if self._token_counter.count(text[start:limit]) <= self._config.target_tokens:
            return limit

        hard_limit = self._largest_prefix_end(
            text,
            start,
            limit,
            self._config.target_tokens,
        )
        minimum_end = self._largest_prefix_end(
            text,
            start,
            hard_limit,
            self._config.minimum_tokens,
        )

        structural_minimum = max(minimum_end, (protected_prefix_end or start) + 1)
        paragraph_end = self._last_boundary(
            (
                match.start()
                for match in _PARAGRAPH_BREAK.finditer(text, start, hard_limit)
            ),
            structural_minimum,
        )
        if paragraph_end is not None:
            return paragraph_end

        sentence_end = self._last_boundary(
            (
                match.end()
                for match in _SENTENCE_BREAK.finditer(text, start, hard_limit)
            ),
            structural_minimum,
        )
        if sentence_end is not None:
            return sentence_end

        return self._prefer_word_boundary(text, start, hard_limit)

    def _choose_overlap_start(self, text: str, chunk_start: int, chunk_end: int) -> int:
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
        paragraph_starts = [
            match.end()
            for match in _PARAGRAPH_BREAK.finditer(text, overlap_start, chunk_end)
            if match.end() < chunk_end
        ]
        if paragraph_starts:
            return paragraph_starts[0]
        if sentence_starts:
            return sentence_starts[0]
        return self._advance_to_token_boundary(text, overlap_start, chunk_end)

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
    def _last_boundary(boundaries: Iterable[int], minimum: int) -> int | None:
        candidates = [boundary for boundary in boundaries if boundary >= minimum]
        return candidates[-1] if candidates else None

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

    @classmethod
    def _build_regions(
        cls,
        text: str,
        sections: list[DocumentSection],
    ) -> list[_Region]:
        valid_sections = sorted(
            (
                section
                for section in sections
                if section.start_char < section.end_char
                and section.start_char < len(text)
                and section.end_char > 0
            ),
            key=lambda section: (section.start_char, section.end_char),
        )
        if not valid_sections:
            return [_Region(0, len(text))]

        regions: list[_Region] = []
        cursor = 0
        for section in valid_sections:
            start = max(cursor, section.start_char, 0)
            end = min(max(start, section.end_char), len(text))
            if cursor < start:
                regions.append(_Region(cursor, start))
            if start < end:
                regions.append(
                    _Region(
                        start,
                        end,
                        section.heading,
                        deepcopy(section.metadata),
                    )
                )
                cursor = end
        if cursor < len(text):
            regions.append(_Region(cursor, len(text)))
        return regions

    @staticmethod
    def _paragraph_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        cursor = start
        for match in _PARAGRAPH_BREAK.finditer(text, start, end):
            left, right = StructureAwareChunker._trim_span(text, cursor, match.start())
            if left < right:
                spans.append((left, right))
            cursor = match.end()
        left, right = StructureAwareChunker._trim_span(text, cursor, end)
        if left < right:
            spans.append((left, right))
        return spans

    @staticmethod
    def _paragraph_index(position: int, spans: list[tuple[int, int]]) -> int | None:
        for index, (start, end) in enumerate(spans):
            if start <= position < end:
                return index
            if position < start:
                return index
        return len(spans) - 1 if spans else None

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
        }
        if document.document.metadata:
            metadata["document_metadata"] = deepcopy(document.document.metadata)
        if document.metadata:
            metadata["normalized_document_metadata"] = deepcopy(document.metadata)
        if span.section_metadata:
            metadata["section_metadata"] = deepcopy(span.section_metadata)
        if len(pages) > 1:
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
