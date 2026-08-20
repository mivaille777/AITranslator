"""Product-oriented settings dialog for AITrans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ai.client import (
    DEFAULT_DEEPSEEK_MODEL,
    DEEPSEEK_BASE_URL,
    SUPPORTED_DEEPSEEK_MODELS,
)
from app.ai.errors import AIConfigurationError
from app.ai.factory import (
    AI_PROVIDER_LABELS,
    DEFAULT_AI_PROVIDER,
    SUPPORTED_AI_PROVIDERS,
    normalize_ai_provider,
    provider_defaults,
)
from app.ai.secrets import ProviderCredentialStore
from app.infrastructure.settings import SettingsManager
from app.overlay.positioning import (
    DEFAULT_POSITION_MODE,
    PositionMode,
    SUPPORTED_POSITION_MODES,
)


class SettingsWindow(QDialog):
    """Edit user settings while exposing the runtime state users care about."""

    settings_saved = Signal(object)
    preview_requested = Signal(object)
    research_notes_requested = Signal()

    def __init__(
        self,
        settings_manager: Any | None = None,
        parent=None,
        *,
        credential_store: ProviderCredentialStore | Any | None = None,
        browser_bridge: Any | None = None,
        research_note_store: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings_manager = settings_manager or SettingsManager()
        self.credential_store = credential_store or ProviderCredentialStore()
        self.browser_bridge = browser_bridge
        self.research_note_store = research_note_store
        self._loaded_api_keys: dict[str, str] = {}
        self._active_ai_provider = ""
        self._pending_settings_category = ""

        self.setObjectName("SettingsWindow")
        self.setWindowTitle("AITrans 设置")
        self.setModal(False)
        self.resize(840, 660)

        root_layout = QVBoxLayout(self)
        intro = QLabel("设置仅保存在本机。修改后点击“保存”即可在下次启动继续生效。")
        intro.setObjectName("SettingsIntro")
        intro.setWordWrap(True)
        root_layout.addWidget(intro)

        self.translation_group = QGroupBox("翻译")
        self.translation_group.setObjectName("SettingsTranslationGroup")
        translation_form = QFormLayout(self.translation_group)
        self.source_language_edit = QLineEdit()
        self.source_language_edit.setObjectName("SourceLanguageEdit")
        self.source_language_edit.setPlaceholderText("auto")
        self.target_language_edit = QLineEdit()
        self.target_language_edit.setObjectName("TargetLanguageEdit")
        self.target_language_edit.setPlaceholderText("zh-CN")
        translation_form.addRow("源语言", self.source_language_edit)
        translation_form.addRow("目标语言", self.target_language_edit)
        root_layout.addWidget(self.translation_group)

        self.ai_group = QGroupBox("AI 模型")
        self.ai_group.setObjectName("AIProviderGroup")
        ai_form = QFormLayout(self.ai_group)
        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.setObjectName("AIProviderCombo")
        for provider in SUPPORTED_AI_PROVIDERS:
            self.ai_provider_combo.addItem(
                AI_PROVIDER_LABELS.get(provider, provider),
                provider,
            )

        self.ai_model_combo = QComboBox()
        self.ai_model_combo.setObjectName("AIModelCombo")
        self.ai_model_combo.setEditable(True)

        self.ai_base_url_edit = QLineEdit()
        self.ai_base_url_edit.setObjectName("AIBaseUrlEdit")
        self.ai_base_url_edit.setPlaceholderText("https://provider.example/v1")

        self.ai_api_key_edit = QLineEdit()
        self.ai_api_key_edit.setObjectName("AIApiKeyEdit")
        self.ai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_api_key_edit.setClearButtonEnabled(True)
        self.ai_api_key_edit.setPlaceholderText("输入当前 Provider 的 API Key")

        credential_note = QLabel(
            "API Key 仅保存在 Windows 凭据管理器，不会写入 user.toml 或日志。"
        )
        credential_note.setWordWrap(True)
        credential_note.setObjectName("AICredentialNote")

        ai_form.addRow("Provider", self.ai_provider_combo)
        ai_form.addRow("Model", self.ai_model_combo)
        ai_form.addRow("Base URL", self.ai_base_url_edit)
        ai_form.addRow("API Key", self.ai_api_key_edit)
        ai_form.addRow("", credential_note)
        root_layout.addWidget(self.ai_group)

        self.reading_group = QGroupBox("阅读交互")
        self.reading_group.setObjectName("SettingsReadingGroup")
        reading_form = QFormLayout(self.reading_group)
        self.ai_chat_selection_capture_check = QCheckBox(
            "Chat 输入框获得焦点后，鼠标划词自动填入"
        )
        self.ai_chat_selection_capture_check.setObjectName(
            "AIChatSelectionCaptureCheck"
        )
        self.ai_chat_selection_capture_check.setToolTip(
            "关闭后，Chat 输入框即使有光标，鼠标划词仍按普通翻译流程处理。"
        )
        reading_note = QLabel(
            "自动划词优先使用 Browser Selection Bridge / Word / UIA，不会在自动路径模拟 Ctrl+C。"
        )
        reading_note.setObjectName("SettingsReadingNote")
        reading_note.setWordWrap(True)
        reading_form.addRow("Chat 划词", self.ai_chat_selection_capture_check)
        reading_form.addRow("", reading_note)
        root_layout.addWidget(self.reading_group)

        self.trigger_group = QGroupBox("触发方式")
        self.trigger_group.setObjectName("SettingsTriggerGroup")
        trigger_form = QFormLayout(self.trigger_group)
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
        root_layout.addWidget(self.trigger_group)

        self.browser_bridge_group = QGroupBox("浏览器集成")
        self.browser_bridge_group.setObjectName("SettingsBrowserIntegrationGroup")
        browser_form = QFormLayout(self.browser_bridge_group)
        self.browser_bridge_status_label = QLabel("未检测", self.browser_bridge_group)
        self.browser_bridge_status_label.setObjectName("BrowserBridgeStatusLabel")
        self.browser_bridge_endpoint_label = QLabel("127.0.0.1:8765", self.browser_bridge_group)
        self.browser_bridge_endpoint_label.setObjectName("BrowserBridgeEndpointLabel")
        self.browser_extension_activity_label = QLabel("等待浏览器扩展活动", self.browser_bridge_group)
        self.browser_extension_activity_label.setObjectName("BrowserExtensionActivityLabel")
        self.browser_extension_activity_label.setWordWrap(True)
        self.browser_current_page_label = QLabel("尚未收到网页上下文", self.browser_bridge_group)
        self.browser_current_page_label.setObjectName("BrowserCurrentPageLabel")
        self.browser_current_page_label.setWordWrap(True)
        self.browser_extension_path_edit = QLineEdit(self.browser_bridge_group)
        self.browser_extension_path_edit.setObjectName("BrowserExtensionPathEdit")
        self.browser_extension_path_edit.setReadOnly(True)
        self.browser_extension_path_edit.setText(str(self._browser_extension_dir()))

        browser_buttons = QWidget(self.browser_bridge_group)
        browser_buttons_layout = QHBoxLayout(browser_buttons)
        browser_buttons_layout.setContentsMargins(0, 0, 0, 0)
        browser_buttons_layout.setSpacing(7)
        self.browser_bridge_refresh_button = QPushButton("重新检测", browser_buttons)
        self.browser_bridge_refresh_button.setObjectName("BrowserBridgeRefreshButton")
        self.browser_extension_open_button = QPushButton("打开扩展目录", browser_buttons)
        self.browser_extension_open_button.setObjectName("BrowserExtensionOpenButton")
        browser_buttons_layout.addWidget(self.browser_bridge_refresh_button)
        browser_buttons_layout.addWidget(self.browser_extension_open_button)
        browser_buttons_layout.addStretch(1)

        browser_help = QLabel(
            "Chrome / Edge 加载 AITrans 扩展后，可直接获得页面标题、章节和选区前后文；未命中时仍会回退到原生 UIA。",
            self.browser_bridge_group,
        )
        browser_help.setObjectName("BrowserIntegrationHelp")
        browser_help.setWordWrap(True)
        browser_form.addRow("Selection Bridge", self.browser_bridge_status_label)
        browser_form.addRow("本机地址", self.browser_bridge_endpoint_label)
        browser_form.addRow("扩展活动", self.browser_extension_activity_label)
        browser_form.addRow("最近页面", self.browser_current_page_label)
        browser_form.addRow("扩展目录", self.browser_extension_path_edit)
        browser_form.addRow("", browser_buttons)
        browser_form.addRow("", browser_help)
        root_layout.addWidget(self.browser_bridge_group)

        self.overlay_group = QGroupBox("悬浮窗外观")
        self.overlay_group.setObjectName("SettingsOverlayGroup")
        overlay_form = QFormLayout(self.overlay_group)
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
        root_layout.addWidget(self.overlay_group)

        self.research_data_group = QGroupBox("研究数据")
        self.research_data_group.setObjectName("SettingsResearchDataGroup")
        research_form = QFormLayout(self.research_data_group)
        self.research_note_count_label = QLabel("0 条", self.research_data_group)
        self.research_note_count_label.setObjectName("ResearchNoteCountLabel")
        self.research_note_path_edit = QLineEdit(self.research_data_group)
        self.research_note_path_edit.setObjectName("ResearchNotePathEdit")
        self.research_note_path_edit.setReadOnly(True)
        self.open_research_notes_button = QPushButton("打开研究笔记库", self.research_data_group)
        self.open_research_notes_button.setObjectName("OpenResearchNotesButton")
        research_note = QLabel(
            "研究笔记与聊天历史分开保存在本机 SQLite 中；删除或编辑笔记不会调用 LLM。",
            self.research_data_group,
        )
        research_note.setObjectName("ResearchDataHelp")
        research_note.setWordWrap(True)
        research_form.addRow("研究笔记", self.research_note_count_label)
        research_form.addRow("数据位置", self.research_note_path_edit)
        research_form.addRow("", self.open_research_notes_button)
        research_form.addRow("", research_note)
        root_layout.addWidget(self.research_data_group)

        self.cache_group = QGroupBox("本地缓存")
        self.cache_group.setObjectName("SettingsCacheGroup")
        cache_form = QFormLayout(self.cache_group)
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
        root_layout.addWidget(self.cache_group)

        self.web_group = QGroupBox("网页翻译后端")
        self.web_group.setObjectName("SettingsWebBackendGroup")
        web_form = QFormLayout(self.web_group)
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
        root_layout.addWidget(self.web_group)

        # The compact settings adapter consumes this declarative map and turns
        # the old long form into left-navigation pages without recreating any
        # controls. Existing object names/signals therefore stay compatible.
        self._settings_category_groups = (
            ("基础", (self.translation_group,)),
            ("AI 模型", (self.ai_group,)),
            ("划词与阅读", (self.reading_group, self.trigger_group)),
            ("浏览器集成", (self.browser_bridge_group,)),
            ("外观", (self.overlay_group,)),
            ("研究数据", (self.research_data_group, self.cache_group)),
            ("高级", (self.web_group,)),
        )

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
        self.ai_provider_combo.currentIndexChanged.connect(
            self._on_ai_provider_changed
        )
        self.browser_bridge_refresh_button.clicked.connect(self.refresh_runtime_status)
        self.browser_extension_open_button.clicked.connect(self._open_browser_extension_dir)
        self.open_research_notes_button.clicked.connect(self.research_notes_requested.emit)
        self._connect_preview_signals()
        self.load_settings()

    @staticmethod
    def _browser_extension_dir() -> Path:
        return Path(__file__).resolve().parents[2] / "browser_extension" / "aitrans_selection_bridge"

    def _open_browser_extension_dir(self) -> None:
        path = self._browser_extension_dir()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @staticmethod
    def _format_activity_age(value: object) -> str:
        try:
            seconds = max(0.0, float(value))
        except (TypeError, ValueError):
            return ""
        if seconds < 1:
            return "刚刚"
        if seconds < 60:
            return f"{int(seconds)} 秒前"
        if seconds < 3600:
            return f"{int(seconds // 60)} 分钟前"
        return f"{int(seconds // 3600)} 小时前"

    def _refresh_browser_status(self) -> None:
        bridge = self.browser_bridge
        running = False
        host = "127.0.0.1"
        port = 8765
        has_activity = False
        age = None
        title = ""
        url = ""
        heading = ""
        status_reader = getattr(bridge, "status_snapshot", None)
        if callable(status_reader):
            try:
                status = status_reader()
            except Exception:
                status = None
            if status is not None:
                running = bool(getattr(status, "running", False))
                host = str(getattr(status, "host", host) or host)
                port = int(getattr(status, "port", port) or port)
                has_activity = bool(getattr(status, "has_extension_activity", False))
                age = getattr(status, "last_activity_age_seconds", None)
                title = str(getattr(status, "last_title", "") or "").strip()
                url = str(getattr(status, "last_url", "") or "").strip()
                heading = str(getattr(status, "last_heading", "") or "").strip()
        elif bridge is not None:
            running = bool(getattr(bridge, "is_running", False))
            host = str(getattr(bridge, "host", host) or host)
            try:
                port = int(getattr(bridge, "bound_port", port))
            except (TypeError, ValueError):
                port = 8765

        self.browser_bridge_status_label.setText("● 正在运行" if running else "○ 未运行")
        self.browser_bridge_status_label.setProperty("bridgeRunning", running)
        self.browser_bridge_endpoint_label.setText(f"{host}:{port}")
        if has_activity:
            age_text = self._format_activity_age(age)
            self.browser_extension_activity_label.setText(
                f"● 已检测到浏览器扩展活动{f' · {age_text}' if age_text else ''}"
            )
        else:
            self.browser_extension_activity_label.setText(
                "○ 尚未检测到扩展活动；安装后在网页中完成一次划词即可验证"
            )

        page_parts = [part for part in (title, f"§ {heading}" if heading else "") if part]
        self.browser_current_page_label.setText(" · ".join(page_parts) or "尚未收到网页上下文")
        self.browser_current_page_label.setToolTip(url)
        extension_path = self._browser_extension_dir()
        self.browser_extension_path_edit.setText(str(extension_path))
        self.browser_extension_open_button.setEnabled(extension_path.exists())

    def _refresh_research_status(self) -> None:
        store = self.research_note_store
        count = 0
        counter = getattr(store, "count", None)
        if callable(counter):
            try:
                count = max(0, int(counter()))
            except Exception:
                count = 0
        self.research_note_count_label.setText(f"{count} 条")
        storage_path = getattr(store, "storage_path", "") if store is not None else ""
        self.research_note_path_edit.setText(str(storage_path or "尚未创建"))
        self.open_research_notes_button.setEnabled(store is not None)

    def refresh_runtime_status(self) -> None:
        """Refresh browser/research diagnostics without touching saved settings."""

        self._refresh_browser_status()
        self._refresh_research_status()

    def _connect_preview_signals(self) -> None:
        self.position_mode_combo.currentIndexChanged.connect(self._emit_preview)
        self.font_family_edit.textChanged.connect(self._emit_preview)
        self.font_size_spin.valueChanged.connect(self._emit_preview)
        self.opacity_spin.valueChanged.connect(self._emit_preview)
        self.text_opacity_spin.valueChanged.connect(self._emit_preview)
        self.max_width_spin.valueChanged.connect(self._emit_preview)
        self.show_original_check.toggled.connect(self._emit_preview)

    def _current_ai_provider(self) -> str:
        return normalize_ai_provider(
            self.ai_provider_combo.currentData() or DEFAULT_AI_PROVIDER
        )

    def _read_saved_api_key(self, provider: str) -> str:
        if provider in self._loaded_api_keys:
            return self._loaded_api_keys[provider]
        try:
            value = self.credential_store.get(provider)
        except AIConfigurationError:
            value = None
        resolved = value.strip() if isinstance(value, str) else ""
        self._loaded_api_keys[provider] = resolved
        return resolved

    def _configure_ai_provider_fields(
        self,
        provider: str,
        *,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        provider = normalize_ai_provider(provider)
        default_model, default_base_url = provider_defaults(provider)

        blocked = self.ai_model_combo.blockSignals(True)
        self.ai_model_combo.clear()
        if provider == DEFAULT_AI_PROVIDER:
            self.ai_model_combo.setEditable(False)
            for model_name in sorted(SUPPORTED_DEEPSEEK_MODELS):
                self.ai_model_combo.addItem(model_name, model_name)
            selected_model = str(model or default_model or DEFAULT_DEEPSEEK_MODEL).strip()
            index = self.ai_model_combo.findData(selected_model)
            if index < 0:
                index = self.ai_model_combo.findData(DEFAULT_DEEPSEEK_MODEL)
            self.ai_model_combo.setCurrentIndex(max(0, index))
            self.ai_base_url_edit.setReadOnly(True)
            self.ai_base_url_edit.setText(DEEPSEEK_BASE_URL)
        else:
            self.ai_model_combo.setEditable(True)
            selected_model = str(model or "").strip()
            if selected_model:
                self.ai_model_combo.addItem(selected_model, selected_model)
                self.ai_model_combo.setCurrentText(selected_model)
            line_edit = self.ai_model_combo.lineEdit()
            if line_edit is not None:
                line_edit.setPlaceholderText("例如 provider-model-id")
            self.ai_base_url_edit.setReadOnly(False)
            self.ai_base_url_edit.setText(
                str(base_url or default_base_url or "").strip()
            )
        self.ai_model_combo.blockSignals(blocked)

    def _on_ai_provider_changed(self, *_args: object) -> None:
        new_provider = self._current_ai_provider()
        if self._active_ai_provider:
            self._loaded_api_keys[self._active_ai_provider] = (
                self.ai_api_key_edit.text().strip()
            )

        old_provider = self._active_ai_provider
        self._active_ai_provider = new_provider
        self.ai_api_key_edit.setText(self._read_saved_api_key(new_provider))

        if old_provider != new_provider:
            current_model = self.ai_model_combo.currentText().strip()
            current_base_url = self.ai_base_url_edit.text().strip()
            if old_provider == DEFAULT_AI_PROVIDER:
                current_model = ""
                current_base_url = ""
            self._configure_ai_provider_fields(
                new_provider,
                model=current_model,
                base_url=current_base_url,
            )

    def load_settings(self) -> None:
        """Populate controls from the current merged configuration."""

        manager = self.settings_manager
        self.source_language_edit.setText(
            str(getattr(manager, "translation_source_language", "auto"))
        )
        self.target_language_edit.setText(
            str(getattr(manager, "translation_target_language", "zh-CN"))
        )

        get = getattr(manager, "get", None)
        provider_value = (
            get("ai", "provider", DEFAULT_AI_PROVIDER)
            if callable(get)
            else DEFAULT_AI_PROVIDER
        )
        provider = normalize_ai_provider(provider_value)
        self._set_combo_data(
            self.ai_provider_combo,
            provider,
            DEFAULT_AI_PROVIDER,
        )
        default_model, default_base_url = provider_defaults(provider)
        model = (
            str(get("ai", "model", default_model) or default_model).strip()
            if callable(get)
            else default_model
        )
        base_url = (
            str(get("ai", "base_url", default_base_url) or default_base_url).strip()
            if callable(get)
            else default_base_url
        )
        self._configure_ai_provider_fields(
            provider,
            model=model,
            base_url=base_url,
        )
        self._active_ai_provider = provider
        self.ai_api_key_edit.setText(self._read_saved_api_key(provider))
        capture_enabled = (
            get("ai", "chat_selection_capture_enabled", True)
            if callable(get)
            else True
        )
        self.ai_chat_selection_capture_check.setChecked(bool(capture_enabled))

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
        self.refresh_runtime_status()

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
        provider = self._current_ai_provider()
        model = self.ai_model_combo.currentText().strip()
        base_url = self.ai_base_url_edit.text().strip()
        if provider == DEFAULT_AI_PROVIDER:
            model = model or DEFAULT_DEEPSEEK_MODEL
            base_url = DEEPSEEK_BASE_URL

        return {
            "translation": {
                "source_language": source_language,
                "target_language": target_language,
            },
            "ai": {
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "chat_selection_capture_enabled": bool(
                    self.ai_chat_selection_capture_check.isChecked()
                ),
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
        """Persist non-secret settings and the active provider credential."""

        provider = self._current_ai_provider()
        api_key = self.ai_api_key_edit.text().strip()
        previous_api_key = self._loaded_api_keys.get(
            provider,
            self._read_saved_api_key(provider),
        )

        if api_key != previous_api_key:
            try:
                self.credential_store.set(provider, api_key)
            except AIConfigurationError:
                self.status_label.setText(
                    "保存失败：无法写入 Windows 凭据管理器中的 API Key。"
                )
                return False
            self._loaded_api_keys[provider] = api_key

        try:
            saved = self.settings_manager.save(self.collect_settings())
        except (OSError, TypeError, ValueError):
            self.status_label.setText("保存失败：配置值无效或文件不可写。")
            return False

        self.status_label.setText("已保存。")
        self.settings_saved.emit(saved)
        self.accept()
        return True

    def _select_settings_category(self, name: str) -> None:
        self._pending_settings_category = str(name or "").strip()
        nav = getattr(self, "_settings_nav_list", None)
        names = getattr(self, "_settings_category_names", ())
        if nav is None:
            return
        try:
            index = tuple(names).index(self._pending_settings_category)
        except ValueError:
            return
        nav.setCurrentRow(index)

    def focus_ai_settings(self) -> None:
        """Open the AI Models page and focus the provider selector."""

        self._select_settings_category("AI 模型")
        self.ai_provider_combo.setFocus()

    def focus_browser_settings(self) -> None:
        self._select_settings_category("浏览器集成")
        self.refresh_runtime_status()
        self.browser_bridge_refresh_button.setFocus()

    def reject(self) -> None:
        """Discard an unsaved live preview before closing the dialog."""

        self.load_settings()
        self.preview_requested.emit(self.preview_settings())
        super().reject()

    save = save_settings


__all__ = ["SettingsWindow"]
