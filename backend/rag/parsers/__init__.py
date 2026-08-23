from __future__ import annotations

from pathlib import Path

from backend.rag.exceptions import UnsupportedDocumentTypeError
from backend.rag.models import NormalizedDocument
from backend.rag.parsers.base import DocumentParser
from backend.rag.parsers.docx import DocxDocumentParser
from backend.rag.parsers.html import HtmlDocumentParser
from backend.rag.parsers.pdf import PdfDocumentParser
from backend.rag.parsers.text import TextDocumentParser

_DEFAULT_PARSERS: tuple[DocumentParser, ...] = (
    PdfDocumentParser(),
    DocxDocumentParser(),
    HtmlDocumentParser(),
    TextDocumentParser(),
)


def get_parser_for_path(source: str | Path) -> DocumentParser:
    for parser in _DEFAULT_PARSERS:
        if parser.supports(source):
            return parser
    suffix = Path(source).suffix.lower() or "<none>"
    raise UnsupportedDocumentTypeError(f"unsupported document type: {suffix}")


def parse_document(source: str | Path) -> NormalizedDocument:
    return get_parser_for_path(source).parse(source)


__all__ = [
    "DocumentParser",
    "DocxDocumentParser",
    "HtmlDocumentParser",
    "PdfDocumentParser",
    "TextDocumentParser",
    "get_parser_for_path",
    "parse_document",
]
