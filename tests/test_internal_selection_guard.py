from app.models.selection import ReadingSelection
from backend.services.reading_selection_resolver import ReadingSelectionResolver


class MutableForeground:
    def __init__(self, process_name: str) -> None:
        self.process_name = process_name

    def snapshot(self):
        return 1, self.process_name


class EmptyBrowserContext:
    def latest_reading_selection(self, **_):
        return None


class StubSelectionManager:
    def __init__(self, selection: ReadingSelection) -> None:
        self.selection = selection
        self.calls = 0

    def get_reading_selection_native(self, **_):
        self.calls += 1
        return self.selection


def test_internal_aitranslator_selection_never_replaces_external_reading_context():
    foreground = MutableForeground("notepad.exe")
    manager = StubSelectionManager(ReadingSelection(text="external paper text", provider="uia"))
    resolver = ReadingSelectionResolver(
        browser_context_service=EmptyBrowserContext(),
        selection_manager=manager,
        foreground_detector=foreground,
    )

    external = resolver.resolve()
    assert external is not None
    assert external.text == "external paper text"
    assert manager.calls == 1

    # Selecting user/AI/translation text inside either Tauri webview must not
    # query UIA and must not create a new reading selection.
    foreground.process_name = "aitrans-desktop.exe"
    internal = resolver.resolve()

    assert internal is not None
    assert internal.selection_id == external.selection_id
    assert internal.text == "external paper text"
    assert manager.calls == 1


def test_internal_selection_without_cache_resolves_to_none():
    foreground = MutableForeground("AITranslator.exe")
    manager = StubSelectionManager(ReadingSelection(text="must never be read", provider="uia"))
    resolver = ReadingSelectionResolver(
        browser_context_service=EmptyBrowserContext(),
        selection_manager=manager,
        foreground_detector=foreground,
    )

    assert resolver.resolve(allow_cached=False) is None
    assert manager.calls == 0
