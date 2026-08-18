"""Deterministic long-text chunking for AI translation and polishing."""

from __future__ import annotations

import re


DEFAULT_CHUNK_SIZE = 2400
MIN_CHUNK_SIZE = 256

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？.!?；;])\s+")


def _split_oversized_block(block: str, max_chars: int) -> list[str]:
    """Split one paragraph using sentence, whitespace, then hard boundaries."""

    if len(block) <= max_chars:
        return [block]

    sentences = [part for part in _SENTENCE_BOUNDARY_RE.split(block) if part]
    if len(sentences) > 1:
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = sentence if not current else f"{current} {sentence}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            if len(sentence) <= max_chars:
                current = sentence
            else:
                chunks.extend(_split_oversized_block(sentence, max_chars))
                current = ""
        if current:
            chunks.append(current)
        return chunks

    chunks = []
    remaining = block
    while len(remaining) > max_chars:
        split_at = remaining.rfind(" ", 0, max_chars + 1)
        if split_at < max_chars // 2:
            split_at = max_chars
        piece = remaining[:split_at].rstrip()
        if piece:
            chunks.append(piece)
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def split_text(text: object, *, max_chars: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    """Split text into stable chunks while preserving paragraph boundaries."""

    source = "" if text is None else str(text)
    if not source:
        return []
    if isinstance(max_chars, bool) or int(max_chars) < MIN_CHUNK_SIZE:
        raise ValueError(f"max_chars must be an integer >= {MIN_CHUNK_SIZE}")
    max_chars = int(max_chars)
    if len(source) <= max_chars:
        return [source]

    paragraphs = re.split(r"(\n\s*\n)", source)
    chunks: list[str] = []
    current = ""
    for part in paragraphs:
        if not part:
            continue
        if re.fullmatch(r"\n\s*\n", part):
            if current and len(current) + len(part) <= max_chars:
                current += part
            elif current:
                chunks.append(current.rstrip())
                current = ""
            continue

        pieces = _split_oversized_block(part, max_chars)
        for piece in pieces:
            separator = "" if not current or current.endswith("\n\n") else "\n\n"
            candidate = f"{current}{separator}{piece}" if current else piece
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current.rstrip())
                current = piece
    if current:
        chunks.append(current.rstrip())
    return [chunk for chunk in chunks if chunk]


def merge_chunks(chunks: list[str]) -> str:
    """Merge generated chunks with paragraph separation and no metadata."""

    return "\n\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip()).strip()


__all__ = ["DEFAULT_CHUNK_SIZE", "MIN_CHUNK_SIZE", "merge_chunks", "split_text"]
