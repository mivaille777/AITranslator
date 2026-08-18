"""Text normalization and input protection before translation requests."""

from __future__ import annotations

import re

from app.translation.errors import TextNormalizationError

DEFAULT_MAX_TEXT_LENGTH = 5000
_HORIZONTAL_WHITESPACE_RE = re.compile(r"[^\S\r\n]+")


class TextNormalizer:
    """Normalize selected text while preserving punctuation and paragraphs."""

    def __init__(self, max_length: int = DEFAULT_MAX_TEXT_LENGTH) -> None:
        try:
            normalized_limit = int(max_length)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "max text length must be a positive integer"
            ) from exc
        if normalized_limit < 1:
            raise ValueError("max text length must be a positive integer")
        self.max_length = normalized_limit

    def normalize(self, text: object | None) -> str:
        """Return normalized text or raise a clear input protection error.

        Newlines are normalized to ``\n``. Horizontal whitespace within each
        line is collapsed to one ordinary space, while paragraph boundaries
        are retained. Punctuation, Unicode characters, and emoji are not
        rewritten.
        """

        value = "" if text is None else str(text)
        value = value.replace("\r\n", "\n").replace("\r", "\n")

        normalized_lines: list[str] = []
        previous_line_was_blank = False
        for raw_line in value.split("\n"):
            line = _HORIZONTAL_WHITESPACE_RE.sub(" ", raw_line).strip()
            if line:
                normalized_lines.append(line)
                previous_line_was_blank = False
            elif normalized_lines and not previous_line_was_blank:
                # Keep one blank line as a paragraph boundary, but do not
                # forward an arbitrary run of empty lines to the provider.
                normalized_lines.append("")
                previous_line_was_blank = True

        normalized = "\n".join(normalized_lines).strip()
        if not normalized:
            raise TextNormalizationError("source text is empty")
        if len(normalized) > self.max_length:
            raise TextNormalizationError(
                "source text exceeds maximum length "
                f"of {self.max_length} characters"
            )
        return normalized


__all__ = ["DEFAULT_MAX_TEXT_LENGTH", "TextNormalizer"]
