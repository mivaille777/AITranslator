"""Translation-layer error types."""

from __future__ import annotations


class TranslationError(RuntimeError):
    """A provider-independent translation failure."""


class WebTranslationError(TranslationError):
    """The Google web-compatible backend failed safely."""


class TextNormalizationError(TranslationError):
    """The selected text is empty or violates the configured input limit."""
