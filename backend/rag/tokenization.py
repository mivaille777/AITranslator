from __future__ import annotations

import re
from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenCounter(Protocol):
    """Count tokens without coupling chunking to a model tokenizer."""

    def count(self, text: str) -> int: ...


class HeuristicTokenCounter:
    """Deterministic, offline token estimate for mixed English and CJK text."""

    _TOKEN_PATTERN = re.compile(
        r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"
        r"|[A-Za-z0-9]+(?:[_'’-][A-Za-z0-9]+)*"
        r"|[^\s]",
        re.UNICODE,
    )

    def count(self, text: str) -> int:
        if not text:
            return 0
        return sum(1 for _ in self._TOKEN_PATTERN.finditer(text))


__all__ = ["HeuristicTokenCounter", "TokenCounter"]
