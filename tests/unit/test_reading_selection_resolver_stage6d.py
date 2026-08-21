from __future__ import annotations

from types import SimpleNamespace

from app.models.selection import DocumentIdentity, ReadingSelection
from app.selection.errors import SelectionError
from backend.services.companion_chat_service import CompanionChatService
from backend.services.companion_handoff_service import CompanionHandoffService
from backend.services.reading_selection_resolver import ReadingSelectionResolver
from backend.services.research_note_service import ResearchNoteService


class _Clock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _Detector:
    def __init__(self, process_name: str) -> None:
        self.process_name = process_name

    def snapshot(self) -> tuple[int, str]:
        return 77, self.process_name


class _BrowserContext:
    def __init__(self, selection: ReadingSelection | None) -> None:
        self.selection = selection
        self.calls = 0
        self.max_age_seconds: list[float] = []

    def latest_reading_selection(
        self,
        *,
        max_age_seconds: float,
        process_name: str,
    ) -> ReadingSelection | None:
        _ = process_name
        self.calls += 1
        self.max_age_seconds.append(max_age_seconds)
        return self.selection


class _NativeManager:
    def __init__(self, selection: ReadingSelection | None) -> None:
        self.selection = selection
        self.calls = []

    def get_reading_selection_native(self, *, context):
        self.calls.append(context)
        if self.selection is None:
            raise SelectionError("native selection unavailable")
        return self.selection


class _StaticReadingResolver:
    def __init__(self, selection: ReadingSelection) -> None:
        self.selection = selection

    def resolve_for_text(self, source_text: str = "") -> ReadingSelection | None:
        expected = str(source_text or "").strip()
        if expected and expected != self.selection.text.strip():
            return None
        return self.selection


class _Store:
    def __init__(self) -> None:
        self.context = None
        self.kwargs = None
        self.result = SimpleNamespace(note=SimpleNamespace(note_id="note-1"), created=True)

    def save_context(self, context, **kwargs):
        self.context = context
        self.kwargs = kwargs
        return self.result


def _browser_dom_selection(text: str = "DOM evidence") -> ReadingSelection:
    return ReadingSelection(
        text=text,
        provider="browser_dom",
        document=DocumentIdentity(
            source_kind="browser",
            resource_url="https://example.org/paper#method",
            resource_title="Example Paper",
            application="chrome.exe",
        ),
        section_heading="2. Method",
        context_before="Before sentence.",
        context_after="After sentence.",
    )


def _browser_pdf_selection(text: str = "PDF evidence") -> ReadingSelection:
    return ReadingSelection(
        text=text,
        provider="browser_pdf_uia",
        document=DocumentIdentity(
            source_kind="browser",
            application="chrome.exe",
        ),
    )


def _word_selection(text: str = "Selected paragraph") -> ReadingSelection:
    return ReadingSelection(
        text=text,
        provider="word",
        document=DocumentIdentity(
            source_kind="word",
            resource_title="paper.docx",
            resource_path=r"D:\papers\paper.docx",
            application="winword.exe",
            page_number=7,
        ),
    )


def test_browser_dom_wins_before_native_fallback() -> None:
    browser = _BrowserContext(_browser_dom_selection())
    native = _NativeManager(_browser_pdf_selection())
    resolver = ReadingSelectionResolver(
        browser_context_service=browser,
        selection_manager=native,
        foreground_detector=_Detector("chrome.exe"),
        clock=_Clock(),
    )

    resolved = resolver.resolve()

    assert resolved is not None
    assert resolved.selection.provider == "browser_dom"
    assert resolved.selection.document.resource_url == "https://example.org/paper#method"
    assert native.calls == []
    assert browser.max_age_seconds == [2.0]


def test_browser_pdf_uia_takes_over_when_dom_is_missing() -> None:
    browser = _BrowserContext(None)
    native = _NativeManager(_browser_pdf_selection())
    resolver = ReadingSelectionResolver(
        browser_context_service=browser,
        selection_manager=native,
        foreground_detector=_Detector("chrome.exe"),
        clock=_Clock(),
    )

    resolved = resolver.resolve()

    assert resolved is not None
    assert resolved.selection.provider == "browser_pdf_uia"
    assert resolved.selection.document.source_kind == "browser"
    assert len(native.calls) == 1
    assert native.calls[0].process_name == "chrome.exe"


def test_word_capture_skips_browser_dom_and_uses_native_manager() -> None:
    browser = _BrowserContext(_browser_dom_selection())
    native = _NativeManager(_word_selection())
    resolver = ReadingSelectionResolver(
        browser_context_service=browser,
        selection_manager=native,
        foreground_detector=_Detector("WINWORD.EXE"),
        clock=_Clock(),
    )

    resolved = resolver.resolve()

    assert resolved is not None
    assert resolved.selection.provider == "word"
    assert resolved.selection.document.page_number == 7
    assert browser.calls == 0
    assert len(native.calls) == 1


