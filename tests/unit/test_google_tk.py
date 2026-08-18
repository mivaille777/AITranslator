"""Tests for the isolated Google web-compatible ``tk`` generator."""

from __future__ import annotations

import re

import pytest

from app.translation.token.google_tk import generate_token


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello world", "814953.678685"),
        ("Bayesian optimization", "691461.833905"),
        ("贝叶斯优化", "948368.543972"),
        ("PID controller 参数整定", "899235.756951"),
        ("😀", "916699.772271"),
        ("", "557215.963819"),
    ],
)
def test_generate_token_matches_web_algorithm(text: str, expected: str) -> None:
    assert generate_token(text) == expected
    assert re.fullmatch(r"\d+\.\d+", generate_token(text))


def test_generate_token_is_deterministic_and_text_sensitive() -> None:
    assert generate_token("same") == generate_token("same")
    assert generate_token("same") != generate_token("different")


def test_generate_token_handles_unpaired_surrogate_without_silent_failure() -> None:
    token = generate_token("unpaired\ud800")

    assert re.fullmatch(r"\d+\.\d+", token)


def test_generate_token_requires_string_input() -> None:
    with pytest.raises(TypeError, match="text must be a string"):
        generate_token(123)  # type: ignore[arg-type]
