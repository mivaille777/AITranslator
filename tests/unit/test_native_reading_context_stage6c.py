from __future__ import annotations

from types import SimpleNamespace

from app.models.selection import (
    DocumentIdentity,
    ReadingSelection,
    SelectedText,
    SelectionContext,
)
from app.selection.base import SelectionProvider
from app.selection.browser_page_bridge import BrowserReadingBridge
from app.selection.browser_pdf_provider import BrowserPdfSelectionProvider
from app.selection.errors import SelectionError
from app.selection.manager import SelectionManager
from app.selection.word_provider import WordSelectionProvider
from backend.services.browser_context_service import BrowserContextService
from backend.services.reading_context_adapter import to_reading_context


class _PythonCom:
    def __init__(self) -> None:
        self.initialized = 0
        self.uninitialized = 0

    def CoInitialize(self) -> None:  # noqa: N802 - pywin32 compatibility
        self.initialized += 1

    def CoUninitialize(self) -> None:  # noqa: N802 - pywin32 compatibility
        self.uninitialized += 1


class _UnavailableProvider(SelectionProvider):
    def get_selected_text(self) -> SelectedText:
        raise SelectionError("unavailable")


class _StaticProvider(SelectionProvider):
    def __init__(self, selected: SelectedText) -> None:
        self.selected = selected

    def get_selected_text(self) -> SelectedText:
        return self.selected

    def get_selected_text_with_context(
        self,
        _context: SelectionContext | None,
    ) -> SelectedText:
        return self.selected


def test_word_keeps_legacy_selection_and_adds_reliable_document_identity() -> None:
    pythoncom = _PythonCom()
    selection = SimpleNamespace(
        Text="Selected paragraph",
        Information=lambda kind: 7 if kind == 1 else 0,
    )
    document = SimpleNamespace(
        Name="paper.docx",
        FullName=r"D:\papers\paper.docx",
    )
    application = SimpleNamespace(
        Selection=selection,
        ActiveDocument=document,
    )
    provider = WordSelectionProvider(
        foreground_detector=lambda: True,
        com_factory=lambda: application,
        pythoncom_module=pythoncom,
    )

    legacy = provider.get_selected_text()
    reading = provider.get_reading_selection()

    assert legacy == SelectedText(text="Selected paragraph", provider="word")
    assert reading.selected_text == legacy
    assert reading.document == DocumentIdentity(
        source_kind="word",
        resource_title="paper.docx",
        resource_path=r"D:\papers\paper.docx",
        application="winword.exe",
        page_number=7,
    )
    assert pythoncom.initialized == 2
    assert pythoncom.uninitialized == 2


def test_word_omits_unsaved_document_path_and_unreliable_page_number() -> None:
    pythoncom = _PythonCom()
    selection = SimpleNamespace(Text="draft", Information=lambda _kind: 0)
    document = SimpleNamespace(Name="Document1", FullName="Document1")
    application = SimpleNamespace(Selection=selection, ActiveDocument=document)
    provider = WordSelectionProvider(
        foreground_detector=lambda: True,
        com_factory=lambda: application,
        pythoncom_module=pythoncom,
    )

    reading = provider.get_reading_selection()

    assert reading.document.resource_title == "Document1"
    assert reading.document.resource_path == ""
    assert reading.document.page_number is None


def test_browser_pdf_accessibility_capture_does_not_invent_url_or_title() -> None:
    provider = BrowserPdfSelectionProvider(
        uia_provider=_StaticProvider(SelectedText("PDF passage", provider="uia")),
        retry_delays_seconds=(0.0,),
    )
    context = SelectionContext(process_name=r"C:\Program Files\Google\Chrome\chrome.exe")

    reading = provider.get_reading_selection_with_context(context)

    assert reading.text == "PDF passage"
    assert reading.provider == "browser_pdf_uia"
    assert reading.document.source_kind == "browser"
    assert reading.document.application == "chrome.exe"
    assert reading.document.resource_url == ""
    assert reading.document.resource_title == ""


def test_selection_manager_upgrades_generic_uia_to_weak_desktop_identity() -> None:
    manager = SelectionManager(
        word_provider=_UnavailableProvider(),
        uia_provider=_StaticProvider(SelectedText("Native text", provider="uia")),
        clipboard_provider=_StaticProvider(
            SelectedText("Clipboard text", provider="clipboard")
        ),
    )
    context = SelectionContext(process_name=r"C:\Windows\System32\notepad.exe")

    reading = manager.get_reading_selection_native(context=context)

    assert reading.selected_text == SelectedText("Native text", provider="uia")
    assert reading.document.source_kind == "desktop"
    assert reading.document.application == "notepad.exe"
    assert reading.document.resource_url == ""
    assert reading.document.resource_title == ""


def test_browser_dom_snapshot_preserves_real_url_title_heading_and_nearby_text() -> None:
    bridge = BrowserReadingBridge(clock=lambda: 100.0)
    bridge.ingest_payload(
        {
            "version": 1,
            "type": "selection",
            "text": "bounded evidence",
            "url": "https://example.org/paper#section-2",
            "title": "Example Paper",
            "heading": "2. Method",
            "context_before": "Before sentence.",
            "context_after": "After sentence.",
        },
        received_at=100.0,
    )
    service = BrowserContextService(bridge)

    reading = service.latest_reading_selection(
        max_age_seconds=5.0,
        process_name=r"C:\Program Files\Google\Chrome\chrome.exe",
    )
    context = service.latest_reading_context(
        max_age_seconds=5.0,
        process_name=r"C:\Program Files\Google\Chrome\chrome.exe",
    )

    assert reading is not None
    assert reading.document.source_kind == "browser"
    assert reading.document.resource_url == "https://example.org/paper#section-2"
    assert reading.document.resource_title == "Example Paper"
    assert reading.document.application == "chrome.exe"
    assert reading.section_heading == "2. Method"
    assert reading.context_before == "Before sentence."
    assert reading.context_after == "After sentence."

    assert context is not None
    assert context.resource_url == "https://example.org/paper#section-2"
    assert context.resource_title == "Example Paper"
    assert context.section_heading == "2. Method"
    assert context.context_before == "Before sentence."
    assert context.context_after == "After sentence."
    assert context.source_kind == "browser"


def test_prompt_adapter_never_promotes_local_path_to_resource_url() -> None:
    selection = ReadingSelection(
        text="local passage",
        provider="word",
        document=DocumentIdentity(
            source_kind="word",
            resource_title="private.docx",
            resource_path=r"D:\private\private.docx",
            application="winword.exe",
            page_number=12,
        ),
    )

    context = to_reading_context(selection)

    assert context.resource_url == ""
    assert context.resource_title == "private.docx"
    assert context.source_kind == "word"
    assert r"D:\private\private.docx" not in repr(context)
