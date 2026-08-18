"""Settings dialog for the desktop translator."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from app.infrastructure.settings import SettingsManager
from app.overlay.positioning import (
    DEFAULT_POSITION_MODE,
    PositionMode,
    SUPPORTED_POSITION_MODES,
)


class SettingsWindow(QDialog):
    """Edit safe user settings and preview Overlay values immediately."""

    settings_saved = Signal(object)
    preview_requested = Signal(object)

    def __init__(
        self,
        settings_manager: Any | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager or SettingsManager()
        self.setObjectName("SettingsWindow")
        self.setWindowTitle("Desktop Translator 设置")
        self.setModal(False)
        self.resize(560, 730)

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(
            QLabel("修改后点击“保存”，设置会写入本机用户配置并在下次启动继续生效。")
        )

        translation_group = QGroupBox("翻译")
        translation_form = QFormLayout(translation_group)
        self.source_language_edit = QLineEdit()
        self.source_language_edit.setObjectName("SourceLanguageEdit")
        self.source_language_edit.setPlaceholderText("auto")
        self.target_language_edit = QLineEdit()
        self.target_language_edit.setObjectName("TargetLanguageEdit")
        self.target_language_edit.setPlaceholderText("zh-CN")
        translation_form.addRow("源语言", self.source_language_edit)
        translation_form.addRow("目标语言", self.target_language_edit)
        root_layout.addWidget(translation_group)

        web_group = QGroupBox("网页后端参数")
        web_form = QFormLayout(web_group)
        self.web_enabled_check = QCheckBox("启用网页后端")
        self.web_enabled_check.setObjectName("GoogleWebEnabledCheck")
        self.web_endpoint_edit = QLineEdit()
        self.web_endpoint_edit.setObjectName("GoogleWebEndpointEdit")
        self.web_timeout_spin = QSpinBox()
        self.web_timeout_spin.setObjectName("GoogleWebTimeoutSpin")
        self.web_timeout_spin.setRange(500, 60000)
        self.web_timeout_spin.setSuffix(" ms")
        self.web_retries_spin = QSpinBox()
        self.web_retries_spin.setObjectName("GoogleWebRetriesSpin")
        self.web_retries_spin.setRange(0, 3)
        self.web_interval_spin = QSpinBox()
        self.web_interval_spin.setObjectName("GoogleWebIntervalSpin")
        self.web_interval_spin.setRange(0, 60000)
        self.web_interval_spin.setSuffix(" ms")
        web_form.addRow("状态", self.web_enabled_check)
        web_form.addRow("请求地址", self.web_endpoint_edit)
        web_form.addRow("超时", self.web_timeout_spin)
        web_form.addRow("最大重试", self.web_retries_spin)
        web_form.addRow("最小间隔", self.web_interval_spin)
        root_layout.addWidget(web_group)

        trigger_group = QGroupBox("触发")
        trigger_form = QFormLayout(trigger_group)
        self.trigger_mode_combo = QComboBox()
        self.trigger_mode_combo.setObjectName("TriggerModeCombo")
        self.trigger_mode_combo.addItem("仅快捷键", "hotkey")
        self.trigger_mode_combo.addItem("自动划词", "auto")
        self.trigger_mode_combo.addItem("快捷键 + 自动划词", "both")
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setObjectName("HotkeyEdit")
        self.hotkey_edit.setPlaceholderText("alt+q")
        self.debounce_spin = QSpinBox()
        self.debounce_spin.setObjectName("DebounceSpin")
        self.debounce_spin.setRange(0, 60000)
        self.debounce_spin.setSuffix(" ms")
        trigger_form.addRow("触发模式", self.trigger_mode_combo)
        trigger_form.addRow("全局快捷键", self.hotkey_edit)
        trigger_form.addRow("去抖间隔", self.debounce_spin)
        root_layout.addWidget(trigger_group)

        overlay_group = QGroupBox("Overlay")
        overlay_form = QFormLayout(overlay_group)
        self.position_mode_combo = QComboBox()
        self.position_mode_combo.setObjectName("PositionModeCombo")
        position_labels = {
            PositionMode.DESKTOP_LYRICS_BOTTOM.value: "桌面歌词底部",
            PositionMode.DESKTOP_LYRICS_CENTER.value: "桌面居中",
            PositionMode.DESKTOP_LYRICS_TOP.value: "桌面顶部",
            PositionMode.MOUSE_FOLLOW.value: "跟随鼠标",
            PositionMode.CUSTOM_FIXED_POSITION.value: "固定位置",
        }
        for mode in SUPPORTED_POSITION_MODES:
            self.position_mode_combo.addItem(position_labels.get(mode, mode), mode)
        self.font_family_edit = QLineEdit()
        self.font_family_edit.setObjectName("FontFamilyEdit")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setObjectName("FontSizeSpin")
        self.font_size_spin.setRange(8, 200)
        self.font_size_spin.setSuffix(" px")
        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setObjectName("OpacitySpin")
        self.opacity_spin.setRange(0.1, 1.0)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.setDecimals(2)
        # Keep the original attribute as a compatibility alias while
        # presenting the new, explicit background setting in the form.
        self.background_opacity_spin = self.opacity_spin
        self.text_opacity_spin = QDoubleSpinBox()
        self.text_opacity_spin.setObjectName("TextOpacitySpin")
        self.text_opacity_spin.setRange(0.1, 1.0)
        self.text_opacity_spin.setSingleStep(0.05)
        self.text_opacity_spin.setDecimals(2)
        self.max_width_spin = QSpinBox()
        self.max_width_spin.setObjectName("MaxWidthSpin")
        self.max_width_spin.setRange(120, 10000)
        self.max_width_spin.setSuffix(" px")
        self.locked_check = QCheckBox("启动时锁定 Overlay")
        self.locked_check.setObjectName("OverlayLockedCheck")
        self.show_original_check = QCheckBox("默认显示原文")
        self.show_original_check.setObjectName("OverlayShowOriginalCheck")
        overlay_form.addRow("位置模式", self.position_mode_combo)
        overlay_form.addRow("字体", self.font_family_edit)
        overlay_form.addRow("字号", self.font_size_spin)
        overlay_form.addRow("背景透明度", self.opacity_spin)
        overlay_form.addRow("字体透明度", self.text_opacity_spin)
        overlay_form.addRow("最大宽度", self.max_width_spin)
        overlay_form.addRow("状态", self.locked_check)
        overlay_form.addRow("内容", self.show_original_check)
        root_layout.addWidget(overlay_group)

        cache_group = QGroupBox("缓存")
        cache_form = QFormLayout(cache_group)
        self.cache_enabled_check = QCheckBox("启用翻译缓存")
        self.cache_enabled_check.setObjectName("CacheEnabledCheck")
        self.cache_max_size_spin = QSpinBox()
        self.cache_max_size_spin.setObjectName("CacheMaxSizeSpin")
        self.cache_max_size_spin.setRange(1, 100000)
        self.sqlite_enabled_check = QCheckBox("启用 SQLite 持久化缓存")
        self.sqlite_enabled_check.setObjectName("CacheSQLiteEnabledCheck")
        self.history_enabled_check = QCheckBox("允许保存可恢复的原文历史")
        self.history_enabled_check.setObjectName("CacheHistoryEnabledCheck")
        cache_form.addRow("状态", self.cache_enabled_check)
        cache_form.addRow("最大条目", self.cache_max_size_spin)
        cache_form.addRow("持久化", self.sqlite_enabled_check)
        cache_form.addRow("历史记录", self.history_enabled_check)
        root_layout.addWidget(cache_group)

        self.status_label = QLabel()
        self.status_label.setObjectName("SettingsStatusLabel")
        root_layout.addWidget(self.status_label)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
        )
        self.button_box.setObjectName("SettingsButtonBox")
        save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText("保存")
        cancel_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel,
        )
        if cancel_button is not None:
            cancel_button.setText("取消")
        root_layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.save_settings)
        self.button_box.rejected.connect(self.reject)
        self._connect_preview_signals()
        self.load_settings()

    def _connect_preview_signals(self) -> None:
        self.position_mode_combo.currentIndexChanged.connect(self._emit_preview)
        self.font_family_edit.textChanged.connect(self._emit_preview)
        self.font_size_spin.valueChanged.connect(self._emit_preview)
        self.opacity_spin.valueChanged.connect(self._emit_preview)
        self.text_opacity_spin.valueChanged.connect(self._emit_preview)
        self.max_width_spin.valueChanged.connect(self._emit_preview)
        self.show_original_check.toggled.connect(self._emit_preview)

    def load_settings(self) -> None:
        """Populate controls from the current merged configuration."""

        manager = self.settings_manager
        self.source_language_edit.setText(
            str(getattr(manager, "translation_source_language", "auto"))
        )
        self.target_language_edit.setText(
            str(getattr(manager, "translation_target_language", "zh-CN"))
        )
        self.web_enabled_check.setChecked(
            bool(getattr(manager, "google_web_enabled", True))
        )
        self.web_endpoint_edit.setText(
            str(
                getattr(
                    manager,
                    "google_web_endpoint",
                    "https://translate.google.com/translate_a/single",
                )
            )
        )
        self.web_timeout_spin.setValue(
            self._safe_int(
                getattr(manager, "google_web_timeout_seconds", 8.0) * 1000,
                8000,
                minimum=500,
                maximum=60000,
            )
        )
        self.web_retries_spin.setValue(
            self._safe_int(
                getattr(manager, "google_web_max_retries", 0),
                0,
                minimum=0,
                maximum=3,
            )
        )
        self.web_interval_spin.setValue(
            self._safe_int(
                getattr(manager, "google_web_min_interval_seconds", 0.0) * 1000,
                0,
                minimum=0,
                maximum=60000,
            )
        )
        self._set_combo_data(
            self.trigger_mode_combo,
            getattr(manager, "trigger_mode", "hotkey"),
            "hotkey",
        )
        self.hotkey_edit.setText(str(getattr(manager, "hotkey", "alt+q")))
        self.debounce_spin.setValue(
            self._safe_int(
                getattr(manager, "hotkey_debounce_seconds", 0.25) * 1000,
                250,
                minimum=0,
                maximum=60000,
            )
        )
        self._set_combo_data(
            self.position_mode_combo,
            getattr(manager, "overlay_position_mode", DEFAULT_POSITION_MODE),
            DEFAULT_POSITION_MODE,
        )
        self.font_family_edit.setText(
            str(getattr(manager, "overlay_font_family", "Segoe UI"))
        )
        self.font_size_spin.setValue(
            self._safe_int(
                getattr(manager, "overlay_font_size", 24),
                24,
                minimum=8,
                maximum=200,
            )
        )
        legacy_opacity = getattr(manager, "overlay_opacity", 1.0)
        self.opacity_spin.setValue(
            self._safe_float(
                getattr(manager, "overlay_background_opacity", legacy_opacity),
                1.0,
                minimum=0.1,
                maximum=1.0,
            )
        )
        self.text_opacity_spin.setValue(
            self._safe_float(
                getattr(manager, "overlay_text_opacity", 1.0),
                1.0,
                minimum=0.1,
                maximum=1.0,
            )
        )
        self.max_width_spin.setValue(
            self._safe_int(
                getattr(manager, "overlay_max_width", 900),
                900,
                minimum=120,
                maximum=10000,
            )
        )
        self.locked_check.setChecked(bool(getattr(manager, "overlay_locked", False)))
        self.show_original_check.setChecked(
            bool(getattr(manager, "overlay_show_original", False))
        )
        self.cache_enabled_check.setChecked(
            bool(getattr(manager, "translation_cache_enabled", True))
        )
        self.cache_max_size_spin.setValue(
            self._safe_int(
                getattr(manager, "translation_cache_max_size", 128),
                128,
                minimum=1,
                maximum=100000,
            )
        )
        self.sqlite_enabled_check.setChecked(
            bool(getattr(manager, "translation_sqlite_cache_enabled", True))
        )
        self.history_enabled_check.setChecked(
            bool(getattr(manager, "translation_history_enabled", False))
        )
        self.status_label.clear()

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object, fallback: str) -> None:
        index = combo.findData(str(value).strip().lower())
        if index < 0:
            index = combo.findData(fallback)
        combo.setCurrentIndex(max(0, index))

    @staticmethod
    def _safe_int(
        value: object,
        fallback: int,
        *,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            normalized = fallback
        return min(maximum, max(minimum, normalized))

    @staticmethod
    def _safe_float(
        value: object,
        fallback: float,
        *,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            normalized = fallback
        return min(maximum, max(minimum, normalized))

    def collect_settings(self) -> dict[str, dict[str, Any]]:
        """Return the settings-page values in the persisted TOML shape."""

        source_language = self.source_language_edit.text().strip() or "auto"
        target_language = self.target_language_edit.text().strip() or "zh-CN"
        hotkey = self.hotkey_edit.text().strip() or "alt+q"
        return {
            "translation": {
                "source_language": source_language,
                "target_language": target_language,
            },
            "trigger": {
                "mode": str(self.trigger_mode_combo.currentData() or "hotkey"),
                "hotkey": hotkey,
                "debounce_ms": int(self.debounce_spin.value()),
            },
            "overlay": {
                "position_mode": str(
                    self.position_mode_combo.currentData() or DEFAULT_POSITION_MODE
                ),
                "font_family": self.font_family_edit.text().strip() or "Segoe UI",
                "font_size": int(self.font_size_spin.value()),
                "opacity": float(self.opacity_spin.value()),
                "background_opacity": float(self.opacity_spin.value()),
                "text_opacity": float(self.text_opacity_spin.value()),
                "max_width": int(self.max_width_spin.value()),
                "locked": bool(self.locked_check.isChecked()),
                "show_original": bool(self.show_original_check.isChecked()),
            },
            "cache": {
                "enabled": bool(self.cache_enabled_check.isChecked()),
                "max_size": int(self.cache_max_size_spin.value()),
                "sqlite_enabled": bool(self.sqlite_enabled_check.isChecked()),
                "history_enabled": bool(self.history_enabled_check.isChecked()),
            },
            "google_web": {
                "enabled": bool(self.web_enabled_check.isChecked()),
                "endpoint": self.web_endpoint_edit.text().strip()
                or "https://translate.google.com/translate_a/single",
                "timeout_ms": int(self.web_timeout_spin.value()),
                "max_retries": int(self.web_retries_spin.value()),
                "min_interval_ms": int(self.web_interval_spin.value()),
            },
        }

    def preview_settings(self) -> dict[str, Any]:
        """Return only visual values used for live Overlay preview."""

        values = self.collect_settings()
        return dict(values["overlay"])

    def _emit_preview(self, *_args: object) -> None:
        self.preview_requested.emit(self.preview_settings())

    def save_settings(self) -> bool:
        """Persist the form and notify the controller of the new values."""

        try:
            saved = self.settings_manager.save(self.collect_settings())
        except (OSError, TypeError, ValueError):
            self.status_label.setText("保存失败：配置值无效或文件不可写。")
            return False

        self.status_label.setText("已保存。")
        self.settings_saved.emit(saved)
        self.accept()
        return True

    def reject(self) -> None:
        """Discard an unsaved live preview before closing the dialog."""

        self.load_settings()
        self.preview_requested.emit(self.preview_settings())
        super().reject()

    save = save_settings


__all__ = ["SettingsWindow"]
