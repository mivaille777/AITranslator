from __future__ import annotations

import re
from dataclasses import dataclass

from backend.rag.models import RetrievalCandidate, RetrievalResult


@dataclass(frozen=True, slots=True)
class StructuralRetrievalIntent:
    name: str
    section_aliases: tuple[str, ...]
    search_terms: tuple[str, ...]
    final_top_k: int = 8


_INTENTS: tuple[tuple[StructuralRetrievalIntent, tuple[re.Pattern[str], ...]], ...] = (
    (
        StructuralRetrievalIntent(
            name="bibliography",
            section_aliases=(
                "references",
                "bibliography",
                "works cited",
                "reference list",
            ),
            search_terms=("References", "Bibliography", "Works Cited", "reference list"),
            final_top_k=12,
        ),
        (
            re.compile(r"\breferences?\b", re.IGNORECASE),
            re.compile(r"\bbibliograph(?:y|ies)\b", re.IGNORECASE),
            re.compile(r"\bworks cited\b", re.IGNORECASE),
            re.compile(r"\bcited (?:papers?|works?|literature)\b", re.IGNORECASE),
            re.compile(r"参考文献|引用文献|文献列表|引用了哪些|用了哪些文献|参考了哪些文献"),
        ),
    ),
    (
        StructuralRetrievalIntent(
            name="conclusion",
            section_aliases=(
                "conclusion",
                "conclusions",
                "concluding remarks",
                "discussion and conclusions",
                "conclusion and future work",
            ),
            search_terms=("Conclusion", "Conclusions", "concluding remarks", "final findings"),
            final_top_k=10,
        ),
        (
            re.compile(r"\bconclusions?\b", re.IGNORECASE),
            re.compile(r"\bconcluding remarks?\b", re.IGNORECASE),
            re.compile(r"\bfinal (?:finding|findings|conclusion|conclusions)\b", re.IGNORECASE),
            re.compile(r"结论|最终结论|最后的观点|最后观点|最终观点|主要结论"),
        ),
    ),
    (
        StructuralRetrievalIntent(
            name="limitations",
            section_aliases=("limitations", "limitation", "limitations and future work"),
            search_terms=("Limitations", "limitation", "study limitations"),
            final_top_k=8,
        ),
        (
            re.compile(r"\blimitations?\b", re.IGNORECASE),
            re.compile(r"局限|局限性|不足之处|研究不足"),
        ),
    ),
    (
        StructuralRetrievalIntent(
            name="future_work",
            section_aliases=(
                "future work",
                "future research",
                "outlook",
                "conclusion and future work",
                "limitations and future work",
            ),
            search_terms=("Future Work", "future research", "outlook"),
            final_top_k=8,
        ),
        (
            re.compile(r"\bfuture (?:work|research|directions?)\b", re.IGNORECASE),
            re.compile(r"未来工作|未来研究|研究展望|未来方向|展望"),
        ),
    ),
    (
        StructuralRetrievalIntent(
            name="discussion",
            section_aliases=("discussion", "discussion and conclusions"),
            search_terms=("Discussion", "discussion section"),
            final_top_k=8,
        ),
        (
            re.compile(r"\bdiscussion\b", re.IGNORECASE),
            re.compile(r"讨论部分|讨论章节|讨论了什么"),
        ),
    ),
    (
        StructuralRetrievalIntent(
            name="table",
            section_aliases=("table", "tables"),
            search_terms=("Table", "Tables", "tabulated results"),
            final_top_k=10,
        ),
        (
            re.compile(r"\btable\s*\d*\b", re.IGNORECASE),
            re.compile(r"表格|表\s*\d+"),
        ),
    ),
    (
        StructuralRetrievalIntent(
            name="figure",
            section_aliases=("figure", "figures", "fig"),
            search_terms=("Figure", "Fig.", "Figures"),
            final_top_k=10,
        ),
        (
            re.compile(r"\bfig(?:ure)?\.?\s*\d+\b", re.IGNORECASE),
            re.compile(r"图\s*\d+|图表"),
        ),
    ),
)