def test_same_text_accessibility_fallback_keeps_richer_dom_context() -> None:
    browser = _BrowserContext(_browser_dom_selection())
    native = _NativeManager(_browser_pdf_selection("DOM evidence"))
    resolver = ReadingSelectionResolver(
        browser_context_service=browser,
        selection_manager=native,
        foreground_detector=_Detector("chrome.exe"),
        clock=_Clock(),
    )

    first = resolver.resolve()
    browser.selection = None
    second = resolver.resolve()

    assert first is not None
    assert second is not None
    assert second.selection_id == first.selection_id
    assert second.selection.provider == "browser_dom"
    assert second.selection.section_heading == "2. Method"


def test_different_pdf_selection_replaces_cached_dom_selection() -> None:
    browser = _BrowserContext(_browser_dom_selection())
    native = _NativeManager(_browser_pdf_selection("New PDF evidence"))
    resolver = ReadingSelectionResolver(
        browser_context_service=browser,
        selection_manager=native,
        foreground_detector=_Detector("chrome.exe"),
        clock=_Clock(),
    )

    first = resolver.resolve()
    browser.selection = None
    second = resolver.resolve()

    assert first is not None
    assert second is not None
    assert second.selection_id != first.selection_id
    assert second.selection.text == "New PDF evidence"
    assert second.selection.provider == "browser_pdf_uia"


def test_cached_native_selection_survives_focus_return_to_aitranslator() -> None:
    clock = _Clock()
    detector = _Detector("WINWORD.EXE")
    native = _NativeManager(_word_selection())
    resolver = ReadingSelectionResolver(
        browser_context_service=_BrowserContext(None),
        selection_manager=native,
        foreground_detector=detector,
        cache_seconds=45.0,
        clock=clock,
    )

    first = resolver.resolve()
    detector.process_name = "AITranslator.exe"
    native.selection = None
    clock.advance(5.0)
    cached = resolver.resolve()
    clock.advance(46.0)
    expired = resolver.resolve()

    assert first is not None
    assert cached is not None
    assert cached.selection_id == first.selection_id
    assert cached.selection.document.resource_title == "paper.docx"
    assert expired is None


def test_resolve_for_text_rejects_metadata_from_another_selection() -> None:
    resolver = ReadingSelectionResolver(
        browser_context_service=_BrowserContext(None),
        selection_manager=_NativeManager(_word_selection()),
        foreground_detector=_Detector("WINWORD.EXE"),
        clock=_Clock(),
    )

    assert resolver.resolve_for_text("different paragraph") is None
    matching = resolver.resolve_for_text("Selected paragraph")
    assert matching is not None
    assert matching.document.resource_title == "paper.docx"


def test_companion_handoff_recovers_matching_native_metadata() -> None:
    service = CompanionHandoffService(
        reading_resolver=_StaticReadingResolver(_word_selection())
    )

    handoff = service.create(source_text="Selected paragraph")

    assert handoff.resource_title == "paper.docx"
    assert handoff.source_kind == "word"
    assert handoff.resource_url == ""
    assert r"D:\papers\paper.docx" not in repr(handoff)


def test_companion_enriches_matching_word_context_without_local_path_leak() -> None:
    service = CompanionChatService(
        reading_resolver=_StaticReadingResolver(_word_selection())
    )

    enriched = service._with_resolved_reading(
        {
            "session_id": "session-1",
            "user_message": "Explain this paragraph",
            "source_text": "Selected paragraph",
            "context_mode": "reading",
        }
    )
    request = service._build_request(**enriched)

    assert request.context.source_text == "Selected paragraph"
    assert request.context.reading.resource_title == "paper.docx"
    assert request.context.reading.source_kind == "word"
    assert request.context.reading.resource_url == ""
    assert r"D:\papers\paper.docx" not in repr(request)


def test_research_note_uses_matching_native_context() -> None:
    store = _Store()
    service = ResearchNoteService(
        store=store,
        reading_resolver=_StaticReadingResolver(_word_selection()),
    )

    result = service.save(
        source_text="Selected paragraph",
        source_kind="browser_selection",
        user_note="Important evidence",
    )

    assert result is store.result
    assert store.context is not None
    assert store.context.source_text == "Selected paragraph"
    assert store.context.reading.resource_title == "paper.docx"
    assert store.context.reading.source_kind == "word"
    assert store.context.reading.resource_url == ""
    assert r"D:\papers\paper.docx" not in repr(store.context)
