"""Tests for deterministic long-text chunking."""

from app.ai.chunking import merge_chunks, split_text


def test_short_text_is_not_split():
    assert split_text("short text", max_chars=256) == ["short text"]


def test_long_paragraph_splits_without_dropping_text():
    source = " ".join([f"word{i}" for i in range(120)])
    chunks = split_text(source, max_chars=256)
    assert len(chunks) > 1
    assert " ".join(" ".join(chunks).split()) == " ".join(source.split())
    assert all(len(chunk) <= 256 for chunk in chunks)


def test_paragraph_text_prefers_paragraph_boundaries():
    source = ("A" * 180) + "\n\n" + ("B" * 180)
    chunks = split_text(source, max_chars=256)
    assert len(chunks) == 2
    assert chunks[0] == "A" * 180
    assert chunks[1] == "B" * 180


def test_merge_chunks_uses_paragraph_spacing():
    assert merge_chunks(["first", " second "]) == "first\n\nsecond"
