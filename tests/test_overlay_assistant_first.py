from backend.services.overlay_state_service import OverlayStateService


def test_new_selection_opens_assistant_and_clears_stale_translation():
    service = OverlayStateService()
    service.show_assistant(
        context_id="selection-a",
        source_text="first external selection",
        source_language="auto",
        target_language="zh-CN",
    )
    service.show_translation(
        context_id="selection-a",
        source_text="first external selection",
        translated_text="第一段",
        source_language="en",
        target_language="zh-CN",
        provider="youdao_web",
    )

    state = service.show_assistant(
        context_id="selection-b",
        source_text="second external selection",
        source_language="auto",
        target_language="zh-CN",
    )

    assert state.visible is True
    assert state.mode == "assistant"
    assert state.phase == "ready"
    assert state.context_id == "selection-b"
    assert state.source_text == "second external selection"
    assert state.translated_text == ""
    assert state.provider == ""
    assert state.translation_notice == ""
    assert state.companion_conversation_id == ""


def test_translation_mode_preserves_companion_binding_for_same_context():
    service = OverlayStateService()
    service.show_assistant(
        context_id="selection-a",
        source_text="paper text",
        source_language="en",
        target_language="zh-CN",
    )
    service.bind_companion_conversation(
        context_id="selection-a",
        conversation_id="conversation-1",
    )

    state = service.show_translation(
        context_id="selection-a",
        source_text="paper text",
        translated_text="论文文本",
        source_language="en",
        target_language="zh-CN",
        provider="ai/deepseek-v4-flash",
        translation_notice="Youdao and Google translation are unavailable; AI translation was used.",
    )

    assert state.mode == "translation"
    assert state.phase == "ready"
    assert state.companion_conversation_id == "conversation-1"
    assert "Youdao and Google" in state.translation_notice
