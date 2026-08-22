from app.models.selection import DocumentIdentity, ReadingSelection
from backend.agent_core.context import ReadingContextProvider
from backend.agent_core.state import AgentState


class FakeResolver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def resolve_for_text(self, source_text: str):
        self.calls.append(source_text)
        assert source_text == "Gaussian Process"
        return ReadingSelection(
            text="Gaussian Process",
            provider="browser_dom",
            document=DocumentIdentity(
                source_kind="browser",
                resource_url="https://example.test/paper",
                resource_title="Control Paper",
            ),
            section_heading="Method",
            context_before="Bayesian optimization models the objective with a",
            context_after="and optimizes an acquisition function.",
        )


def test_reading_context_provider_reuses_existing_selection_pipeline():
    resolver = FakeResolver()
    provider = ReadingContextProvider(resolver)
    state = AgentState(
        selected_text="Gaussian Process",
        browser_context={"target_language": "zh-CN"},
    )

    context = provider(state)

    assert resolver.calls == ["Gaussian Process"]
    assert context["source_text"] == "Gaussian Process"
    assert context["resource_url"] == "https://example.test/paper"
    assert context["resource_title"] == "Control Paper"
    assert context["section_heading"] == "Method"
    assert context["source_kind"] == "browser"
    assert context["target_language"] == "zh-CN"


def test_reading_context_provider_preserves_explicit_api_context_without_native_lookup():
    resolver = FakeResolver()
    provider = ReadingContextProvider(resolver)
    state = AgentState(
        selected_text="Gaussian Process",
        browser_context={
            "resource_url": "file:///frozen-paper.pdf",
            "resource_title": "Frozen Paper",
            "section_heading": "Results",
            "context_before": "Explicit before",
            "context_after": "Explicit after",
            "source_kind": "pdf_uia",
            "target_language": "zh-CN",
        },
    )

    context = provider(state)

    assert resolver.calls == []
    assert context["source_text"] == "Gaussian Process"
    assert context["resource_url"] == "file:///frozen-paper.pdf"
    assert context["resource_title"] == "Frozen Paper"
    assert context["section_heading"] == "Results"
    assert context["source_kind"] == "pdf_uia"
