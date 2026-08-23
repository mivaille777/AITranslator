from __future__ import annotations


class RagError(RuntimeError):
    """Base exception for RAG-domain failures."""


class RagConfigurationError(RagError):
    """Raised when runtime RAG configuration cannot be used."""


class RagInvariantError(RagError):
    """Raised when a RAG-domain invariant is violated at runtime."""


class RagParsingError(RagError):
    """Raised when a source document cannot be normalized safely."""


class UnsupportedDocumentTypeError(RagParsingError):
    """Raised when no basic ingestion parser supports a document type."""


__all__ = [
    "RagConfigurationError",
    "RagError",
    "RagInvariantError",
    "RagParsingError",
    "UnsupportedDocumentTypeError",
]
