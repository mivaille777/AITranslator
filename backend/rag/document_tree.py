from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256

from backend.rag.models import DocumentPage, DocumentSection, NormalizedDocument


@dataclass(frozen=True, slots=True)
class DocumentParagraphNode:
    """Atomic prose block retained with exact source provenance."""

    node_id: str
    paragraph_index: int
    start_char: int
    end_char: int
    text: str
    page_start: int | None = None
    page_end: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentSectionNode:
    """A section/subsection in document order with its hierarchy path."""

    node_id: str
    heading: str
    level: int
    section_path: tuple[str, ...]
    parent_section_id: str | None
    start_char: int
    end_char: int
    paragraphs: tuple[DocumentParagraphNode, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
    synthetic: bool = False


@dataclass(frozen=True, slots=True)
class DocumentTree:
    document_id: str
    sections: tuple[DocumentSectionNode, ...]


class DocumentTreeBuilder:
    """Build a hierarchy-first representation from normalized parser offsets.

    Parser sections remain non-overlapping source regions. The tree adds the
    conceptual parent/child relationship by heading level while paragraphs are
    retained as atomic source spans inside each region.
    """

    @classmethod
    def build(cls, document: NormalizedDocument) -> DocumentTree:
        text = document.text
        if not text:
            return DocumentTree(document_id=document.document.document_id, sections=())

        valid_sections = cls._valid_sections(text, document.sections)
        regions = cls._regions(text, valid_sections)
        paragraph_index = 0
        section_nodes: list[DocumentSectionNode] = []
        hierarchy_stack: list[DocumentSectionNode] = []

        for region_index, (start, end, section) in enumerate(regions):
            if start >= end:
                continue
            heading = section.heading.strip() if section is not None else ""
            level = section.level if section is not None else 0
            synthetic = section is None

            if synthetic:
                parent_section_id = None
                section_path: tuple[str, ...] = ()
                hierarchy_stack.clear()
            else:
                while hierarchy_stack and hierarchy_stack[-1].level >= level:
                    hierarchy_stack.pop()
                parent = hierarchy_stack[-1] if hierarchy_stack else None
                parent_section_id = parent.node_id if parent else None
                section_path = (
                    (*parent.section_path, heading) if parent else (heading,)
                )

            node_id = cls._section_id(
                document.document.document_id,
                region_index,
                start,
                heading,
            )
            paragraphs: list[DocumentParagraphNode] = []
            for paragraph_start, paragraph_end in cls._paragraph_spans(text, start, end):
                page_start, page_end = cls._page_range(
                    paragraph_start,
                    paragraph_end,
                    document.pages,
                )
                paragraphs.append(
                    DocumentParagraphNode(
                        node_id=f"{node_id}:p{paragraph_index}",
                        paragraph_index=paragraph_index,
                        start_char=paragraph_start,
                        end_char=paragraph_end,
                        text=text[paragraph_start:paragraph_end],
                        page_start=page_start,
                        page_end=page_end,
                    )
                )
                paragraph_index += 1

            node = DocumentSectionNode(
                node_id=node_id,
                heading=heading,
                level=level,
                section_path=section_path,
                parent_section_id=parent_section_id,
                start_char=start,
                end_char=end,
                paragraphs=tuple(paragraphs),
                metadata=dict(section.metadata) if section is not None else {},
                synthetic=synthetic,
            )
            section_nodes.append(node)
            if not synthetic:
                hierarchy_stack.append(node)

        return DocumentTree(
            document_id=document.document.document_id,
            sections=tuple(section_nodes),
        )

    @staticmethod
    def _valid_sections(
        text: str,
        sections: list[DocumentSection],
    ) -> list[DocumentSection]:
        return sorted(
            (
                section
                for section in sections
                if section.start_char < section.end_char
                and section.start_char < len(text)
                and section.end_char > 0
            ),
            key=lambda section: (section.start_char, section.end_char),
        )

    @staticmethod
    def _regions(
        text: str,
        sections: list[DocumentSection],
    ) -> list[tuple[int, int, DocumentSection | None]]:
        if not sections:
            return [(0, len(text), None)]

        regions: list[tuple[int, int, DocumentSection | None]] = []
        cursor = 0
        for section in sections:
            start = max(cursor, section.start_char, 0)
            end = min(max(start, section.end_char), len(text))
            if cursor < start:
                regions.append((cursor, start, None))
            if start < end:
                regions.append((start, end, section))
                cursor = end
        if cursor < len(text):
            regions.append((cursor, len(text), None))
        return regions

    @staticmethod
    def _paragraph_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        cursor = start
        index = start
        while index < end:
            if text[index] == "\n":
                boundary_start = index
                probe = index
                newline_count = 0
                while probe < end:
                    if text[probe] == "\n":
                        newline_count += 1
                        probe += 1
                        continue
                    if text[probe] in " \t\r":
                        probe += 1
                        continue
                    break
                if newline_count >= 2:
                    left, right = DocumentTreeBuilder._trim_span(text, cursor, boundary_start)
                    if left < right:
                        spans.append((left, right))
                    cursor = probe
                    index = probe
                    continue
            index += 1

        left, right = DocumentTreeBuilder._trim_span(text, cursor, end)
        if left < right:
            spans.append((left, right))
        return spans

    @staticmethod
    def _page_range(
        start: int,
        end: int,
        pages: list[DocumentPage],
    ) -> tuple[int | None, int | None]:
        intersecting = sorted(
            (page for page in pages if start < page.end_char and end > page.start_char),
            key=lambda page: page.page_number,
        )
        if not intersecting:
            return None, None
        return intersecting[0].page_number, intersecting[-1].page_number

    @staticmethod
    def _section_id(
        document_id: str,
        index: int,
        start_char: int,
        heading: str,
    ) -> str:
        digest = sha256(
            f"{document_id}\x1f{index}\x1f{start_char}\x1f{heading}".encode("utf-8")
        ).hexdigest()[:16]
        return f"section_{digest}"

    @staticmethod
    def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end


__all__ = [
    "DocumentParagraphNode",
    "DocumentSectionNode",
    "DocumentTree",
    "DocumentTreeBuilder",
]
