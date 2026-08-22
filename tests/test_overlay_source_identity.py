from backend.services.overlay_state_service import OverlayStateService


def test_overlay_keeps_application_identity_across_translation_presentation():
    service = OverlayStateService()
    assistant = service.show_assistant(
        context_id="selection-source",
        source_text="Selected browser text",
        source_language="auto",
        target_language="zh-CN",
        application="chrome.exe",
        resource_url="https://chatgpt.com/c/example",
        resource_title="AITrans - Agent架构设计",
        source_kind="browser",
    )

    assert assistant.application == "chrome.exe"
    assert assistant.resource_title == "AITrans - Agent架构设计"

    translation = service.show_translation(
        context_id="selection-source",
        source_text="Selected browser text",
        translated_text="选中的浏览器文本",
        source_language="en",
        target_language="zh-CN",
        provider="youdao_web",
        application="",
    )

    assert translation.application == "chrome.exe"
    assert translation.resource_url == "https://chatgpt.com/c/example"
    assert translation.resource_title == "AITrans - Agent架构设计"


def test_new_selection_replaces_source_application_without_resetting_conversation():
    service = OverlayStateService()
    service.show_assistant(
        context_id="selection-browser",
        source_text="browser text",
        source_language="auto",
        target_language="zh-CN",
        application="chrome.exe",
        source_kind="browser",
    )
    service.bind_companion_conversation(
        context_id="selection-browser",
        conversation_id="conversation-1",
    )

    word = service.show_assistant(
        context_id="selection-word",
        source_text="word text",
        source_language="auto",
        target_language="zh-CN",
        application="WINWORD.EXE",
        resource_title="paper.docx",
        source_kind="word",
    )

    assert word.application == "WINWORD.EXE"
    assert word.source_kind == "word"
    assert word.companion_conversation_id == "conversation-1"
