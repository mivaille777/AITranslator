from types import SimpleNamespace

from backend.services.agent_tool_registry import AgentToolRegistry


class StubCascade:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def translate(self, source_text: str, **kwargs):
        self.calls.append({"source_text": source_text, **kwargs})
        return SimpleNamespace(
            translated_text="级联译文",
            provider="ai",
            model="deepseek-v4-flash",
            source_language=kwargs["source_language"],
            target_language=kwargs["target_language"],
            request_id=kwargs["request_id"],
            fallback_level=2,
            notice="有道和 Google 翻译当前不可用，已使用 AI 翻译。",
            attempts=(
                SimpleNamespace(provider="youdao_web", status="unavailable"),
                SimpleNamespace(provider="google_web", status="unavailable"),
                SimpleNamespace(provider="ai", status="success"),
            ),
        )


class StubQuickAction:
    def run(self, **_):
        raise AssertionError("quick action should not run")


class StubResearch:
    def save(self, **_):
        raise AssertionError("research write should not run")


def test_translate_selection_uses_shared_cascade_metadata():
    cascade = StubCascade()
    registry = AgentToolRegistry(
        translation_fallback_service=cascade,
        quick_action_service=StubQuickAction(),
        research_note_service=StubResearch(),
    )

    result = registry.execute(
        "translate_selection",
        source_text="Gaussian process",
        source_language="en",
        target_language="zh-CN",
        request_id=17,
    )

    assert result.output_text == "级联译文"
    assert result.provider == "ai"
    assert result.model == "deepseek-v4-flash"
    assert result.request_id == 17
    assert result.data is not None
    assert result.data["fallback_level"] == 2
    assert "有道和 Google 翻译当前不可用" in result.data["notice"]
    assert result.data["attempts"] == [
        {"provider": "youdao_web", "status": "unavailable"},
        {"provider": "google_web", "status": "unavailable"},
        {"provider": "ai", "status": "success"},
    ]
    assert cascade.calls[0]["source_text"] == "Gaussian process"
