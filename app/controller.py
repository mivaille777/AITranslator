"""Application-layer coordination between the tray and overlay managers."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QThreadPool, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QMessageBox

from app.infrastructure.config import ConfigManager
from app.infrastructure.logging import sanitized_exception_info
from app.infrastructure.settings import SettingsManager
from app.input.hotkey_manager import GlobalHotkeyManager
from app.input.mouse_selection_manager import (
    MOUSE_SELECTION_SOURCE,
    MouseSelectionManager,
)
from app.models.events import TranslationTriggerEvent
from app.models.translation import TranslationResult
from app.overlay.manager import OverlayManager
from app.overlay.window import DEFAULT_TEST_TEXT
from app.selection.errors import SelectionError
from app.selection.manager import SelectionManager
from app.translation.errors import TextNormalizationError, TranslationError
from app.translation.manager import TranslationManager
from app.translation.request_version import RequestVersionController
from app.translation.task import TranslationTask, TranslationTaskFailure
from app.ui.tray import TrayManager

LOGGER_NAME = "desktop_translator"
TRANSLATION_ERROR_TEXT = "TranslationError: translation request failed."
INPUT_TEXT_ERROR_TEXT = "InputError: selected text is empty or exceeds the limit."
SELECTION_ERROR_TEXT = "SelectionError: unable to read the selected text."
ERROR_DISPLAY_MILLISECONDS = 3000
HEALTH_CHECK_INTERVAL_MILLISECONDS = 5000
ABOUT_DIALOG_TITLE = "关于 AITranslator"
ABOUT_DIALOG_TEXT = (
    "AITranslator\n\n"
    "联系方式：2735545778@qq.com\n"
    "作者：Mivaille"
)


class AppController(QObject):
    """Connect tray intents to application services without UI coupling."""

    def __init__(
        self,
        application: QApplication,
        *,
        overlay_manager: OverlayManager | None = None,
        tray_manager: TrayManager | None = None,
        hotkey_manager: GlobalHotkeyManager | None = None,
        mouse_selection_manager: MouseSelectionManager | None = None,
        selection_manager: SelectionManager | None = None,
        translation_manager: TranslationManager | None = None,
        translation_pool: QThreadPool | None = None,
        config_manager: ConfigManager | Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(application)
        self.application = application
        self.config_manager = config_manager or SettingsManager()
        self.overlay_manager = overlay_manager or OverlayManager(
            config_manager=self.config_manager,
        )
        self.tray_manager = tray_manager or TrayManager(parent=self)
        self.hotkey_manager = hotkey_manager or GlobalHotkeyManager(
            parent=self,
            config_manager=self.config_manager,
        )
        self.selection_manager = selection_manager or SelectionManager(
            config_manager=self.config_manager,
        )
        overlay_hit_test = getattr(
            self.overlay_manager,
            "contains_global_point",
            None,
        )
        if not callable(overlay_hit_test):
            overlay_hit_test = lambda _x, _y: False
        self.mouse_selection_manager = (
            mouse_selection_manager
            if mouse_selection_manager is not None
            else MouseSelectionManager(
                parent=self,
                config_manager=self.config_manager,
                overlay_hit_test=overlay_hit_test,
            )
        )
        self.translation_manager = (
            translation_manager
            if translation_manager is not None
            else TranslationManager(config_manager=self.config_manager)
        )
        self.translation_pool = (
            translation_pool if translation_pool is not None else QThreadPool()
        )
        self.logger = logger or logging.getLogger(LOGGER_NAME)

        self._started = False
        self._shutdown = False
        self._translation_enabled = True
        self._auto_selection_enabled = bool(
            getattr(self.config_manager, "auto_selection_enabled", True)
        )
        self._overlay_visible = False
        self._last_source_text = ""
        self._last_translation_text = ""
        self._translation_tasks: set[TranslationTask] = set()
        self._request_versions = RequestVersionController()
        self._settings_window = None
        self._error_hide_timer = QTimer(self)
        self._error_hide_timer.setSingleShot(True)
        self._error_hide_timer.timeout.connect(self._hide_translation_error)
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(HEALTH_CHECK_INTERVAL_MILLISECONDS)
        self._health_timer.timeout.connect(self._check_runtime_health)

        self._connect_tray_signals()
        self.hotkey_manager.triggered.connect(self._on_translation_triggered)
        self.mouse_selection_manager.triggered.connect(
            self._on_translation_triggered,
        )
        connect_overlay_context = getattr(
            self.overlay_manager,
            "connect_context_menu",
            None,
        )
        if callable(connect_overlay_context):
            self._safe_call(
                "overlay_context_menu_connect_failed",
                connect_overlay_context,
                self._on_overlay_context_action,
            )
        self._synchronize_tray_state()
        self._apply_overlay_visual_settings()
        if bool(getattr(self.config_manager, "overlay_locked", False)):
            self._lock_overlay()
        self.application.aboutToQuit.connect(self.shutdown)

    @property
    def translation_enabled(self) -> bool:
        """Return the current translation-enabled state."""

        return self._translation_enabled

    @property
    def auto_selection_enabled(self) -> bool:
        """Return whether automatic mouse-selection mode is active."""

        return self._auto_selection_enabled

    @property
    def overlay_visible(self) -> bool:
        """Return whether the controller last showed the overlay."""

        return self._overlay_visible

    @property
    def latest_request_id(self) -> int:
        """Return the newest translation request submitted by this controller."""

        return self._request_versions.latest_request_id

    def _log_exception(self, event: str, exc: BaseException) -> None:
        """Record a diagnostic traceback without copying request contents."""

        self.logger.error(
            "%s error_type=%s",
            event,
            type(exc).__name__,
            exc_info=sanitized_exception_info(exc),
        )

    def _safe_call(self, event: str, callback: Any, *args: Any, **kwargs: Any) -> Any:
        """Call a UI/service boundary without letting one module escape."""

        try:
            return callback(*args, **kwargs)
        except Exception as exc:
            self._log_exception(event, exc)
            return None

    def _check_runtime_health(self) -> None:
        """Periodically recover listeners that died outside the Qt thread."""

        if self._shutdown:
            return
        checks = (
            ("global_hotkey", self.hotkey_manager),
            ("mouse_selection", self.mouse_selection_manager),
        )
        for name, manager in checks:
            ensure_running = getattr(manager, "ensure_running", None)
            if not callable(ensure_running):
                continue
            try:
                ensure_running()
            except Exception as exc:
                self._log_exception(f"{name}_health_check_failed", exc)

    def _hide_translation_error(self) -> None:
        """Hide a transient user-facing error after its display window."""

        if self._shutdown or not self._overlay_visible:
            return
        try:
            self.overlay_manager.hide_overlay()
        except Exception as exc:
            self._log_exception("translation_error_hide_failed", exc)
        self._overlay_visible = False
        try:
            self.tray_manager.set_overlay_visible(False)
        except Exception as exc:
            self._log_exception("tray_error_visibility_update_failed", exc)
        self.logger.info("translation_error_hidden")

    def start(self, *, start_hotkey: bool = True) -> None:
        """Start the tray-facing application services."""

        if self._started or self._shutdown:
            return
        self._started = True
        try:
            self.tray_manager.show()
        except Exception as exc:
            self._log_exception("tray_start_failed", exc)
        else:
            self.logger.info("tray_started")
        if start_hotkey:
            try:
                self.hotkey_manager.start()
            except Exception as exc:
                # Keep the tray usable if the OS rejects the hook. The
                # failure is recorded without exposing a system traceback.
                self._log_exception("global_hotkey_start_failed", exc)
            else:
                self.logger.info(
                    "global_hotkey_started hotkey=%s",
                    self.hotkey_manager.hotkey,
                )
            if self._auto_selection_enabled:
                self._start_auto_selection()
        self._health_timer.start()

    def shutdown(self) -> None:
        """Release UI state and stop accepting background result updates."""

        if self._shutdown:
            return
        self._shutdown = True
        self._health_timer.stop()
        self._error_hide_timer.stop()

        # ``clear`` cancels tasks that have not started yet. A running
        # provider call cannot be forcefully interrupted safely, so use only
        # a bounded wait here; application shutdown must never wait forever
        # for a remote service. Completed workers are ignored by the slots
        # below because ``_shutdown`` is already true.
        try:
            self.translation_pool.clear()
            self.translation_pool.waitForDone(100)
        except Exception as exc:
            self._log_exception("translation_pool_shutdown_failed", exc)

        try:
            self.hotkey_manager.stop()
        except Exception as exc:
            self._log_exception("global_hotkey_stop_failed", exc)
        try:
            self.mouse_selection_manager.stop()
        except Exception as exc:
            self.logger.error(
                "mouse_selection_stop_failed error_type=%s",
                type(exc).__name__,
            )
        try:
            if self.overlay_manager.is_locked:
                self.overlay_manager.unlock_overlay()
        except Exception as exc:
            self._log_exception("overlay_unlock_shutdown_failed", exc)
        try:
            self.overlay_manager.hide_overlay()
        except Exception as exc:
            self._log_exception("overlay_hide_shutdown_failed", exc)
        try:
            self.tray_manager.hide()
        except Exception as exc:
            self._log_exception("tray_stop_failed", exc)
        if self._settings_window is not None:
            self._settings_window.close()
            self._settings_window = None
        close_translation = getattr(self.translation_manager, "close", None)
        if callable(close_translation):
            try:
                close_translation()
            except Exception as exc:
                self._log_exception("translation_manager_shutdown_failed", exc)
        self.logger.info("application_controller_stopped")

    def _connect_tray_signals(self) -> None:
        self.tray_manager.enable_translation_requested.connect(
            self._enable_translation,
        )
        self.tray_manager.pause_translation_requested.connect(
            self._pause_translation,
        )
        self.tray_manager.auto_selection_requested.connect(
            self._set_auto_selection,
        )
        self.tray_manager.lock_overlay_requested.connect(self._lock_overlay)
        self.tray_manager.unlock_overlay_requested.connect(self._unlock_overlay)
        self.tray_manager.show_test_text_requested.connect(self._show_test_text)
        self.tray_manager.hide_overlay_requested.connect(self._hide_overlay)
        self.tray_manager.settings_requested.connect(self._show_settings)
        self.tray_manager.exit_requested.connect(self._exit_application)

    def _show_settings(self) -> None:
        """Open the non-modal settings page from the tray menu."""

        try:
            if not callable(getattr(self.config_manager, "save", None)):
                self.logger.warning("settings_unavailable")
                return

            if self._settings_window is None:
                from app.ui.settings import SettingsWindow

                self._settings_window = SettingsWindow(self.config_manager)
                self._settings_window.preview_requested.connect(
                    self._preview_overlay_settings,
                )
                self._settings_window.settings_saved.connect(
                    self._apply_saved_settings,
                )
            else:
                self._settings_window.load_settings()

            self._settings_window.show()
            self._settings_window.raise_()
            self._settings_window.activateWindow()
        except Exception as exc:
            self._log_exception("settings_window_open_failed", exc)

    def _preview_overlay_settings(self, values: object) -> None:
        """Apply visual form changes without persisting them yet."""

        if not isinstance(values, dict):
            return
        self._apply_overlay_visual_settings(values)

    def _apply_saved_settings(self, _values: object) -> None:
        """Refresh running services after a successful settings save."""

        try:
            self._apply_runtime_settings()
        except Exception as exc:
            self._log_exception("runtime_settings_apply_failed", exc)
            self._show_translation_error("SettingsError: unable to apply settings.", "SettingsError")

    def _apply_overlay_visual_settings(self, values: dict[str, Any] | None = None) -> None:
        """Apply safe Overlay style and position values when supported."""

        source = values or {}
        apply_style = getattr(self.overlay_manager, "apply_style", None)
        if callable(apply_style):
            legacy_opacity = source.get(
                "opacity",
                getattr(self.config_manager, "overlay_opacity", 1.0),
            )
            background_opacity = source.get(
                "background_opacity",
                getattr(
                    self.config_manager,
                    "overlay_background_opacity",
                    legacy_opacity,
                ),
            )
            text_opacity = source.get(
                "text_opacity",
                getattr(self.config_manager, "overlay_text_opacity", 1.0),
            )
            self._safe_call(
                "overlay_style_apply_failed",
                apply_style,
                font_family=source.get(
                    "font_family",
                    getattr(self.config_manager, "overlay_font_family", "Segoe UI"),
                ),
                font_size=source.get(
                    "font_size",
                    getattr(self.config_manager, "overlay_font_size", 24),
                ),
                background_opacity=background_opacity,
                text_opacity=text_opacity,
                max_width=source.get(
                    "max_width",
                    getattr(self.config_manager, "overlay_max_width", 900),
                ),
            )

        set_position_mode = getattr(self.overlay_manager, "set_position_mode", None)
        if callable(set_position_mode):
            self._safe_call(
                "overlay_position_apply_failed",
                set_position_mode,
                source.get(
                    "position_mode",
                    getattr(
                        self.config_manager,
                        "overlay_position_mode",
                        "desktop_lyrics_bottom",
                    ),
                )
            )

        set_theme = getattr(self.overlay_manager, "set_theme", None)
        if callable(set_theme):
            self._safe_call(
                "overlay_theme_apply_failed",
                set_theme,
                source.get(
                    "theme",
                    getattr(self.config_manager, "overlay_theme", "dark"),
                ),
            )

        set_original_visible = getattr(
            self.overlay_manager,
            "set_original_visible",
            None,
        )
        if callable(set_original_visible):
            self._safe_call(
                "overlay_original_visibility_apply_failed",
                set_original_visible,
                source.get(
                    "show_original",
                    getattr(self.config_manager, "overlay_show_original", False),
                ),
            )

        set_languages = getattr(self.overlay_manager, "set_languages", None)
        if callable(set_languages):
            self._safe_call(
                "overlay_language_display_apply_failed",
                set_languages,
                getattr(
                    self.config_manager,
                    "translation_source_language",
                    "auto",
                ),
                getattr(
                    self.config_manager,
                    "translation_target_language",
                    "zh-CN",
                ),
            )

    def _apply_runtime_settings(self) -> None:
        """Apply persisted values to services without restarting the process."""

        source_language = getattr(
            self.config_manager,
            "translation_source_language",
            "auto",
        )
        target_language = getattr(
            self.config_manager,
            "translation_target_language",
            "zh-CN",
        )
        configure_languages = getattr(
            self.translation_manager,
            "configure_languages",
            None,
        )
        if callable(configure_languages):
            configure_languages(source_language, target_language)
        else:
            if hasattr(self.translation_manager, "default_source_language"):
                self.translation_manager.default_source_language = source_language
            if hasattr(self.translation_manager, "default_target_language"):
                self.translation_manager.default_target_language = target_language

        set_overlay_languages = getattr(
            self.overlay_manager,
            "set_languages",
            None,
        )
        if callable(set_overlay_languages):
            self._safe_call(
                "overlay_language_display_apply_failed",
                set_overlay_languages,
                source_language,
                target_language,
            )

        configure_cache = getattr(self.translation_manager, "configure_cache", None)
        if callable(configure_cache):
            self._safe_call(
                "translation_cache_reconfigure_failed",
                configure_cache,
                enabled=getattr(
                    self.config_manager,
                    "translation_cache_enabled",
                    True,
                ),
                max_size=getattr(
                    self.config_manager,
                    "translation_cache_max_size",
                    128,
                ),
                sqlite_enabled=getattr(
                    self.config_manager,
                    "translation_sqlite_cache_enabled",
                    True,
                ),
                sqlite_path=getattr(
                    self.config_manager,
                    "translation_cache_path",
                    None,
                ),
                history_enabled=getattr(
                    self.config_manager,
                    "translation_history_enabled",
                    False,
                ),
            )

    def _on_overlay_context_action(self, key: str, value: object) -> None:
        """Handle semantic actions emitted by the Overlay right-click menu."""

        if key == "copy_original":
            self._copy_overlay_text("original", self._last_source_text)
            return
        if key == "copy_translation":
            self._copy_overlay_text("translation", self._last_translation_text)
            return
        if key == "hide":
            self._error_hide_timer.stop()
            self._overlay_visible = False
            self._safe_call(
                "tray_overlay_visibility_update_failed",
                self.tray_manager.set_overlay_visible,
                False,
            )
            self.logger.info("overlay_hidden_from_context_menu")
            return
        if key == "lock_position":
            self._safe_call(
                "tray_overlay_lock_state_update_failed",
                self.tray_manager.set_overlay_locked,
                bool(value),
            )
            self.logger.info("overlay_lock_changed_from_context_menu locked=%s", bool(value))
            return
        if key == "always_on_top":
            self.logger.info(
                "overlay_topmost_changed_from_context_menu enabled=%s",
                bool(value),
            )
            return
        if key == "show_original":
            self._persist_overlay_menu_setting(
                "show_original",
                bool(value),
            )
            self.logger.info(
                "overlay_original_visibility_changed_from_context_menu visible=%s",
                bool(value),
            )
            return
        if key == "source_language":
            source_language = str(value).strip() or "auto"
            configure_languages = getattr(
                self.translation_manager,
                "configure_languages",
                None,
            )
            if callable(configure_languages):
                self._safe_call(
                    "translation_language_apply_failed",
                    configure_languages,
                    source_language,
                    "zh-CN",
                )
            self._persist_translation_menu_language(source_language)
            self.logger.info(
                "translation_source_language_changed_from_context_menu language=%s",
                source_language,
            )
            return
        if key in {
            "font_size",
            "opacity",
            "background_opacity",
            "text_opacity",
            "theme",
        }:
            setting_key = key
            setting_value = value
            if key == "font_size":
                try:
                    setting_value = int(value)
                except (TypeError, ValueError):
                    return
            elif key in {"opacity", "background_opacity", "text_opacity"}:
                try:
                    setting_value = float(value)
                except (TypeError, ValueError):
                    return
            else:
                setting_value = str(value)
            self._persist_overlay_menu_setting(setting_key, setting_value)
            self.logger.info(
                "overlay_%s_changed_from_context_menu",
                setting_key,
            )
            return
        if key == "settings":
            self._show_settings()
            return
        if key == "about":
            self._show_about_dialog()
            return
        if key == "exit":
            self._exit_application()

    def _copy_overlay_text(self, kind: str, text: str) -> bool:
        """Copy a known overlay value without logging its contents."""

        if not text:
            self.logger.info("overlay_copy_unavailable kind=%s", kind)
            return False
        try:
            clipboard = QApplication.clipboard()
            if clipboard is None:
                raise RuntimeError("clipboard unavailable")
            clipboard.setText(text)
        except Exception as exc:
            self._log_exception("overlay_copy_failed", exc)
            return False
        show_feedback = getattr(
            self.overlay_manager,
            "show_copy_feedback",
            None,
        )
        if callable(show_feedback):
            self._safe_call(
                "overlay_copy_feedback_failed",
                show_feedback,
            )
        self.logger.info("overlay_text_copied kind=%s text_length=%s", kind, len(text))
        return True

    def _persist_overlay_menu_setting(self, key: str, value: object) -> None:
        """Persist context-menu visual choices when the settings layer exists."""

        save = getattr(self.config_manager, "save", None)
        if not callable(save):
            return
        try:
            overlay_values = {key: value}
            # Keep the old single-opacity key synchronized with the
            # background value so older integrations observe the same choice.
            if key == "background_opacity":
                overlay_values["opacity"] = value
            save({"overlay": overlay_values})
        except Exception as exc:
            self._log_exception("overlay_context_setting_save_failed", exc)

    def _persist_translation_menu_language(self, source_language: str) -> None:
        """Persist a preset source language with the fixed Chinese target."""

        save = getattr(self.config_manager, "save", None)
        if not callable(save):
            return
        try:
            save(
                {
                    "translation": {
                        "source_language": source_language,
                        "target_language": "zh-CN",
                    }
                }
            )
        except Exception as exc:
            self._log_exception("translation_language_setting_save_failed", exc)

    def _show_about_dialog(self) -> None:
        """Show a small non-secret about dialog from the Overlay menu."""

        try:
            parent = getattr(self.overlay_manager, "window", None)
            QMessageBox.information(
                parent,
                ABOUT_DIALOG_TITLE,
                ABOUT_DIALOG_TEXT,
            )
        except Exception as exc:
            self._log_exception("about_dialog_failed", exc)

        configure_provider = getattr(
            self.translation_manager,
            "configure_provider",
            None,
        )
        if callable(configure_provider):
            try:
                configure_provider()
            except Exception as exc:
                # A malformed or unavailable web configuration must not make
                # the running tray application crash after saving settings.
                self._log_exception("translation_provider_reconfigure_failed", exc)

        reconfigure_hotkey = getattr(self.hotkey_manager, "reconfigure", None)
        if callable(reconfigure_hotkey):
            try:
                if not reconfigure_hotkey():
                    self.logger.warning("global_hotkey_reconfigure_failed")
            except Exception as exc:
                self._log_exception("global_hotkey_reconfigure_failed", exc)

        reconfigure_mouse = getattr(
            self.mouse_selection_manager,
            "reconfigure",
            None,
        )
        if callable(reconfigure_mouse):
            try:
                if not reconfigure_mouse():
                    self.logger.warning("mouse_selection_reconfigure_failed")
            except Exception as exc:
                self._log_exception("mouse_selection_reconfigure_failed", exc)

        self._apply_overlay_visual_settings()
        desired_locked = bool(getattr(self.config_manager, "overlay_locked", False))
        if desired_locked and not self.overlay_manager.is_locked:
            self._lock_overlay()
        elif not desired_locked and self.overlay_manager.is_locked:
            self._unlock_overlay()

        self._set_auto_selection(
            bool(getattr(self.config_manager, "auto_selection_enabled", True))
        )

        # QMessageBox runs its own nested event loop.  When it closes, Qt can
        # leave one more geometry/style pass queued for the overlay; refresh
        # after that pass so the source row cannot retain a stale narrow width.
        refresh_layout = getattr(self.overlay_manager, "refresh_layout", None)
        if callable(refresh_layout):
            QTimer.singleShot(
                0,
                lambda: self._safe_call(
                    "overlay_layout_refresh_failed",
                    refresh_layout,
                ),
            )

    def _is_cursor_over_overlay(self) -> bool:
        """Check the current cursor on the Qt thread before hiding a result."""

        contains_global_point = getattr(
            self.overlay_manager,
            "contains_global_point",
            None,
        )
        if not callable(contains_global_point):
            return False
        try:
            cursor_position = QCursor.pos()
            return bool(
                contains_global_point(
                    cursor_position.x(),
                    cursor_position.y(),
                )
            )
        except Exception as exc:
            self.logger.debug(
                "overlay_cursor_hit_test_failed error_type=%s",
                type(exc).__name__,
            )
            return False

    def _on_translation_triggered(self, event: TranslationTriggerEvent) -> None:
        """Read the selection and submit an asynchronous translation request."""

        if event.source == MOUSE_SELECTION_SOURCE:
            self.logger.info(
                "AUTO_SELECTION_TRIGGERED source=%s",
                event.source,
            )
        else:
            self.logger.info(
                "HOTKEY_TRIGGERED hotkey=%s source=%s",
                event.hotkey,
                event.source,
            )

        if not self._translation_enabled:
            if event.source == MOUSE_SELECTION_SOURCE:
                self.logger.info("auto_selection_ignored translation_paused")
            else:
                self.logger.info("selection_trigger_ignored translation_paused")
            return

        # The global mouse listener and Qt can observe a release in different
        # orders. If the cursor is already over the result card, this is an
        # Overlay gesture/hover rather than a new text-selection request. Do
        # this check on the Qt thread as a second guard against a stale native
        # frame geometry from the pynput callback.
        if (
            event.source == MOUSE_SELECTION_SOURCE
            and self._is_cursor_over_overlay()
        ):
            self.logger.info("auto_selection_ignored overlay_hover")
            return

        # A previous result is always-on-top. Hide it before Ctrl+C so it
        # cannot cover the user's selection or become the active window while
        # the foreground application publishes the copied text.
        self._hide_overlay_for_selection()

        try:
            selected = self.selection_manager.get_selected_text()
        except SelectionError as exc:
            self.logger.info(
                "selection_failed error_type=%s",
                type(exc).__name__,
            )
            self._show_translation_error(SELECTION_ERROR_TEXT, "SelectionError")
            return
        except Exception as exc:
            self._log_exception("selection_unexpected_error", exc)
            self._show_translation_error(SELECTION_ERROR_TEXT, "SelectionError")
            return

        self.logger.info(
            "selection_captured text_length=%s provider=%s",
            len(selected.text),
            selected.provider,
        )
        self._last_source_text = selected.text

        try:
            translatable_text = self._prepare_selected_text(selected.text)
        except TextNormalizationError as exc:
            self.logger.info(
                "input_text_rejected error_type=%s",
                type(exc).__name__,
            )
            self._show_translation_error(INPUT_TEXT_ERROR_TEXT, "InputError")
            return

        self._submit_translation(translatable_text)

    def _prepare_selected_text(self, source_text: object | None) -> str:
        """Normalize and cap a selected string before showing/loading it."""

        prepare_source_text = getattr(
            self.translation_manager,
            "prepare_source_text",
            None,
        )
        if callable(prepare_source_text):
            prepared = prepare_source_text(source_text, truncate=True)
            if len(str(source_text or "")) > len(prepared):
                self.logger.info(
                    "selection_truncated max_length=%s",
                    getattr(
                        getattr(self.translation_manager, "text_normalizer", None),
                        "max_length",
                        len(prepared),
                    ),
                )
            return prepared
        return "" if source_text is None else str(source_text)

    def _submit_translation(self, source_text: str) -> None:
        """Submit translation work without blocking the Qt GUI thread."""

        if self._shutdown:
            return

        request_id = self._request_versions.next_request_id()
        task = TranslationTask(
            self.translation_manager,
            source_text,
            request_id=request_id,
            logger=self.logger,
        )
        task.signals.succeeded.connect(self._on_translation_task_succeeded)
        task.signals.failed.connect(self._on_translation_task_failed)
        task.signals.finished.connect(self._on_translation_task_finished)
        self._translation_tasks.add(task)
        self.logger.info(
            "translation_submitted request_id=%s text_length=%s",
            request_id,
            len(source_text),
        )

        try:
            self._show_translation_loading(source_text)
            self.translation_pool.start(task)
        except Exception as exc:
            # QThreadPool normally accepts the task immediately, but preserve
            # the same safe UI behavior if a custom/injected pool rejects it.
            self._translation_tasks.discard(task)
            self._log_exception("translation_task_start_failed", exc)
            self._show_translation_error(
                TRANSLATION_ERROR_TEXT,
                "TranslationError",
            )

    def _show_translation_loading(self, source_text: str) -> None:
        """Display the animated loading card while the worker is running."""

        show_loading = getattr(self.overlay_manager, "show_loading", None)
        if not callable(show_loading):
            return
        try:
            show_loading(
                source_text,
                getattr(
                    self.translation_manager,
                    "default_source_language",
                    "auto",
                ),
                getattr(
                    self.translation_manager,
                    "default_target_language",
                    "zh-CN",
                ),
            )
        except Exception as exc:
            self._log_exception("translation_loading_display_failed", exc)
            return
        self._overlay_visible = True
        self._safe_call(
            "tray_overlay_visibility_update_failed",
            self.tray_manager.set_overlay_visible,
            True,
        )
        self.logger.info("translation_loading_displayed")

    def _on_translation_task_succeeded(self, result: object) -> None:
        """Handle a worker result on the GUI thread only."""

        if self._shutdown:
            return
        if not isinstance(result, TranslationResult):
            self.logger.error(
                "translation_unexpected_result result_type=%s",
                type(result).__name__,
            )
            return
        if not self._request_versions.is_latest(result.request_id):
            self.logger.debug(
                "translation_result_discarded request_id=%s latest_request_id=%s",
                result.request_id,
                self.latest_request_id,
            )
            return
        self._show_translation(
            result.translated_text,
            source_text=result.source_text,
            source_language=result.source_language,
            target_language=result.target_language,
        )

    def _on_translation_task_failed(self, failure: object) -> None:
        """Convert a worker exception into a safe, user-facing result."""

        if self._shutdown:
            return
        if not isinstance(failure, TranslationTaskFailure):
            self.logger.error(
                "translation_unexpected_failure failure_type=%s",
                type(failure).__name__,
            )
            return
        if not self._request_versions.is_latest(failure.request_id):
            self.logger.debug(
                "translation_failure_discarded request_id=%s latest_request_id=%s",
                failure.request_id,
                self.latest_request_id,
            )
            return

        error = failure.error
        if isinstance(error, TextNormalizationError):
            self.logger.info(
                "input_text_rejected error_type=%s",
                type(error).__name__,
            )
            self._show_translation_error(INPUT_TEXT_ERROR_TEXT, "InputError")
            return
        if isinstance(error, TranslationError):
            self.logger.info(
                "translation_failed error_type=%s",
                type(error).__name__,
            )
            self._show_translation_error(TRANSLATION_ERROR_TEXT, "TranslationError")
            return

        self.logger.error(
            "translation_unexpected_error error_type=%s",
            type(error).__name__,
        )

    def _on_translation_task_finished(self, task: object) -> None:
        """Release the controller's keep-alive reference for a completed task."""

        if isinstance(task, TranslationTask):
            self._translation_tasks.discard(task)

    def _hide_overlay_for_selection(self) -> None:
        """Remove the previous result before asking another app to copy."""

        if not self._overlay_visible:
            return
        self._error_hide_timer.stop()
        try:
            self.overlay_manager.hide_overlay()
        except Exception as exc:
            self._log_exception("overlay_hide_for_selection_failed", exc)
        self._overlay_visible = False
        try:
            self.tray_manager.set_overlay_visible(False)
        except Exception as exc:
            self._log_exception("tray_visibility_update_failed", exc)
        self.logger.info("overlay_hidden_for_selection")

    def _show_translation(
        self,
        translated_text: str,
        *,
        source_text: str = "",
        source_language: str = "auto",
        target_language: str = "zh-CN",
    ) -> None:
        self._error_hide_timer.stop()
        try:
            show_translation = getattr(
                self.overlay_manager,
                "show_translation",
                None,
            )
            if callable(show_translation):
                show_translation(
                    source_text,
                    translated_text,
                    source_language,
                    target_language,
                )
            else:
                self.overlay_manager.show_text(translated_text)
        except Exception as exc:
            self._log_exception("translation_display_failed", exc)
            return
        self._last_translation_text = translated_text
        self._overlay_visible = True
        try:
            self.tray_manager.set_overlay_visible(True)
        except Exception as exc:
            self._log_exception("tray_visibility_update_failed", exc)
        self.logger.info(
            "translation_displayed text_length=%s",
            len(translated_text),
        )

    def _show_translation_error(self, message: str, error_type: str) -> None:
        """Display a safe provider error without exposing SDK details."""

        self._error_hide_timer.stop()
        try:
            self.overlay_manager.show_text(message)
        except Exception as exc:
            self._log_exception("translation_error_display_failed", exc)
            return
        self._overlay_visible = True
        try:
            self.tray_manager.set_overlay_visible(True)
        except Exception as exc:
            self._log_exception("tray_visibility_update_failed", exc)
        self._error_hide_timer.start(ERROR_DISPLAY_MILLISECONDS)
        self.logger.info(
            "translation_error_displayed error_type=%s",
            error_type,
        )

    def _synchronize_tray_state(self) -> None:
        self._safe_call(
            "tray_translation_state_sync_failed",
            self.tray_manager.set_translation_enabled,
            self._translation_enabled,
        )
        self._safe_call(
            "tray_auto_selection_state_sync_failed",
            self.tray_manager.set_auto_selection_enabled,
            self._auto_selection_enabled,
        )
        try:
            overlay_locked = bool(self.overlay_manager.is_locked)
        except Exception as exc:
            self._log_exception("overlay_lock_state_sync_failed", exc)
            overlay_locked = False
        self._safe_call(
            "tray_overlay_lock_state_sync_failed",
            self.tray_manager.set_overlay_locked,
            overlay_locked,
        )
        self._safe_call(
            "tray_overlay_visibility_sync_failed",
            self.tray_manager.set_overlay_visible,
            self._overlay_visible,
        )

    def _enable_translation(self) -> None:
        self._translation_enabled = True
        self._safe_call(
            "tray_translation_enable_failed",
            self.tray_manager.set_translation_enabled,
            True,
        )
        self.logger.info("translation_enabled")

    def _pause_translation(self) -> None:
        self._translation_enabled = False
        self._safe_call(
            "tray_translation_pause_failed",
            self.tray_manager.set_translation_enabled,
            False,
        )
        self.logger.info("translation_paused")

    def _start_auto_selection(self) -> bool:
        """Start the optional mouse listener while keeping the tray usable."""

        try:
            started = self.mouse_selection_manager.start()
        except Exception as exc:
            self._auto_selection_enabled = False
            self._safe_call(
                "tray_auto_selection_state_update_failed",
                self.tray_manager.set_auto_selection_enabled,
                False,
            )
            self._log_exception("mouse_selection_start_failed", exc)
            return False

        if not started:
            self._auto_selection_enabled = False
            self._safe_call(
                "tray_auto_selection_state_update_failed",
                self.tray_manager.set_auto_selection_enabled,
                False,
            )
            self.logger.error("mouse_selection_start_failed error_type=Unknown")
            return False

        self._auto_selection_enabled = True
        self._safe_call(
            "tray_auto_selection_state_update_failed",
            self.tray_manager.set_auto_selection_enabled,
            True,
        )
        self.logger.info("mouse_selection_started")
        return True

    def _set_auto_selection(self, enabled: bool) -> None:
        """Enable or disable automatic mouse-selection mode from the tray."""

        if enabled:
            self._start_auto_selection()
            return

        try:
            self.mouse_selection_manager.stop()
        except Exception as exc:
            self._log_exception("mouse_selection_stop_failed", exc)
        self._auto_selection_enabled = False
        self._safe_call(
            "tray_auto_selection_state_update_failed",
            self.tray_manager.set_auto_selection_enabled,
            False,
        )
        self.logger.info("mouse_selection_stopped")

    def _lock_overlay(self) -> None:
        try:
            locked = bool(self.overlay_manager.lock_overlay())
        except Exception as exc:
            self._log_exception("overlay_lock_failed", exc)
            return
        if locked:
            self._safe_call(
                "tray_overlay_lock_state_update_failed",
                self.tray_manager.set_overlay_locked,
                True,
            )
            self.logger.info("overlay_locked")
        else:
            self.logger.warning("overlay_lock_failed")

    def _unlock_overlay(self) -> None:
        try:
            unlocked = bool(self.overlay_manager.unlock_overlay())
        except Exception as exc:
            self._log_exception("overlay_unlock_failed", exc)
            return
        if unlocked:
            self._safe_call(
                "tray_overlay_lock_state_update_failed",
                self.tray_manager.set_overlay_locked,
                False,
            )
            self.logger.info("overlay_unlocked")
        else:
            self.logger.warning("overlay_unlock_failed")

    def _show_test_text(self) -> None:
        try:
            self.overlay_manager.show_text(DEFAULT_TEST_TEXT)
        except Exception as exc:
            self._log_exception("overlay_test_text_failed", exc)
            return
        self._last_translation_text = DEFAULT_TEST_TEXT
        self._overlay_visible = True
        self._safe_call(
            "tray_overlay_visibility_update_failed",
            self.tray_manager.set_overlay_visible,
            True,
        )
        self.logger.info("overlay_test_text_shown")

    def _hide_overlay(self) -> None:
        try:
            self.overlay_manager.hide_overlay()
        except Exception as exc:
            self._log_exception("overlay_hide_failed", exc)
        self._overlay_visible = False
        self._safe_call(
            "tray_overlay_visibility_update_failed",
            self.tray_manager.set_overlay_visible,
            False,
        )
        self.logger.info("overlay_hidden")

    def _exit_application(self) -> None:
        self.logger.info("exit_requested")
        self.application.quit()
