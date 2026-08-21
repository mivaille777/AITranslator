"""Selection provider orchestration."""

from __future__ import annotations

import logging
from typing import Any

from app.infrastructure.config import ConfigManager
from app.models.selection import ReadingSelection, SelectedText, SelectionContext
from app.selection.base import SelectionProvider
from app.selection.browser_pdf_provider import BrowserPdfSelectionProvider
from app.selection.clipboard_provider import ClipboardSelectionProvider
from app.selection.errors import SelectionError
from app.selection.reading_context import reading_selection_from_selected_text
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

    Stage 6C adds parallel ``get_reading_selection*`` methods. They preserve the
    exact provider ordering while preferring richer metadata when a provider
    exposes it. Legacy providers are upgraded to weak :class:`ReadingSelection`
    values without changing their original API.
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

            # Preserve the explicit legacy compatibility contract only when
            # the caller has not supplied runtime configuration.  A caller
            # that injects Word + Clipboard with no config is defining a
            # deterministic two-tier Word -> Clipboard chain and should not
            # inherit a live system UIA provider from the developer desktop.
            # Supplying config_manager, however, is an explicit request to use
            # the configured native stack, including the configured UIA
            # timeout, so the default UIA provider must remain in that chain.
            explicit_word_clipboard_chain = bool(
                word_provider is not None
                and clipboard_provider is not None
                and uia_provider is None
                and config_manager is None
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

    def get_reading_selection(self) -> ReadingSelection:
        """Return selected text plus the best reliable document metadata."""

        return self._capture_reading_from(
            self.providers,
            context=None,
            mode="full",
        )

    def get_reading_selection_native(
        self,
        *,
        context: SelectionContext | None = None,
    ) -> ReadingSelection:
        """Return rich native capture without clipboard or keyboard synthesis."""

        return self._capture_reading_from(
            self.automatic_native_providers,
            context=context,
            mode="native",
        )

    @staticmethod
    def _selected_from_provider(
        provider: SelectionProvider,
        context: SelectionContext | None,
    ) -> SelectedText:
        contextual_capture = getattr(
            provider,
            "get_selected_text_with_context",
            None,
        )
        if context is not None and callable(contextual_capture):
            selected = contextual_capture(context)
        else:
            selected = provider.get_selected_text()
        if not isinstance(selected, SelectedText):
            raise SelectionError("selection provider returned unsupported result")
        return selected

    @staticmethod
    def _reading_from_provider(
        provider: SelectionProvider,
        context: SelectionContext | None,
    ) -> ReadingSelection:
        contextual_capture = getattr(
            provider,
            "get_reading_selection_with_context",
            None,
        )
        capture = getattr(provider, "get_reading_selection", None)

        if context is not None and callable(contextual_capture):
            result = contextual_capture(context)
        elif callable(capture):
            result = capture()
        else:
            result = SelectionManager._selected_from_provider(provider, context)

        if isinstance(result, ReadingSelection):
            if not result.text.strip():
                raise SelectionError("reading selection is empty")
            return result
        if isinstance(result, SelectedText):
            return reading_selection_from_selected_text(result, context=context)
        raise SelectionError("reading selection provider returned unsupported result")

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
                    selected = self._selected_from_provider(provider, context)

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

    def _capture_reading_from(
        self,
        providers: tuple[SelectionProvider, ...],
        *,
        context: SelectionContext | None,
        mode: str,
    ) -> ReadingSelection:
        if self._busy:
            raise SelectionError("selection already in progress")
        self._busy = True
        try:
            last_error: SelectionError | None = None
            for provider in providers:
                try:
                    selection = self._reading_from_provider(provider, context)
                    self.logger.info(
                        "selection_provider_used provider=%s mode=%s capture=reading",
                        selection.provider,
                        mode,
                    )
                    return selection
                except SelectionError as exc:
                    last_error = exc
                    self.logger.debug(
                        "selection_provider_failed provider=%s mode=%s capture=reading error_type=%s",
                        type(provider).__name__,
                        mode,
                        type(exc).__name__,
                    )
                except Exception as exc:
                    error = SelectionError("reading selection provider failed")
                    error.__cause__ = exc
                    last_error = error
                    self.logger.debug(
                        "selection_provider_failed provider=%s mode=%s capture=reading error_type=%s",
                        type(provider).__name__,
                        mode,
                        type(exc).__name__,
                    )

            if last_error is not None:
                self.logger.info(
                    "selection_provider_failed_all mode=%s capture=reading",
                    mode,
                )
                raise last_error
            raise SelectionError("no selection provider is configured")
        finally:
            self._busy = False

    select = get_selected_text


__all__ = ["SelectionManager"]
