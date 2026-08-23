from __future__ import annotations


class RagError(RuntimeError):
    """Base exception for RAG-domain failures."""


class RagConfigurationError(RagError):
    """Raised when runtime RAG configuration cannot be used."""


class RagInvariantError(RagError):
    """Raised when a RAG-domain invariant is violated at runtime."""


__all__ = ["RagConfigurationError", "RagError", "RagInvariantError"]
