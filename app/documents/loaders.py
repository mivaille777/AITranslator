from __future__ import annotations

from abc import ABC, abstractmethod

from .models import DocumentSource, DocumentSourceType


class DocumentLoader(ABC):
    """Common boundary for PDF, DOCX, browser and selection ingestion."""

    source_type: DocumentSourceType

    @abstractmethod
    def load(self, source_id: str, title: str, content: str, **metadata) -> DocumentSource:
        raise NotImplementedError


class TextDocumentLoader(DocumentLoader):
    """Initial generic loader used by higher-level source adapters."""

    source_type = DocumentSourceType.SELECTION

    def load(self, source_id: str, title: str, content: str, **metadata) -> DocumentSource:
        return DocumentSource(
            source_id=source_id,
            source_type=self.source_type,
            title=title,
            content=content,
            metadata=metadata,
        )


class BrowserContextLoader(TextDocumentLoader):
    source_type = DocumentSourceType.BROWSER


class SelectionLoader(TextDocumentLoader):
    source_type = DocumentSourceType.SELECTION


class PDFLoader(TextDocumentLoader):
    source_type = DocumentSourceType.PDF


class DocxLoader(TextDocumentLoader):
    source_type = DocumentSourceType.DOCX
