from __future__ import annotations

from app.agent.workspace import (
    CONFIRMATION_RETRY_TEXT,
    OPEN_TRANSLATION_COMMAND,
    RETURN_TO_CHAT_COMMAND,
    TRANSLATION_CANCELLED_TEXT,
    TRANSLATION_CONFIRMATION_TEXT,
    TRANSLATION_ENTERED_TEXT,
    TRANSLATION_FINISHED_TEXT,
    WorkspaceAgentCoordinator,
)


def test_translation_request_requires_human_confirmation_before_ui_command() -> None:
    coordinator = WorkspaceAgentCoordinator()

    proposed = coordinator.handle_message(
        "session-a",
        "我要你帮我翻译东西",
        workspace="chat",
    )

    assert proposed.handled is True
    assert proposed.pending_confirmation is True
    assert proposed.assistant_message == TRANSLATION_CONFIRMATION_TEXT
    assert proposed.ui_command == ""

    approved = coordinator.handle_message(
        "session-a",
        "确定",
        workspace="chat",
    )

    assert approved.handled is True
    assert approved.pending_confirmation is False
    assert approved.assistant_message == TRANSLATION_ENTERED_TEXT
    assert approved.ui_command == OPEN_TRANSLATION_COMMAND


def test_confirmation_reject_and_unrecognized_reply_do_not_switch_workspace() -> None:
    coordinator = WorkspaceAgentCoordinator()
    coordinator.handle_message("session-b", "帮我翻译一下", workspace="chat")

    retry = coordinator.handle_message("session-b", "我再想想", workspace="chat")
    assert retry.handled is True
    assert retry.pending_confirmation is True
    assert retry.assistant_message == CONFIRMATION_RETRY_TEXT
    assert retry.ui_command == ""

    rejected = coordinator.handle_message("session-b", "取消", workspace="chat")
    assert rejected.handled is True
    assert rejected.pending_confirmation is False
    assert rejected.assistant_message == TRANSLATION_CANCELLED_TEXT
    assert rejected.ui_command == ""


def test_translation_workspace_keeps_normal_chat_and_recognizes_finish_intent() -> None:
    coordinator = WorkspaceAgentCoordinator()
    coordinator.handle_message("session-c", "我要翻译东西", workspace="chat")
    coordinator.handle_message("session-c", "好的", workspace="chat")

    normal = coordinator.handle_message(
        "session-c",
        "这句话有没有更自然的表达？",
        workspace="translation",
    )
    assert normal.handled is False
    assert normal.ui_command == ""

    finished = coordinator.handle_message(
        "session-c",
        "翻译完了",
        workspace="translation",
    )
    assert finished.handled is True
    assert finished.assistant_message == TRANSLATION_FINISHED_TEXT
    assert finished.ui_command == RETURN_TO_CHAT_COMMAND
