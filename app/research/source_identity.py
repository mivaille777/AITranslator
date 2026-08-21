"""Stable, source-neutral identities for research evidence collections."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

SOURCE_FAMILIES = frozenset({"browser", "pdf", "word", "desktop", "other"})
IDENTITY_QUALITIES = frozenset({"locator", "title", "note"})
_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\x00", "").strip().split())


def normalize_source_family(source_kind: object) -> str:
    """Map provider-specific source kinds onto a small durable family set."""

    token = _clean(source_kind).casefold().replace("-", "_").replace(" ", "_")
    if not token:
        return "other"
    if "pdf" in token:
        return "pdf"
    if "word" in token or token in {"doc", "docx", "msword", "word_com"}:
        return "word"
    if (
        "browser" in token
        or "chromium" in token
        or token in {"web", "webpage", "dom", "browser_selection", "browser_page"}
    ):
        return "browser"
    if (
        "uia" in token
        or "desktop" in token
        or "clipboard" in token
        or token in {"windows", "native"}
    ):
        return "desktop"
    return "other"


def canonical_resource_locator(value: object) -> str:
    """Canonicalize a URL/path enough for source grouping without inventing metadata."""

    raw = str(value or "").replace("\x00", "").strip()
    if not raw:
        return ""

    if _WINDOWS_PATH_RE.match(raw):
        return "file:///" + raw.replace("\\", "/").lstrip("/").casefold()

    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw

    scheme = parsed.scheme.casefold()
    if scheme in {"http", "https"}:
        # Fragments identify an in-page location, not a distinct research source.
        return urlunsplit(
            (
                scheme,
                parsed.netloc.casefold(),
                parsed.path or "/",
                parsed.query,
                "",
            )
        )
    if scheme == "file":
        return urlunsplit(
            (
                "file",
                parsed.netloc.casefold(),
                parsed.path.replace("\\", "/").casefold(),
                parsed.query,
                "",
            )
        )
    return raw


@dataclass(frozen=True, slots=True)
class ResearchSourceIdentity:
    source_id: str
    source_family: str
    source_kind: str
    resource_locator: str
    display_title: str
    identity_quality: str


def build_research_source_identity(
    *,
    resource_url: object = "",
    resource_title: object = "",
    source_kind: object = "",
    fallback_key: object = "",
) -> ResearchSourceIdentity:
    """Build the best identity supported by captured metadata.

    Quality is explicit because native PDF/Word providers do not yet always expose
    a stable document locator. Consumers can therefore distinguish a URL/path
    identity from a title-only or note-local fallback instead of assuming more
    precision than the source provider supplied.
    """

    kind = _clean(source_kind)
    family = normalize_source_family(kind)
    locator = canonical_resource_locator(resource_url)
    title = _clean(resource_title)
    fallback = _clean(fallback_key)

    if locator:
        quality = "locator"
        identity_material = f"locator\x1f{family}\x1f{locator}"
    elif title:
        quality = "title"
        identity_material = f"title\x1f{family}\x1f{title.casefold()}"
    else:
        quality = "note"
        identity_material = f"note\x1f{family}\x1f{fallback or 'unknown'}"

    source_id = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()[:20]
    display_title = title or locator or kind or "Unidentified source"
    return ResearchSourceIdentity(
        source_id=source_id,
        source_family=family,
        source_kind=kind,
        resource_locator=locator,
        display_title=display_title,
        identity_quality=quality,
    )


__all__ = [
    "IDENTITY_QUALITIES",
    "SOURCE_FAMILIES",
    "ResearchSourceIdentity",
    "build_research_source_identity",
    "canonical_resource_locator",
    "normalize_source_family",
]
