"""Controller layer for routing mouse selections into the active chat input."""

from __future__ import annotations

from typing import Any

from app.ai.chat_controller import ConversationalAIAppController
from app.ai.chat_selection_overlay import (
    SelectionCaptureConversationalAIOverlayManager,
)
from app.infrastructure.settings import SettingsManager
from app.input.mouse_selection_manager import MOUSE_SELECTION_SOURCE
from app.models.events import TranslationTriggerEvent
from app.selection.errors import SelectionError
from app.translation.errors import TextNormalizationError


CHAT_SELECTION_ERROR_TEXT = "无法读取选中的文本。"
CHAT_SELECTION_INPUT_ERROR_TEXT = "选中的文本为空或超过输入限制。"


class SelectionCaptureConversationalAIAppController(ConversationalAIAppController):
    """Send mouse-selected text to Chat while its input capture is armed."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("overlay_manager") is None:
            resolved_config = kwargs.get("config_manager")
            if resolved_config is None:
                resolved_config = SettingsManager()
                kwargs["config_manager"] = resolved_config
            kwargs["overlay_manager"] = SelectionCaptureConversationalAIOverlayManager(
                config_manager=resolved_config,
            )
        super().__init__(*args, **kwargs)

    def _is_chat_selection_capture_armed(self) -> bool:
        checker = getattr(
            self.overlay_manager,
            "is_chat_selection_capture_armed",
            None,
        )
        if not callable(checker):
            return False
        try:
            return bool(checker())
        except Exception as exc:
            self._log_exception("chat_selection_capture_state_failed", exc)
            return False

    def _capture_mouse_selection_into_chat(self) -> bool:
        if self._is_cursor_over_overlay():
            self.logger.info("chat_selection_capture_ignored overlay_hover")
            return True

        try:
            selected = self.selection_manager.get_selected_text()
        except SelectionError as exc:
            self.logger.info(
                "chat_selection_capture_failed error_type=%s",
                type(exc).__name__,
            )
            self._chat_overlay_call("set_chat_error", CHAT_SELECTION_ERROR_TEXT)
            return True
        except Exception as exc:
            self._log_exception("chat_selection_capture_failed", exc)
            self._chat_overlay_call("set_chat_error", CHAT_SELECTION_ERROR_TEXT)
            return True

        self.logger.info(
            "chat_selection_captured text_length=%s provider=%s",
            len(selected.text),
            selected.provider,
        )
        try:
            prepared = self._prepare_selected_text(selected.text)
        except TextNormalizationError as exc:
            self.logger.info(
                "chat_selection_input_rejected error_type=%s",
                type(exc).__name__,
            )
            self._chat_overlay_call(
                "set_chat_error",
                CHAT_SELECTION_INPUT_ERROR_TEXT,
            )
            return True

        if not str(prepared).strip():
            self._chat_overlay_call(
                "set_chat_error",
                CHAT_SELECTION_INPUT_ERROR_TEXT,
            )
            return True

        inserted = bool(
            self._chat_overlay_call(
                "insert_chat_selection",
                prepared,
            )
        )
        if inserted:
            self.logger.info(
                "chat_selection_inserted text_length=%s",
                len(prepared),
            )
        else:
            self._chat_overlay_call("set_chat_error", CHAT_SELECTION_ERROR_TEXT)
        return True

    def _on_translation_triggered(self, event: TranslationTriggerEvent) -> None:
        if (
            event.source == MOUSE_SELECTION_SOURCE
            and self._is_chat_selection_capture_armed()
        ):
            self.logger.info("CHAT_SELECTION_CAPTURE_TRIGGERED source=%s", event.source)
            self._capture_mouse_selection_into_chat()
            return
        super()._on_translation_triggered(event)


__all__ = [
    "CHAT_SELECTION_ERROR_TEXT",
    "CHAT_SELECTION_INPUT_ERROR_TEXT",
    "SelectionCaptureConversationalAIAppController",
]
