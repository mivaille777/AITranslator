"""Selection provider orchestration."""

from __future__ import annotations

import logging
from typing import Any

from app.infrastructure.config import ConfigManager
from app.models.selection import SelectedText, SelectionContext
from app.selection.base import SelectionProvider
from app.selection.browser_pdf_provider import BrowserPdfSelectionProvider
from app.selection.clipboard_provider import ClipboardSelectionProvider
from app.selection.errors import SelectionError
from app.selection.uia_provider import (
    DEFAULT_UIA_TIMEOUT_SECONDS,
    UIASelectionProvider,
)
from app.selection.word_provider import WordSelectionProvider

LOGGER_NAME = "desktop_translator"


class SelectionManager:
    """Route selection capture across native and compatibility providers.

    ``get_selected_text()`` retains the existing full fallback chain for
    explicit/hotkey translation. ``get_selected_text_native()`` is the safe
    automatic-mouse path: it uses only providers that read the target
    application's selection directly and can therefore guarantee that no
    synthetic Ctrl+C is emitted.
    """

    def __init__(
        self,
        provider: SelectionProvider | None = None,
        *,
        word_provider: SelectionProvider | None = None,
        browser_pdf_provider: SelectionProvider | None = None,
        uia_provider: SelectionProvider | None = None,
        clipboard_provider: SelectionProvider | None = None,
        config_manager: ConfigManager | Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._provider_override = provider
        if provider is not None:
            self.native_providers: tuple[SelectionProvider, ...] = (provider,)
            self.automatic_native_providers: tuple[SelectionProvider, ...] = (provider,)
            self.clipboard_provider: SelectionProvider | None = None
            self.providers: tuple[SelectionProvider, ...] = (provider,)
        else:
            resolved_config = config_manager or ConfigManager()
            uia_timeout_seconds = getattr(
                resolved_config,
                "selection_uia_timeout_seconds",
                DEFAULT_UIA_TIMEOUT_SECONDS,
            )
            resolved_word = (
                word_provider if word_provider is not None else WordSelectionProvider()
            )
            resolved_uia = (
                uia_provider
                if uia_provider is not None
                else UIASelectionProvider(timeout_seconds=uia_timeout_seconds)
            )
            resolved_clipboard = (
                clipboard_provider
                if clipboard_provider is not None
                else ClipboardSelectionProvider()
            )
            self.native_providers = (resolved_word, resolved_uia)

            # Production gets the dedicated browser/PDF retry tier. Existing
            # tests/integrations that explicitly inject their own UIA provider
            # retain the historical Word -> injected UIA ordering unless they
            # also explicitly supply a browser_pdf_provider.
            automatic: list[SelectionProvider] = [resolved_word]
            if browser_pdf_provider is not None:
                automatic.append(browser_pdf_provider)
            elif uia_provider is None:
                automatic.append(BrowserPdfSelectionProvider())
            automatic.append(resolved_uia)
            self.automatic_native_providers = tuple(automatic)

            self.clipboard_provider = resolved_clipboard

            # Preserve the explicit legacy compatibility contract.  A caller
            # that injects Word + Clipboard but deliberately omits UIA is
            # defining a two-tier Word -> Clipboard chain.  Do not silently
            # insert a live system UIA provider into that chain: doing so makes
            # deterministic tests/integrations depend on whatever application
            # happens to own the real desktop selection at that instant.
            explicit_word_clipboard_chain = bool(
                word_provider is not None
                and clipboard_provider is not None
                and uia_provider is None
            )
            if explicit_word_clipboard_chain:
                self.providers = (resolved_word, resolved_clipboard)
            else:
                self.providers = (*self.native_providers, resolved_clipboard)

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
        """Return selection using the complete compatibility fallback chain."""

        return self._capture_from(self.providers, context=None, mode="full")

    def get_selected_text_native(
        self,
        *,
        context: SelectionContext | None = None,
    ) -> SelectedText:
        """Return selection without clipboard writes or synthetic keyboard input."""

        return self._capture_from(
            self.automatic_native_providers,
            context=context,
            mode="native",
        )

    def _capture_from(
        self,
        providers: tuple[SelectionProvider, ...],
        *,
        context: SelectionContext | None,
        mode: str,
    ) -> SelectedText:
        if self._busy:
            raise SelectionError("selection already in progress")
        self._busy = True
        try:
            last_error: SelectionError | None = None
            for provider in providers:
                try:
                    contextual_capture = getattr(
                        provider,
                        "get_selected_text_with_context",
                        None,
                    )
                    if context is not None and callable(contextual_capture):
                        selected = contextual_capture(context)
                    else:
                        selected = provider.get_selected_text()

                    if mode == "full":
                        self.logger.info(
                            "selection_provider_used provider=%s",
                            selected.provider,
                        )
                    else:
                        self.logger.info(
                            "selection_provider_used provider=%s mode=%s",
                            selected.provider,
                            mode,
                        )
                    return selected
                except SelectionError as exc:
                    last_error = exc
                    self.logger.debug(
                        "selection_provider_failed provider=%s mode=%s error_type=%s",
                        type(provider).__name__,
                        mode,
                        type(exc).__name__,
                    )
                except Exception as exc:
                    error = SelectionError("selection provider failed")
                    error.__cause__ = exc
                    last_error = error
                    self.logger.debug(
                        "selection_provider_failed provider=%s mode=%s error_type=%s",
                        type(provider).__name__,
                        mode,
                        type(exc).__name__,
                    )

            if last_error is not None:
                self.logger.info("selection_provider_failed_all mode=%s", mode)
                raise last_error
            raise SelectionError("no selection provider is configured")
        finally:
            self._busy = False

    select = get_selected_text


__all__ = ["SelectionManager"]
