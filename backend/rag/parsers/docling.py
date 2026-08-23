from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Protocol

from backend.rag.config import RagAdvancedParsingConfig
from backend.rag.exceptions import RagParsingError
from backend.rag.models import NormalizedDocument
from backend.rag.parsers.base import (
    BaseFileParser,
    DocumentParser,
    ParsedBlock,
    compose_blocks,
)


class DoclingBackend(Protocol):
    def convert(self, path: Path, config: RagAdvancedParsingConfig) -> str: ...


class DefaultDoclingBackend:
    """Lazy adapter that keeps Docling outside the normal installation path."""

    def convert(self, path: Path, config: RagAdvancedParsingConfig) -> str:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:
            raise RagParsingError(
                "Docling is not installed; install the 'rag-advanced' optional "
                "dependency to enable advanced parsing"
            ) from exc

        try:
            pipeline_options = PdfPipelineOptions(
                do_table_structure=config.table_enabled,
                do_ocr=config.ocr_enabled,
                do_formula_enrichment=config.formula_enabled,
                document_timeout=config.document_timeout_seconds,
            )
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options,
                    )
                }
            )
            document = converter.convert(path).document
            if config.layout_enabled:
                return str(document.export_to_markdown())
            return str(document.export_to_text())
        except Exception as exc:
            raise RagParsingError(f"Docling failed to parse document: {path}") from exc


def _markdown_blocks(text: str, *, layout_enabled: bool) -> list[ParsedBlock]:
    if not layout_enabled:
        return [ParsedBlock(text=text)]
    blocks: list[ParsedBlock] = []
    for raw_block in re.split(r"\n\s*\n", text):
        block = raw_block.strip()
        if not block:
            continue
        heading = re.fullmatch(r"(#{1,6})\s+(.+)", block)
        if heading:
            blocks.append(
                ParsedBlock(
                    text=heading.group(2).strip(),
                    heading_level=len(heading.group(1)),
                )
            )
        else:
            blocks.append(ParsedBlock(text=block))
    return blocks


class DoclingDocumentParser(BaseFileParser):
    name = "docling"
    version = "docling-v1"
    supported_suffixes = frozenset({".pdf"})

    def __init__(
        self,
        config: RagAdvancedParsingConfig | None = None,
        *,
        backend: DoclingBackend | None = None,
    ) -> None:
        self.config = config or RagAdvancedParsingConfig(enabled=True)
        self._backend = backend or DefaultDoclingBackend()

    def parse(self, source: str | Path) -> NormalizedDocument:
        path = self._resolve_source(source)
        raw_bytes = self._read_bytes(path)
        try:
            converted = self._backend.convert(path, self.config)
        except RagParsingError:
            raise
        except Exception as exc:
            raise RagParsingError(f"Docling failed to parse document: {path}") from exc
        normalized = self._normalize_text(converted)
        if not normalized:
            raise RagParsingError(f"Docling produced no extractable text: {path}")

        text, sections = compose_blocks(
            _markdown_blocks(normalized, layout_enabled=self.config.layout_enabled)
        )
        title = sections[0].heading if sections else path.stem
        try:
            library_version = version("docling")
        except PackageNotFoundError:
            library_version = "injected-backend"
        document = self._build_document(
            path=path,
            raw_bytes=raw_bytes,
            title=title,
            source_kind="pdf",
            mime_type="application/pdf",
            metadata={"advanced_parser": True},
        )
        return NormalizedDocument(
            document=document,
            text=text,
            sections=sections,
            metadata={
                "parser_name": self.name,
                "parser_version": self.version,
                "library_version": library_version,
                "layout_enabled": self.config.layout_enabled,
                "table_enabled": self.config.table_enabled,
                "ocr_enabled": self.config.ocr_enabled,
                "formula_enabled": self.config.formula_enabled,
            },
        )


class AdvancedParserWithFallback:
    name = "advanced_with_basic_fallback"
    version = "1"

    def __init__(self, primary: DocumentParser, fallback: DocumentParser) -> None:
        self.primary = primary
        self.fallback = fallback
        self.supported_suffixes = primary.supported_suffixes.intersection(
            fallback.supported_suffixes
        )

    def supports(self, source: str | Path) -> bool:
        return self.primary.supports(source) and self.fallback.supports(source)

    def parse(self, source: str | Path) -> NormalizedDocument:
        try:
            return self.primary.parse(source)
        except RagParsingError as exc:
            result = self.fallback.parse(source)
            return result.model_copy(
                update={
                    "metadata": {
                        **result.metadata,
                        "advanced_parser_enabled": True,
                        "advanced_parser_fallback": True,
                        "advanced_parser_name": self.primary.name,
                        "advanced_parser_error": str(exc)[:300],
                    }
                }
            )


__all__ = [
    "AdvancedParserWithFallback",
    "DefaultDoclingBackend",
    "DoclingBackend",
    "DoclingDocumentParser",
]
