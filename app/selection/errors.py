"""Selection-layer error types."""

from __future__ import annotations


class SelectionError(RuntimeError):
    """A recoverable failure while reading the user's selected text."""
