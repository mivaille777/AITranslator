"""Unified source-neutral reading selection resolver.

Stage 6C collected rich reading context from several independent capture paths.
This module is the first Stage 6D boundary that gives application services one
stable resolver instead of making them understand Browser DOM, browser/PDF
accessibility, Word COM, or generic UIA individually.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2s
from threading import RLock
from time import monotonic
from typing import Any

from app.models.selection import ReadingSelection, SelectionContext
from app.selection.browser_pdf_provider import BROWSER_PDF_PROCESS_NAMES
from app.selection.errors import SelectionError
from app.selection.foreground import ForegroundApplicationDetector
from app.selection.manager import SelectionManager
from backend.services.browser_context_service import BrowserContextService

DEFAULT_BROWSER_SELECTION_MAX_AGE_SECONDS = 2.0
DEFAULT_READING_SELECTION_CACHE_SECONDS = 45.0
INTERNAL_SELECTION_PROCESS_NAMES = frozenset(
    {
        "aitrans-desktop.exe",
        "aitrans-desktop",
        "aitranslator.exe",
        "aitranslator",
        "desktop_translator.exe",
        "desktop_translator",
    }
)


@dataclass(frozen=True, slots=True)
class ResolvedReadingSelection:
    """One resolved reading selection with a stable UI-facing identity."""

    selection_id: str
    selection: ReadingSelection

    @property
    def text(self) -> str:
        return self.selection.text

    @property
    def provider(self) -> str:
        return self.selection.provider


def _normalized_process_name(value: str | None) -> str:
    return str(value or "").replace("\\", "/").rsplit("/", 1)[-1].casefold()


def _selection_fingerprint(selection: ReadingSelection) -> str:
    document = selection.document
    parts = (
        selection.provider,
        selection.text.strip(),
        document.source_kind,
        document.resource_url,
        document.resource_title,
        document.resource_path,
        document.application,
        str(document.page_number or ""),
        selection.section_heading,
        selection.context_before,
        selection.context_after,
    )
    digest = blake2s("\x1f".join(parts).encode("utf-8"), digest_size=12).hexdigest()
    provider = selection.provider.strip() or "selection"
    return f"{provider}:{digest}"


def _context_richness(selection: ReadingSelection) -> int:
    document = selection.document
    return sum(
        bool(value)
        for value in (
            document.resource_url,
            document.resource_title,
            document.resource_path,
            document.application,
            document.page_number,
            selection.section_heading,
            selection.context_before,
            selection.context_after,
        )
    )


class ReadingSelectionResolver:
    """Resolve the best current reading selection across all capture tiers.

    AITranslator's own main/overlay processes are explicit exclusion zones.
    Selecting user messages, AI output, source text or translated text inside
    the product must never become a new reading selection.
    """

    def __init__(
        self,
        *,
        browser_context_service: BrowserContextService | Any | None = None,
        selection_manager: SelectionManager | Any | None = None,
        foreground_detector: ForegroundApplicationDetector | Any | None = None,
        browser_max_age_seconds: float = DEFAULT_BROWSER_SELECTION_MAX_AGE_SECONDS,
        cache_seconds: float = DEFAULT_READING_SELECTION_CACHE_SECONDS,
        clock: Any = monotonic,
    ) -> None:
        self._browser_context_service = browser_context_service or BrowserContextService()
        self._selection_manager = selection_manager
        self._foreground_detector = foreground_detector or ForegroundApplicationDetector()
        self._browser_max_age_seconds = max(0.0, float(browser_max_age_seconds))
        self._cache_seconds = max(0.0, float(cache_seconds))
        self._clock = clock
        self._lock = RLock()
        self._cached: ResolvedReadingSelection | None = None
        self._cached_at: float | None = None

    def _manager(self) -> SelectionManager | Any:
        with self._lock:
            if self._selection_manager is None:
                self._selection_manager = SelectionManager()
            return self._selection_manager

    def _foreground_context(self) -> SelectionContext:
        try:
            hwnd, process_name = self._foreground_detector.snapshot()
        except Exception:
            hwnd, process_name = None, None
        return SelectionContext(
            foreground_hwnd=hwnd,
            process_name=process_name,
            captured_at=float(self._clock()),
        )

    @staticmethod
    def _is_browser(context: SelectionContext) -> bool:
        return _normalized_process_name(context.process_name) in BROWSER_PDF_PROCESS_NAMES

    @staticmethod
    def _is_internal_surface(context: SelectionContext) -> bool:
        return _normalized_process_name(context.process_name) in INTERNAL_SELECTION_PROCESS_NAMES

    def _remember(self, selection: ReadingSelection) -> ResolvedReadingSelection:
        resolved = ResolvedReadingSelection(
            selection_id=_selection_fingerprint(selection),
            selection=selection,
        )
        with self._lock:
            self._cached = resolved
            self._cached_at = float(self._clock())
        return resolved

    def _cached_if_fresh(self) -> ResolvedReadingSelection | None:
        with self._lock:
            cached = self._cached
            cached_at = self._cached_at
        if cached is None or cached_at is None:
            return None
        if float(self._clock()) - cached_at > self._cache_seconds:
            return None
        return cached

    def _prefer_richer_same_text(
        self,
        selection: ReadingSelection,
    ) -> ResolvedReadingSelection:
        cached = self._cached_if_fresh()
        if (
            cached is not None
            and cached.selection.text.strip() == selection.text.strip()
            and _context_richness(cached.selection) > _context_richness(selection)
        ):
            return cached
        return self._remember(selection)

    def resolve(self, *, allow_cached: bool = True) -> ResolvedReadingSelection | None:
        """Return the best live external selection, or a short-lived cached one."""

        context = self._foreground_context()

        if self._is_internal_surface(context):
            # Internal selections are visual/clipboard interactions only. Never
            # query UIA for AITranslator itself, because that would feed chat or
            # translation output back into the reading pipeline.
            return self._cached_if_fresh() if allow_cached else None

        if self._is_browser(context):
            try:
                browser_selection = self._browser_context_service.latest_reading_selection(
                    max_age_seconds=self._browser_max_age_seconds,
                    process_name=str(context.process_name or ""),
                )
            except Exception:
                browser_selection = None
            if browser_selection is not None and browser_selection.text.strip():
                return self._remember(browser_selection)

        try:
            native_selection = self._manager().get_reading_selection_native(context=context)
        except SelectionError:
            native_selection = None
        except Exception:
            native_selection = None

        if native_selection is not None and native_selection.text.strip():
            return self._prefer_richer_same_text(native_selection)
        if allow_cached:
            return self._cached_if_fresh()
        return None

    def resolve_for_text(self, source_text: str = "") -> ReadingSelection | None:
        """Resolve context only when it safely belongs to the supplied text."""

        resolved = self.resolve()
        if resolved is None:
            return None
        expected = str(source_text or "").strip()
        if expected and resolved.selection.text.strip() != expected:
            return None
        return resolved.selection

    def clear_cache(self) -> None:
        with self._lock:
            self._cached = None
            self._cached_at = None


__all__ = [
    "DEFAULT_BROWSER_SELECTION_MAX_AGE_SECONDS",
    "DEFAULT_READING_SELECTION_CACHE_SECONDS",
    "INTERNAL_SELECTION_PROCESS_NAMES",
    "ReadingSelectionResolver",
    "ResolvedReadingSelection",
]
