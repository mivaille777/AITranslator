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
ABOUT_DIALOG_TITLE = "å…³äºŽ AITranslator"
ABOUT_DIALOG_TEXT = (
    "AITranslator\n\n"
    "è”ç³»æ–¹å¼ï¼š2735545778@qq.com\n"
    "ä½œè€…ï¼šMivaille"
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
                getattr(self.config_manager, "overlay_text_opacity", 1.0),çž:¶‰žËkºwµça•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰Í•±•Ñ¥½¹}Õ¹•áÁ•Ñ•‘}•ÉÉ½Èˆ°•áŒ¤(€€€€€€€€€€€Í•±˜¹}Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¹}•ÉÉ½È¡M1Q%=9}II=I}QaP°€‰M•±•Ñ¥½¹ÉÉ½Èˆ¤(€€€€€€€€€€€É•ÑÕÉ¸((€€€€€€€Í•±˜¹±½•È¹¥¹™¼ (€€€€€€€€€€€€‰Í•±•Ñ¥½¹}…ÁÑÕÉ•Ñ•áÑ}±•¹Ñ ô•ÌÁÉ½Ù¥‘•Èô•Ìˆ°(€€€€€€€€€€€±•¸¡Í•±•Ñ•¹Ñ•áÐ¤°(€€€€€€€€€€€Í•±•Ñ•¹ÁÉ½Ù¥‘•È°(€€€€€€€€¤(€€€€€€€Í•±˜¹}±…ÍÑ}Í½ÕÉ•}Ñ•áÐ€ôÍ•±•Ñ•¹Ñ•áÐ((€€€€€€€ÑÉäè(€€€€€€€€€€€ÑÉ…¹Í±…Ñ…‰±•}Ñ•áÐ€ôÍ•±˜¹}ÁÉ•Á…É•}Í•±•Ñ•‘}Ñ•áÐ¡Í•±•Ñ•¹Ñ•áÐ¤(€€€€€€€•á•ÁÐQ•áÑ9½Éµ…±¥é…Ñ¥½¹ÉÉ½È…Ì•áŒè(€€€€€€€€€€€Í•±˜¹±½•È¹¥¹™¼ (€€€€€€€€€€€€€€€€‰¥¹ÁÕÑ}Ñ•áÑ}É•©•Ñ••ÉÉ½É}ÑåÁ”ô•Ìˆ°(€€€€€€€€€€€€€€€ÑåÁ”¡•áŒ¤¹}}¹…µ•}|°(€€€€€€€€€€€€¤(€€€€€€€€€€€Í•±˜¹}Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¹}•ÉÉ½È¡%9AUQ}QaQ}II=I}QaP°€‰%¹ÁÕÑÉÉ½Èˆ¤(€€€€€€€€€€€É•ÑÕÉ¸((€€€€€€€Í•±˜¹}ÍÕ‰µ¥Ñ}ÑÉ…¹Í±…Ñ¥½¸¡ÑÉ…¹Í±…Ñ…‰±•}Ñ•áÐ¤((€€€‘•˜}ÁÉ•Á…É•}Í•±•Ñ•‘}Ñ•áÐ¡Í•±˜°Í½ÕÉ•}Ñ•áÐè½‰©•Ðð9½¹”¤€´øÍÑÈè(€€€€€€€€ˆˆ‰9½Éµ…±¥é”…¹…À„Í•±•Ñ•ÍÑÉ¥¹œ‰•™½É”Í¡½Ý¥¹œ½±½…‘¥¹œ¥Ð¸ˆˆˆ((€€€€€€€ÁÉ•Á…É•}Í½ÕÉ•}Ñ•áÐ€ô•Ñ…ÑÑÈ (€€€€€€€€€€€Í•±˜¹ÑÉ…¹Í±…Ñ¥½¹}µ…¹…•È°(€€€€€€€€€€€€‰ÁÉ•Á…É•}Í½ÕÉ•}Ñ•áÐˆ°(€€€€€€€€€€€9½¹”°(€€€€€€€€¤(€€€€€€€¥˜…±±…‰±”¡ÁÉ•Á…É•}Í½ÕÉ•}Ñ•áÐ¤è(€€€€€€€€€€€ÁÉ•Á…É•€ôÁÉ•Á…É•}Í½ÕÉ•}Ñ•áÐ¡Í½ÕÉ•}Ñ•áÐ°ÑÉÕ¹…Ñ”õQÉÕ”¤(€€€€€€€€€€€¥˜±•¸¡ÍÑÈ¡Í½ÕÉ•}Ñ•áÐ½È€ˆˆ¤¤€ø±•¸¡ÁÉ•Á…É•¤è(€€€€€€€€€€€€€€€Í•±˜¹±½•È¹¥¹™¼ (€€€€€€€€€€€€€€€€€€€€‰Í•±•Ñ¥½¹}ÑÉÕ¹…Ñ•µ…á}±•¹Ñ ô•Ìˆ°(€€€€€€€€€€€€€€€€€€€•Ñ…ÑÑÈ (€€€€€€€€€€€€€€€€€€€€€€€•Ñ…ÑÑÈ¡Í•±˜¹ÑÉ…¹Í±…Ñ¥½¹}µ…¹…•È°€‰Ñ•áÑ}¹½Éµ…±¥é•Èˆ°9½¹”¤°(€€€€€€€€€€€€€€€€€€€€€€€€‰µ…á}±•¹Ñ ˆ°(€€€€€€€€€€€€€€€€€€€€€€€±•¸¡ÁÉ•Á…É•¤°(€€€€€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€É•ÑÕÉ¸ÁÉ•Á…É•(€€€€€€€É•ÑÕÉ¸€ˆˆ¥˜Í½ÕÉ•}Ñ•áÐ¥Ì9½¹”•±Í”ÍÑÈ¡Í½ÕÉ•}Ñ•áÐ¤((€€€‘•˜}ÍÕ‰µ¥Ñ}ÑÉ…¹Í±…Ñ¥½¸¡Í•±˜°Í½ÕÉ•}Ñ•áÐèÍÑÈ¤€´ø9½¹”è(€€€€€€€€ˆˆ‰MÕ‰µ¥ÐÑÉ…¹Í±…Ñ¥½¸Ý½É¬Ý¥Ñ¡½ÕÐ‰±½­¥¹œÑ¡”EÐU$Ñ¡É•…¸ˆˆˆ((€€€€€€€¥˜Í•±˜¹}Í¡ÕÑ‘½Ý¸è(€€€€€€€€€€€É•ÑÕÉ¸((€€€€€€€É•ÅÕ•ÍÑ}¥€ôÍ•±˜¹}É•ÅÕ•ÍÑ}Ù•ÉÍ¥½¹Ì¹¹•áÑ}É•ÅÕ•ÍÑ}¥ ¤(€€€€€€€Ñ…Í¬€ôQÉ…¹Í±…Ñ¥½¹Q…Í¬ (€€€€€€€€€€€Í•±˜¹ÑÉ…¹Í±…Ñ¥½¹}µ…¹…•È°(€€€€€€€€€€€Í½ÕÉ•}Ñ•áÐ°(€€€€€€€€€€€É•ÅÕ•ÍÑ}¥õÉ•ÅÕ•ÍÑ}¥°(€€€€€€€€€€€±½•ÈõÍ•±˜¹±½•È°(€€€€€€€€¤(€€€€€€€Ñ…Í¬¹Í¥¹…±Ì¹ÍÕ••‘•¹½¹¹•Ð¡Í•±˜¹}½¹}ÑÉ…¹Í±…Ñ¥½¹}Ñ…Í­}ÍÕ••‘•¤(€€€€€€€Ñ…Í¬¹Í¥¹…±Ì¹™…¥±•¹½¹¹•Ð¡Í•±˜¹}½¹}ÑÉ…¹Í±…Ñ¥½¹}Ñ…Í­}™…¥±•¤(€€€€€€€Ñ…Í¬¹Í¥¹…±Ì¹™¥¹¥Í¡•¹½¹¹•Ð¡Í•±˜¹}½¹}ÑÉ…¹Í±…Ñ¥½¹}Ñ…Í­}™¥¹¥Í¡•¤(€€€€€€€Í•±˜¹}ÑÉ…¹Í±…Ñ¥½¹}Ñ…Í­Ì¹…‘¡Ñ…Í¬¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ (€€€€€€€€€€€€‰ÑÉ…¹Í±…Ñ¥½¹}ÍÕ‰µ¥ÑÑ•É•ÅÕ•ÍÑ}¥ô•ÌÑ•áÑ}±•¹Ñ ô•Ìˆ°(€€€€€€€€€€€É•ÅÕ•ÍÑ}¥°(€€€€€€€€€€€±•¸¡Í½ÕÉ•}Ñ•áÐ¤°(€€€€€€€€¤((€€€€€€€ÑÉäè(€€€€€€€€€€€Í•±˜¹}Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¹}±½…‘¥¹œ¡Í½ÕÉ•}Ñ•áÐ¤(€€€€€€€€€€€Í•±˜¹ÑÉ…¹Í±…Ñ¥½¹}Á½½°¹ÍÑ…ÉÐ¡Ñ…Í¬¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€€ŒEQ¡É•…‘A½½°¹½Éµ…±±ä…•ÁÑÌÑ¡”Ñ…Í¬¥µµ•‘¥…Ñ•±ä°‰ÕÐÁÉ•Í•ÉÙ”(€€€€€€€€€€€€ŒÑ¡”Í…µ”Í…™”U$‰•¡…Ù¥½È¥˜„ÕÍÑ½´½¥¹©•Ñ•Á½½°É•©•ÑÌ¥Ð¸(€€€€€€€€€€€Í•±˜¹}ÑÉ…¹Í±…Ñ¥½¹}Ñ…Í­Ì¹‘¥Í…É¡Ñ…Í¬¤(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰ÑÉ…¹Í±…Ñ¥½¹}Ñ…Í­}ÍÑ…ÉÑ}™…¥±•ˆ°•áŒ¤(€€€€€€€€€€€Í•±˜¹}Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¹}•ÉÉ½È (€€€€€€€€€€€€€€€QI9M1Q%=9}II=I}QaP°(€€€€€€€€€€€€€€€€‰QÉ…¹Í±…Ñ¥½¹ÉÉ½Èˆ°(€€€€€€€€€€€€¤((€€€‘•˜}Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¹}±½…‘¥¹œ¡Í•±˜°Í½ÕÉ•}Ñ•áÐèÍÑÈ¤€´ø9½¹”è(€€€€€€€€ˆˆ‰¥ÍÁ±…äÑ¡”…¹¥µ…Ñ•±½…‘¥¹œ…ÉÝ¡¥±”Ñ¡”Ý½É­•È¥ÌÉÕ¹¹¥¹œ¸ˆˆˆ((€€€€€€€Í¡½Ý}±½…‘¥¹œ€ô•Ñ…ÑÑÈ¡Í•±˜¹½Ù•É±…å}µ…¹…•È°€‰Í¡½Ý}±½…‘¥¹œˆ°9½¹”¤(€€€€€€€¥˜¹½Ð…±±…‰±”¡Í¡½Ý}±½…‘¥¹œ¤è(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€ÑÉäè(€€€€€€€€€€€Í¡½Ý}±½…‘¥¹œ (€€€€€€€€€€€€€€€Í½ÕÉ•}Ñ•áÐ°(€€€€€€€€€€€€€€€•Ñ…ÑÑÈ (€€€€€€€€€€€€€€€€€€€Í•±˜¹ÑÉ…¹Í±…Ñ¥½¹}µ…¹…•È°(€€€€€€€€€€€€€€€€€€€€‰‘•™…Õ±Ñ}Í½ÕÉ•}±…¹Õ…”ˆ°(€€€€€€€€€€€€€€€€€€€€‰…ÕÑ¼ˆ°(€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€€€€•Ñ…ÑÑÈ (€€€€€€€€€€€€€€€€€€€Í•±˜¹ÑÉ…¹Í±…Ñ¥½¹}µ…¹…•È°(€€€€€€€€€€€€€€€€€€€€‰‘•™…Õ±Ñ}Ñ…É•Ñ}±…¹Õ…”ˆ°(€€€€€€€€€€€€€€€€€€€€‰é µ8ˆ°(€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰ÑÉ…¹Í±…Ñ¥½¹}±½…‘¥¹}‘¥ÍÁ±…å}™…¥±•ˆ°•áŒ¤(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€Í•±˜¹}½Ù•É±…å}Ù¥Í¥‰±”€ôQÉÕ”(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}½Ù•É±…å}Ù¥Í¥‰¥±¥Ñå}ÕÁ‘…Ñ•}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}½Ù•É±…å}Ù¥Í¥‰±”°(€€€€€€€€€€€QÉÕ”°(€€€€€€€€¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰ÑÉ…¹Í±…Ñ¥½¹}±½…‘¥¹}‘¥ÍÁ±…å•ˆ¤((€€€‘•˜}½¹}ÑÉ…¹Í±…Ñ¥½¹}Ñ…Í­}ÍÕ••‘•¡Í•±˜°É•ÍÕ±Ðè½‰©•Ð¤€´ø9½¹”è(€€€€€€€€ˆˆ‰!…¹‘±”„Ý½É­•ÈÉ•ÍÕ±Ð½¸Ñ¡”U$Ñ¡É•…½¹±ä¸ˆˆˆ((€€€€€€€¥˜Í•±˜¹}Í¡ÕÑ‘½Ý¸è(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€¥˜¹½Ð¥Í¥¹ÍÑ…¹”¡É•ÍÕ±Ð°QÉ…¹Í±…Ñ¥½¹I•ÍÕ±Ð¤è(€€€€€€€€€€€Í•±˜¹±½•È¹•ÉÉ½È (€€€€€€€€€€€€€€€€‰ÑÉ…¹Í±…Ñ¥½¹}Õ¹•áÁ•Ñ•‘}É•ÍÕ±ÐÉ•ÍÕ±Ñ}ÑåÁ”ô•Ìˆ°(€€€€€€€€€€€€€€€ÑåÁ”¡É•ÍÕ±Ð¤¹}}¹…µ•}|°(€€€€€€€€€€€€¤(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€¥˜¹½ÐÍ•±˜¹}É•ÅÕ•ÍÑ}Ù•ÉÍ¥½¹Ì¹¥Í}±…Ñ•ÍÐ¡É•ÍÕ±Ð¹É•ÅÕ•ÍÑ}¥¤è(€€€€€€€€€€€Í•±˜¹±½•È¹‘•‰Õœ (€€€€€€€€€€€€€€€€‰ÑÉ…¹Í±…Ñ¥½¹}É•ÍÕ±Ñ}‘¥Í…É‘•É•ÅÕ•ÍÑ}¥ô•Ì±…Ñ•ÍÑ}É•ÅÕ•ÍÑ}¥ô•Ìˆ°(€€€€€€€€€€€€€€€É•ÍÕ±Ð¹É•ÅÕ•ÍÑ}¥°(€€€€€€€€€€€€€€€Í•±˜¹±…Ñ•ÍÑ}É•ÅÕ•ÍÑ}¥°(€€€€€€€€€€€€¤(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€Í•±˜¹}Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¸ (€€€€€€€€€€€É•ÍÕ±Ð¹ÑÉ…¹Í±…Ñ•‘}Ñ•áÐ°(€€€€€€€€€€€Í½ÕÉ•}Ñ•áÐõÉ•ÍÕ±Ð¹Í½ÕÉ•}Ñ•áÐ°(€€€€€€€€€€€Í½ÕÉ•}±…¹Õ…”õÉ•ÍÕ±Ð¹Í½ÕÉ•}±…¹Õ…”°(€€€€€€€€€€€Ñ…É•Ñ}±…¹Õ…”õÉ•ÍÕ±Ð¹Ñ…É•Ñ}±…¹Õ…”°(€€€€€€€€¤((€€€‘•˜}½¹}ÑÉ…¹Í±…Ñ¥½¹}Ñ…Í­}™…¥±•¡Í•±˜°™…¥±ÕÉ”è½‰©•Ð¤€´ø9½¹”è(€€€€€€€€ˆˆ‰½¹Ù•ÉÐ„Ý½É­•È•á•ÁÑ¥½¸¥¹Ñ¼„Í…™”°ÕÍ•Èµ™…¥¹œÉ•ÍÕ±Ð¸ˆˆˆ((€€€€€€€¥˜Í•±˜¹}Í¡ÕÑ‘½Ý¸è(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€¥˜¹½Ð¥Í¥¹ÍÑ…¹”¡™…¥±ÕÉ”°QÉ…¹Í±…Ñ¥½¹Q…Í­…¥±ÕÉ”¤è(€€€€€€€€€€€Í•±˜¹±½•È¹•ÉÉ½È (€€€€€€€€€€€€€€€€‰ÑÉ…¹Í±…Ñ¥½¹}Õ¹•áÁ•Ñ•‘}™…¥±ÕÉ”™…¥±ÕÉ•}ÑåÁ”ô•Ìˆ°(€€€€€€€€€€€€€€€ÑåÁ”¡™…¥±ÕÉ”¤¹}}¹…µ•}|°(€€€€€€€€€€€€¤(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€¥˜¹½ÐÍ•±˜¹}É•ÅÕ•ÍÑ}Ù•ÉÍ¥½¹Ì¹¥Í}±…Ñ•ÍÐ¡™…¥±ÕÉ”¹É•ÅÕ•ÍÑ}¥¤è(€€€€€€€€€€€Í•±˜¹±½•È¹‘•‰Õœ (€€€€€€€€€€€€€€€€‰ÑÉ…¹Í±…Ñ¥½¹}™…¥±ÕÉ•}‘¥Í…É‘•É•ÅÕ•ÍÑ}¥ô•Ì±…Ñ•ÍÑ}É•ÅÕ•ÍÑ}¥ô•Ìˆ°(€€€€€€€€€€€€€€€™…¥±ÕÉ”¹É•ÅÕ•ÍÑ}¥°(€€€€€€€€€€€€€€€Í•±˜¹±…Ñ•ÍÑ}É•ÅÕ•ÍÑ}¥°(€€€€€€€€€€€€¤(€€€€€€€€€€€É•ÑÕÉ¸((€€€€€€€•ÉÉ½È€ô™…¥±ÕÉ”¹•ÉÉ½È(€€€€€€€¥˜¥Í¥¹ÍÑ…¹”¡•ÉÉ½È°Q•áÑ9½Éµ…±¥é…Ñ¥½¹ÉÉ½È¤è(€€€€€€€€€€€Í•±˜¹±½•È¹¥¹™¼ (€€€€€€€€€€€€€€€€‰¥¹ÁÕÑ}Ñ•áÑ}É•©•Ñ••ÉÉ½É}ÑåÁ”ô•Ìˆ°(€€€€€€€€€€€€€€€ÑåÁ”¡•ÉÉ½È¤¹}}¹…µ•}|°(€€€€€€€€€€€€¤(€€€€€€€€€€€Í•±˜¹}Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¹}•ÉÉ½È¡%9AUQ}QaQ}II=I}QaP°€‰%¹ÁÕÑÉÉ½Èˆ¤(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€¥˜¥Í¥¹ÍÑ…¹”¡•ÉÉ½È°QÉ…¹Í±…Ñ¥½¹ÉÉ½È¤è(€€€€€€€€€€€Í•±˜¹±½•È¹¥¹™¼ (€€€€€€€€€€€€€€€€‰ÑÉ…¹Í±…Ñ¥½¹}™…¥±••ÉÉ½É}ÑåÁ”ô•Ìˆ°(€€€€€€€€€€€€€€€ÑåÁ”¡•ÉÉ½È¤¹}}¹…µ•}|°(€€€€€€€€€€€€¤(€€€€€€€€€€€Í•±˜¹}Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¹}•ÉÉ½È¡QI9M1Q%=9}II=I}QaP°€‰QÉ…¹Í±…Ñ¥½¹ÉÉ½Èˆ¤(€€€€€€€€€€€É•ÑÕÉ¸((€€€€€€€Í•±˜¹±½•È¹•ÉÉ½È (€€€€€€€€€€€€‰ÑÉ…¹Í±…Ñ¥½¹}Õ¹•áÁ•Ñ•‘}•ÉÉ½È•ÉÉ½É}ÑåÁ”ô•Ìˆ°(€€€€€€€€€€€ÑåÁ”¡•ÉÉ½È¤¹}}¹…µ•}|°(€€€€€€€€¤((€€€‘•˜}½¹}ÑÉ…¹Í±…Ñ¥½¹}Ñ…Í­}™¥¹¥Í¡•¡Í•±˜°Ñ…Í¬è½‰©•Ð¤€´ø9½¹”è(€€€€€€€€ˆˆ‰I•±•…Í”Ñ¡”½¹ÑÉ½±±•ÈÌ­••Àµ…±¥Ù”É•™•É•¹”™½È„½µÁ±•Ñ•Ñ…Í¬¸ˆˆˆ((€€€€€€€¥˜¥Í¥¹ÍÑ…¹”¡Ñ…Í¬°QÉ…¹Í±…Ñ¥½¹Q…Í¬¤è(€€€€€€€€€€€Í•±˜¹}ÑÉ…¹Í±…Ñ¥½¹}Ñ…Í­Ì¹‘¥Í…É¡Ñ…Í¬¤((€€€‘•˜}¡¥‘•}½Ù•É±…å}™½É}Í•±•Ñ¥½¸¡Í•±˜¤€´ø9½¹”è(€€€€€€€€ˆˆ‰I•µ½Ù”Ñ¡”ÁÉ•Ù¥½ÕÌÉ•ÍÕ±Ð‰•™½É”…Í­¥¹œ…¹½Ñ¡•È…ÁÀÑ¼½Áä¸ˆˆˆ((€€€€€€€¥˜¹½ÐÍ•±˜¹}½Ù•É±…å}Ù¥Í¥‰±”è(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€Í•±˜¹}•ÉÉ½É}¡¥‘•}Ñ¥µ•È¹ÍÑ½À ¤(€€€€€€€ÑÉäè(€€€€€€€€€€€Í•±˜¹½Ù•É±…å}µ…¹…•È¹¡¥‘•}½Ù•É±…ä ¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰½Ù•É±…å}¡¥‘•}™½É}Í•±•Ñ¥½¹}™…¥±•ˆ°•áŒ¤(€€€€€€€Í•±˜¹}½Ù•É±…å}Ù¥Í¥‰±”€ô…±Í”(€€€€€€€ÑÉäè(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}½Ù•É±…å}Ù¥Í¥‰±”¡…±Í”¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰ÑÉ…å}Ù¥Í¥‰¥±¥Ñå}ÕÁ‘…Ñ•}™…¥±•ˆ°•áŒ¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰½Ù•É±…å}¡¥‘‘•¹}™½É}Í•±•Ñ¥½¸ˆ¤((€€€‘•˜}Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¸ (€€€€€€€Í•±˜°(€€€€€€€ÑÉ…¹Í±…Ñ•‘}Ñ•áÐèÍÑÈ°(€€€€€€€€¨°(€€€€€€€Í½ÕÉ•}Ñ•áÐèÍÑÈ€ô€ˆˆ°(€€€€€€€Í½ÕÉ•}±…¹Õ…”èÍÑÈ€ô€‰…ÕÑ¼ˆ°(€€€€€€€Ñ…É•Ñ}±…¹Õ…”èÍÑÈ€ô€‰é µ8ˆ°(€€€€¤€´ø9½¹”è(€€€€€€€Í•±˜¹}•ÉÉ½É}¡¥‘•}Ñ¥µ•È¹ÍÑ½À ¤(€€€€€€€ÑÉäè(€€€€€€€€€€€Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¸€ô•Ñ…ÑÑÈ (€€€€€€€€€€€€€€€Í•±˜¹½Ù•É±…å}µ…¹…•È°(€€€€€€€€€€€€€€€€‰Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¸ˆ°(€€€€€€€€€€€€€€€9½¹”°(€€€€€€€€€€€€¤(€€€€€€€€€€€¥˜…±±…‰±”¡Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¸¤è(€€€€€€€€€€€€€€€Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¸ (€€€€€€€€€€€€€€€€€€€Í½ÕÉ•}Ñ•áÐ°(€€€€€€€€€€€€€€€€€€€ÑÉ…¹Í±…Ñ•‘}Ñ•áÐ°(€€€€€€€€€€€€€€€€€€€Í½ÕÉ•}±…¹Õ…”°(€€€€€€€€€€€€€€€€€€€Ñ…É•Ñ}±…¹Õ…”°(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€•±Í”è(€€€€€€€€€€€€€€€Í•±˜¹½Ù•É±…å}µ…¹…•È¹Í¡½Ý}Ñ•áÐ¡ÑÉ…¹Í±…Ñ•‘}Ñ•áÐ¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰ÑÉ…¹Í±…Ñ¥½¹}‘¥ÍÁ±…å}™…¥±•ˆ°•áŒ¤(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€Í•±˜¹}±…ÍÑ}ÑÉ…¹Í±…Ñ¥½¹}Ñ•áÐ€ôÑÉ…¹Í±…Ñ•‘}Ñ•áÐ(€€€€€€€Í•±˜¹}½Ù•É±…å}Ù¥Í¥‰±”€ôQÉÕ”(€€€€€€€ÑÉäè(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}½Ù•É±…å}Ù¥Í¥‰±”¡QÉÕ”¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰ÑÉ…å}Ù¥Í¥‰¥±¥Ñå}ÕÁ‘…Ñ•}™…¥±•ˆ°•áŒ¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ (€€€€€€€€€€€€‰ÑÉ…¹Í±…Ñ¥½¹}‘¥ÍÁ±…å•Ñ•áÑ}±•¹Ñ ô•Ìˆ°(€€€€€€€€€€€±•¸¡ÑÉ…¹Í±…Ñ•‘}Ñ•áÐ¤°(€€€€€€€€¤((€€€‘•˜}Í¡½Ý}ÑÉ…¹Í±…Ñ¥½¹}•ÉÉ½È¡Í•±˜°µ•ÍÍ…”èÍÑÈ°•ÉÉ½É}ÑåÁ”èÍÑÈ¤€´ø9½¹”è(€€€€€€€€ˆˆ‰¥ÍÁ±…ä„Í…™”ÁÉ½Ù¥‘•È•ÉÉ½ÈÝ¥Ñ¡½ÕÐ•áÁ½Í¥¹œM,‘•Ñ…¥±Ì¸ˆˆˆ((€€€€€€€Í•±˜¹}•ÉÉ½É}¡¥‘•}Ñ¥µ•È¹ÍÑ½À ¤(€€€€€€€ÑÉäè(€€€€€€€€€€€Í•±˜¹½Ù•É±…å}µ…¹…•È¹Í¡½Ý}Ñ•áÐ¡µ•ÍÍ…”¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰ÑÉ…¹Í±…Ñ¥½¹}•ÉÉ½É}‘¥ÍÁ±…å}™…¥±•ˆ°•áŒ¤(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€Í•±˜¹}½Ù•É±…å}Ù¥Í¥‰±”€ôQÉÕ”(€€€€€€€ÑÉäè(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}½Ù•É±…å}Ù¥Í¥‰±”¡QÉÕ”¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰ÑÉ…å}Ù¥Í¥‰¥±¥Ñå}ÕÁ‘…Ñ•}™…¥±•ˆ°•áŒ¤(€€€€€€€Í•±˜¹}•ÉÉ½É}¡¥‘•}Ñ¥µ•È¹ÍÑ…ÉÐ¡II=I}%MA1e}5%11%M=9L¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ (€€€€€€€€€€€€‰ÑÉ…¹Í±…Ñ¥½¹}•ÉÉ½É}‘¥ÍÁ±…å••ÉÉ½É}ÑåÁ”ô•Ìˆ°(€€€€€€€€€€€•ÉÉ½É}ÑåÁ”°(€€€€€€€€¤((€€€‘•˜}Íå¹¡É½¹¥é•}ÑÉ…å}ÍÑ…Ñ”¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}ÑÉ…¹Í±…Ñ¥½¹}ÍÑ…Ñ•}Íå¹}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}ÑÉ…¹Í±…Ñ¥½¹}•¹…‰±•°(€€€€€€€€€€€Í•±˜¹}ÑÉ…¹Í±…Ñ¥½¹}•¹…‰±•°(€€€€€€€€¤(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}…ÕÑ½}Í•±•Ñ¥½¹}ÍÑ…Ñ•}Íå¹}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}…ÕÑ½}Í•±•Ñ¥½¹}•¹…‰±•°(€€€€€€€€€€€Í•±˜¹}…ÕÑ½}Í•±•Ñ¥½¹}•¹…‰±•°(€€€€€€€€¤(€€€€€€€ÑÉäè(€€€€€€€€€€€½Ù•É±…å}±½­•€ô‰½½°¡Í•±˜¹½Ù•É±…å}µ…¹…•È¹¥Í}±½­•¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰½Ù•É±…å}±½­}ÍÑ…Ñ•}Íå¹}™…¥±•ˆ°•áŒ¤(€€€€€€€€€€€½Ù•É±…å}±½­•€ô…±Í”(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}½Ù•É±…å}±½­}ÍÑ…Ñ•}Íå¹}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}½Ù•É±…å}±½­•°(€€€€€€€€€€€½Ù•É±…å}±½­•°(€€€€€€€€¤(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}½Ù•É±…å}Ù¥Í¥‰¥±¥Ñå}Íå¹}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}½Ù•É±…å}Ù¥Í¥‰±”°(€€€€€€€€€€€Í•±˜¹}½Ù•É±…å}Ù¥Í¥‰±”°(€€€€€€€€¤((€€€‘•˜}•¹…‰±•}ÑÉ…¹Í±…Ñ¥½¸¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í•±˜¹}ÑÉ…¹Í±…Ñ¥½¹}•¹…‰±•€ôQÉÕ”(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}ÑÉ…¹Í±…Ñ¥½¹}•¹…‰±•}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}ÑÉ…¹Í±…Ñ¥½¹}•¹…‰±•°(€€€€€€€€€€€QÉÕ”°(€€€€€€€€¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰ÑÉ…¹Í±…Ñ¥½¹}•¹…‰±•ˆ¤((€€€‘•˜}Á…ÕÍ•}ÑÉ…¹Í±…Ñ¥½¸¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í•±˜¹}ÑÉ…¹Í±…Ñ¥½¹}•¹…‰±•€ô…±Í”(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}ÑÉ…¹Í±…Ñ¥½¹}Á…ÕÍ•}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}ÑÉ…¹Í±…Ñ¥½¹}•¹…‰±•°(€€€€€€€€€€€…±Í”°(€€€€€€€€¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰ÑÉ…¹Í±…Ñ¥½¹}Á…ÕÍ•ˆ¤((€€€‘•˜}ÍÑ…ÉÑ}…ÕÑ½}Í•±•Ñ¥½¸¡Í•±˜¤€´ø‰½½°è(€€€€€€€€ˆˆ‰MÑ…ÉÐÑ¡”½ÁÑ¥½¹…°µ½ÕÍ”±¥ÍÑ•¹•ÈÝ¡¥±”­••Á¥¹œÑ¡”ÑÉ…äÕÍ…‰±”¸ˆˆˆ((€€€€€€€ÑÉäè(€€€€€€€€€€€ÍÑ…ÉÑ•€ôÍ•±˜¹µ½ÕÍ•}Í•±•Ñ¥½¹}µ…¹…•È¹ÍÑ…ÉÐ ¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}…ÕÑ½}Í•±•Ñ¥½¹}•¹…‰±•€ô…±Í”(€€€€€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€€€€€‰ÑÉ…å}…ÕÑ½}Í•±•Ñ¥½¹}ÍÑ…Ñ•}ÕÁ‘…Ñ•}™…¥±•ˆ°(€€€€€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}…ÕÑ½}Í•±•Ñ¥½¹}•¹…‰±•°(€€€€€€€€€€€€€€€…±Í”°(€€€€€€€€€€€€¤(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰µ½ÕÍ•}Í•±•Ñ¥½¹}ÍÑ…ÉÑ}™…¥±•ˆ°•áŒ¤(€€€€€€€€€€€É•ÑÕÉ¸…±Í”((€€€€€€€¥˜¹½ÐÍÑ…ÉÑ•è(€€€€€€€€€€€Í•±˜¹}…ÕÑ½}Í•±•Ñ¥½¹}•¹…‰±•€ô…±Í”(€€€€€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€€€€€‰ÑÉ…å}…ÕÑ½}Í•±•Ñ¥½¹}ÍÑ…Ñ•}ÕÁ‘…Ñ•}™…¥±•ˆ°(€€€€€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}…ÕÑ½}Í•±•Ñ¥½¹}•¹…‰±•°(€€€€€€€€€€€€€€€…±Í”°(€€€€€€€€€€€€¤(€€€€€€€€€€€Í•±˜¹±½•È¹•ÉÉ½È ‰µ½ÕÍ•}Í•±•Ñ¥½¹}ÍÑ…ÉÑ}™…¥±••ÉÉ½É}ÑåÁ”õU¹­¹½Ý¸ˆ¤(€€€€€€€€€€€É•ÑÕÉ¸…±Í”((€€€€€€€Í•±˜¹}…ÕÑ½}Í•±•Ñ¥½¹}•¹…‰±•€ôQÉÕ”(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}…ÕÑ½}Í•±•Ñ¥½¹}ÍÑ…Ñ•}ÕÁ‘…Ñ•}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}…ÕÑ½}Í•±•Ñ¥½¹}•¹…‰±•°(€€€€€€€€€€€QÉÕ”°(€€€€€€€€¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰µ½ÕÍ•}Í•±•Ñ¥½¹}ÍÑ…ÉÑ•ˆ¤(€€€€€€€É•ÑÕÉ¸QÉÕ”((€€€‘•˜}Í•Ñ}…ÕÑ½}Í•±•Ñ¥½¸¡Í•±˜°•¹…‰±•è‰½½°¤€´ø9½¹”è(€€€€€€€€ˆˆ‰¹…‰±”½È‘¥Í…‰±”…ÕÑ½µ…Ñ¥Œµ½ÕÍ”µÍ•±•Ñ¥½¸µ½‘”™É½´Ñ¡”ÑÉ…ä¸ˆˆˆ((€€€€€€€¥˜•¹…‰±•è(€€€€€€€€€€€Í•±˜¹}ÍÑ…ÉÑ}…ÕÑ½}Í•±•Ñ¥½¸ ¤(€€€€€€€€€€€É•ÑÕÉ¸((€€€€€€€ÑÉäè(€€€€€€€€€€€Í•±˜¹µ½ÕÍ•}Í•±•Ñ¥½¹}µ…¹…•È¹ÍÑ½À ¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰µ½ÕÍ•}Í•±•Ñ¥½¹}ÍÑ½Á}™…¥±•ˆ°•áŒ¤(€€€€€€€Í•±˜¹}…ÕÑ½}Í•±•Ñ¥½¹}•¹…‰±•€ô…±Í”(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}…ÕÑ½}Í•±•Ñ¥½¹}ÍÑ…Ñ•}ÕÁ‘…Ñ•}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}…ÕÑ½}Í•±•Ñ¥½¹}•¹…‰±•°(€€€€€€€€€€€…±Í”°(€€€€€€€€¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰µ½ÕÍ•}Í•±•Ñ¥½¹}ÍÑ½ÁÁ•ˆ¤((€€€‘•˜}±½­}½Ù•É±…ä¡Í•±˜¤€´ø9½¹”è(€€€€€€€ÑÉäè(€€€€€€€€€€€±½­•€ô‰½½°¡Í•±˜¹½Ù•É±…å}µ…¹…•È¹±½­}½Ù•É±…ä ¤¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰½Ù•É±…å}±½­}™…¥±•ˆ°•áŒ¤(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€¥˜±½­•è(€€€€€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€€€€€‰ÑÉ…å}½Ù•É±…å}±½­}ÍÑ…Ñ•}ÕÁ‘…Ñ•}™…¥±•ˆ°(€€€€€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}½Ù•É±…å}±½­•°(€€€€€€€€€€€€€€€QÉÕ”°(€€€€€€€€€€€€¤(€€€€€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰½Ù•É±…å}±½­•ˆ¤(€€€€€€€•±Í”è(€€€€€€€€€€€Í•±˜¹±½•È¹Ý…É¹¥¹œ ‰½Ù•É±…å}±½­}™…¥±•ˆ¤((€€€‘•˜}Õ¹±½­}½Ù•É±…ä¡Í•±˜¤€´ø9½¹”è(€€€€€€€ÑÉäè(€€€€€€€€€€€Õ¹±½­•€ô‰½½°¡Í•±˜¹½Ù•É±…å}µ…¹…•È¹Õ¹±½­}½Ù•É±…ä ¤¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰½Ù•É±…å}Õ¹±½­}™…¥±•ˆ°•áŒ¤(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€¥˜Õ¹±½­•è(€€€€€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€€€€€‰ÑÉ…å}½Ù•É±…å}±½­}ÍÑ…Ñ•}ÕÁ‘…Ñ•}™…¥±•ˆ°(€€€€€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}½Ù•É±…å}±½­•°(€€€€€€€€€€€€€€€…±Í”°(€€€€€€€€€€€€¤(€€€€€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰½Ù•É±…å}Õ¹±½­•ˆ¤(€€€€€€€•±Í”è(€€€€€€€€€€€Í•±˜¹±½•È¹Ý…É¹¥¹œ ‰½Ù•É±…å}Õ¹±½­}™…¥±•ˆ¤((€€€‘•˜}Í¡½Ý}Ñ•ÍÑ}Ñ•áÐ¡Í•±˜¤€´ø9½¹”è(€€€€€€€ÑÉäè(€€€€€€€€€€€Í•±˜¹½Ù•É±…å}µ…¹…•È¹Í¡½Ý}Ñ•áÐ¡U1Q}QMQ}QaP¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰½Ù•É±…å}Ñ•ÍÑ}Ñ•áÑ}™…¥±•ˆ°•áŒ¤(€€€€€€€€€€€É•ÑÕÉ¸(€€€€€€€Í•±˜¹}±…ÍÑ}ÑÉ…¹Í±…Ñ¥½¹}Ñ•áÐ€ôU1Q}QMQ}QaP(€€€€€€€Í•±˜¹}½Ù•É±…å}Ù¥Í¥‰±”€ôQÉÕ”(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}½Ù•É±…å}Ù¥Í¥‰¥±¥Ñå}ÕÁ‘…Ñ•}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}½Ù•É±…å}Ù¥Í¥‰±”°(€€€€€€€€€€€QÉÕ”°(€€€€€€€€¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰½Ù•É±…å}Ñ•ÍÑ}Ñ•áÑ}Í¡½Ý¸ˆ¤((€€€‘•˜}¡¥‘•}½Ù•É±…ä¡Í•±˜¤€´ø9½¹”è(€€€€€€€ÑÉäè(€€€€€€€€€€€Í•±˜¹½Ù•É±…å}µ…¹…•È¹¡¥‘•}½Ù•É±…ä ¤(€€€€€€€•á•ÁÐá•ÁÑ¥½¸…Ì•áŒè(€€€€€€€€€€€Í•±˜¹}±½}•á•ÁÑ¥½¸ ‰½Ù•É±…å}¡¥‘•}™…¥±•ˆ°•áŒ¤(€€€€€€€Í•±˜¹}½Ù•É±…å}Ù¥Í¥‰±”€ô…±Í”(€€€€€€€Í•±˜¹}Í…™•}…±° (€€€€€€€€€€€€‰ÑÉ…å}½Ù•É±…å}Ù¥Í¥‰¥±¥Ñå}ÕÁ‘…Ñ•}™…¥±•ˆ°(€€€€€€€€€€€Í•±˜¹ÑÉ…å}µ…¹…•È¹Í•Ñ}½Ù•É±…å}Ù¥Í¥‰±”°(€€€€€€€€€€€…±Í”°(€€€€€€€€¤(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰½Ù•É±…å}¡¥‘‘•¸ˆ¤((€€€‘•˜}•á¥Ñ}…ÁÁ±¥…Ñ¥½¸¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í•±˜¹±½•È¹¥¹™¼ ‰•á¥Ñ}É•ÅÕ•ÍÑ•ˆ¤(€€€€€€€Í•±˜¹…ÁÁ±¥…Ñ¥½¸¹ÅÕ¥Ð ¤(