_HEADING_PREFIX = re.compile(
    r"^\s*(?:(?:\d+(?:\.\d+)*)|(?:[ivxlcdm]+)|(?:[a-z]))[\s.():\-]+",
    re.IGNORECASE,
)
_NON_WORD = re.compile(r"[^a-z0-9\u4e00-\u9fff]+", re.IGNORECASE)


def normalize_section_heading(value: str) -> str:
    normalized = _HEADING_PREFIX.sub("", str(value or "").strip().casefold())
    return _NON_WORD.sub(" ", normalized).strip()


def detect_structural_intent(query: str) -> StructuralRetrievalIntent | None:
    text = str(query or "").strip()
    if not text:
        return None
    for intent, patterns in _INTENTS:
        if any(pattern.search(text) for pattern in patterns):
            return intent
    return None


def build_structural_queries(
    base_queries: tuple[str, ...] | list[str],
    *,
    original_query: str,
    intent: StructuralRetrievalIntent | None,
    max_queries: int = 3,
) -> tuple[str, ...]:
    if max_queries <= 0:
        return ()
    normalized_base = [str(item or "").strip() for item in base_queries if str(item or "").strip()]
    if intent is None:
        return tuple(dict.fromkeys(normalized_base))[:max_queries]

    primary = normalized_base[0] if normalized_base else str(original_query or "").strip()
    structural_terms = " ".join(intent.search_terms)
    candidates = [
        f"{primary} {structural_terms}".strip(),
        structural_terms,
        primary,
        *normalized_base[1:],
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.casefold()
        if candidate and key not in seen:
            unique.append(candidate)
            seen.add(key)
        if len(unique) >= max_queries:
            break
    return tuple(unique)


def section_match_priority(
    candidate: RetrievalCandidate,
    section_aliases: tuple[str, ...],
) -> int:
    if not section_aliases:
        return 0
    aliases = tuple(normalize_section_heading(item) for item in section_aliases)
    heading = normalize_section_heading(candidate.chunk.section_heading)
    if heading:
        if heading in aliases:
            return 3
        if any(alias and (heading.startswith(alias) or alias in heading) for alias in aliases):
            return 2

    prefix = normalize_section_heading(candidate.chunk.text[:180])
    if any(alias and prefix.startswith(alias) for alias in aliases):
        return 1
    return 0


def promote_structural_candidates(
    result: RetrievalResult,
    *,
    intent: StructuralRetrievalIntent | None,
    limit: int,
) -> RetrievalResult:
    if limit <= 0:
        raise ValueError("structural result limit must be positive")
    if intent is None or not result.candidates:
        return result.model_copy(update={"candidates": result.candidates[:limit]})

    indexed = list(enumerate(result.candidates))
    matching = [
        (index, candidate, section_match_priority(candidate, intent.section_aliases))
        for index, candidate in indexed
    ]
    matching_count = sum(priority > 0 for _, _, priority in matching)
    ordered = sorted(
        matching,
        key=lambda item: (
            -item[2],
            item[1].chunk.document_id,
            item[1].chunk.page_number if item[1].chunk.page_number is not None else 10**9,
            item[1].chunk.chunk_index,
            item[0],
        )
        if item[2] > 0
        else (1, "", 10**9, 10**9, item[0]),
    )
    candidates = [
        candidate.model_copy(update={"rank": rank})
        for rank, (_index, candidate, _priority) in enumerate(ordered[:limit], start=1)
    ]
    metadata = dict(result.metadata)
    metadata.update(
        {
            "structural_intent": intent.name,
            "structural_section_hints": list(intent.section_aliases),
            "structural_match_count": matching_count,
        }
    )
    return result.model_copy(update={"candidates": candidates, "metadata": metadata})


__all__ = [
    "StructuralRetrievalIntent",
    "build_structural_queries",
    "detect_structural_intent",
    "normalize_section_heading",
    "promote_structural_candidates",
    "section_match_priority",
]
