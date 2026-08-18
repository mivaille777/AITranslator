"""Selection provider orchestration."""

from __future__ import annotations

import logging
from typing import Any

from app.infrastructure.config import ConfigManager
from app.models.selection import SelectedText
from app.selection.base import SelectionProvider
from app.selection.clipboard_provider import ClipboardSelectionProvider
from app.selection.errors import SelectionError
from app.selection.uia_provider import (
    DEFAULT_UIA_TIMEOUT_SECONDS,
    UIASelectionProvider,
)
from app.selection.word_provider import WordSelectionProvider

LOGGER_NAME = "desktop_translator"


class SelectionManager:
    """Keep application code independent of the active selection provider."""

    def __init__(
        self,
        provider: SelectionProvider | None = None,
        *,
        word_provider: SelectionProvider | None = None,
        uia_provider: SelectionProvider | None = None,
        clipboard_provider: SelectionProvider | None = None,
        config_manager: ConfigManager | Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._provider_override = provider
        if provider is not None:
            self.providers: tuple[SelectionProvider, ...] = (provider,)
        else:
            resolved_config = config_manager or ConfigManager()
            uia_timeout_seconds = getattr(
                resolved_config,
                "selection_uia_timeout_seconds",
                DEFAULT_UIA_TIMEOUT_SECONDS,
            )
            self.providers = (
                word_provider if word_provider is not None else WordSelectionProvider(),
                uia_provider
                if uia_provider is not None
                else UIASelectionProvider(timeout_seconds=uia_timeout_seconds),
                clipboard_provider
                if clipboard_provider is not None
                else ClipboardSelectionProvider(),
            )
        # Preserve the Step5 ``provider`` attribute for callers that supplied
        # one explicitly; for the default chain it identifies the first tier.
        self.provider = self.providers[0]
        self.logger = logger or logging.getLogger(LOGGER_NAME)
        self._busy = False

    @property
    def is_busy(self) -> bool:
        """Whether a selection operation is currently in progress."""

        return self._busy

    def get_selected_text(self) -> SelectedText:
        """Return the current selection from the configured provider."""

        if self._busy:
            raise SelectionError("selection already in progress")
        self._busy = True
        try:
            last_error: SelectionError | None = None
            for provider in self.providers:
                try:
                    selected = provider.get_selected_text()
                    self.logger.info(
                        "selection_provider_used provider=%s",
                        selected.provider,
                    )
                    return selected
                except SelectionError as exc:
                    last_error = exc
                    self.logger.debug(
                        "selection_provider_failed provider=%s error_type=%s",
                        type(provider).__name__,
                        type(exc).__name__,
                    )
                except Exception as exc:
                    error = SelectionError("selection provider failed")
                    error.__cause__ = exc
                    last_error = error
                    self.logger.debug(
                        "selection_provider_failed provider=%s error_type=%s",
                        type(provider).__name__,
                        type(exc).__name__,
                    )

            if last_error is not None:
                self.logger.info("selection_provider_failed_all")
                raise last_error
            raise SelectionError("no selection provider is configured")
        finally:
            self._busy = False

    select = get_selected_text
