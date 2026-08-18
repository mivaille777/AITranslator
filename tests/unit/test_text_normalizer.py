"""Step11 text normalization and input protection tests."""

from __future__ import annotations

import pytest

from app.translation.errors import TextNormalizationError
from app.translation.normalizer import TextNormalizer


def test_normalizer_trims_and_collapses_horizontal_whitespace() -> None:
    normalizer = TextNormalizer()

    assert normalizer.normalize("\t  The   quick\t brown fox  ") == (
        "The quick brown fox"
    )


def test_normalizer_unifies_windows_newlines_and_preserves_paragraphs() -> None:
    normalizer = TextNormalizer()

    assert normalizer.normalize("first\r\n\r\nsecond\rthird") == (
        "first\n\nsecond\nthird"
    )


def test_normalizer_preserves_chinese_punctuation_unicode_and_emoji() -> None:
    text = "  你好，世界！Unicode: café — 🚀  "

    assert TextNormalizer().normalize(text) == "你好，世界！Unicode: café — 🚀"


@pytest.mark.parametrize("text", [None, "", "   \r\n\t  "])
def test_normalizer_rejects_empty_or_whitespace_only_text(text: object) -> None:
    with pytest.raises(TextNormalizationError, match="source text is empty"):
        TextNormalizer().normalize(text)


def test_normalizer_rejects_text_over_configured_limit() -> None:
    with pytest.raises(TextNormalizationError, match="maximum length of 5"):
        TextNormalizer(max_length=5).normalize("123456")


def test_normalizer_does_not_remove_required_punctuation() -> None:
    text = "Don't delete: commas, periods... or C++ symbols!"

    assert TextNormalizer().normalize(text) == text
