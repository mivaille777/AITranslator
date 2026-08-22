"""Deterministic context budgeting for prompt construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


DEFAULT_CONTEXT_MAX_CHARS = 24_000
DEFAULT_CHARS_PER_TOKEN = 4.0


@dataclass(frozen=True, slots=True)
class ContextField:
    name: str
    value: str
    priority: int
    max_chars: int


@dataclass(frozen=True, slots=True)
class ContextBudgetReport:
    max_chars: int
    used_chars: int
    estimated_tokens: int
    truncated_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContextBudgetResult:
    values: dict[str, str]
    report: ContextBudgetReport


def _clip(value: str, limit: int) -> str:
    text = str(value or "")
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"


class ContextBudgetManager:
    """Allocate a bounded character budget by explicit field priority.

    Character budgeting avoids adding tokenizer/provider dependencies while
    still preventing unbounded prompts. Lower numeric priority is allocated
    first. Each field also has its own hard cap.
    """

    def __init__(
        self,
        *,
        max_chars: int = DEFAULT_CONTEXT_MAX_CHARS,
        chars_per_token: float = DEFAULT_CHARS_PER_TOKEN,
    ) -> None:
        self.max_chars = max(1, int(max_chars))
        self.chars_per_token = max(1.0, float(chars_per_token))

    def allocate(self, fields: Iterable[ContextField]) -> ContextBudgetResult:
        ordered = sorted(enumerate(fields), key=lambda item: (item[1].priority, item[0]))
        remaining = self.max_chars
        values: dict[str, str] = {}
        truncated: list[str] = []

        for _index, field in ordered:
            raw = str(field.value or "")
            field_cap = max(0, int(field.max_chars))
            allowed = min(field_cap, remaining)
            clipped = _clip(raw, allowed)
            values[field.name] = clipped
            if clipped != raw:
                truncated.append(field.name)
            remaining = max(0, remaining - len(clipped))

        used = self.max_chars - remaining
        estimated_tokens = int((used / self.chars_per_token) + 0.999) if used else 0
        return ContextBudgetResult(
            values=values,
            report=ContextBudgetReport(
                max_chars=self.max_chars,
                used_chars=used,
                estimated_tokens=estimated_tokens,
                truncated_fields=tuple(truncated),
            ),
        )


__all__ = [
    "ContextBudgetManager",
    "ContextBudgetReport",
    "ContextBudgetResult",
    "ContextField",
    "DEFAULT_CONTEXT_MAX_CHARS",
]
