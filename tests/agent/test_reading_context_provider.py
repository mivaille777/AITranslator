from app.models.selection import DocumentIdentity, ReadingSelection
from backend.agent_core.context import ReadingContextProvider
from backend.agent_core.state import AgentState


class FakeResolver:
    def resolve_for_text(self, source_text: str):
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
    provider = ReadingContextProvider(FakeResolver())
    state = AgentState(
        selected_text="Gaussian Process",
        browser_context={"target_language": "zh-CN"},
    )

    context = provider(state)

    assert context["source_text"] == "Gaussian Process"
    assert context["resource_url"] == "https://example.test/paper"
    assert context["resource_title"] == "Control Paper"
    assert context["section_heading"] == "Method"
    assert context["source_kind"] == "browser"
    assert context["target_language"] == "zh-CN"
