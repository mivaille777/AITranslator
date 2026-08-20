from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.ui.compact_settings import apply_compact_settings_layout, ensure_settings_widget_visible
from app.ui.settings import SettingsWindow


class FakeCredentialStore:
    def get(self, _provider: str):
        return ""

    def set(self, _provider: str, _api_key: str) -> None:
        return None


class FakeSettingsManager:
    overlay_theme = "dark"
    translation_source_language = "auto"
    translation_target_language = "zh-CN"
    trigger_mode = "both"
    hotkey = "alt+q"
    hotkey_debounce_seconds = 0.25
    overlay_position_mode = "mouse_follow"
    overlay_font_family = "Segoe UI"
    overlay_font_size = 24
    overlay_opacity = 1.0
    overlay_background_opacity = 1.0
    overlay_text_opacity = 1.0
    overlay_max_width = 900
    overlay_locked = False
    overlay_show_original = False
    translation_cache_enabled = True
    translation_cache_max_size = 128
    translation_sqlite_cache_enabled = True
    translation_history_enabled = False
    google_web_enabled = True
    google_web_endpoint = "https://translate.google.com/translate_a/single"
    google_web_timeout_seconds = 8.0
    google_web_max_retries = 0
    google_web_min_interval_seconds = 0.0

    def get(self, _section: str, _key: str, default=None):
        return default

    def save(self, values):
        return values


class FakeBridge:
    def status_snapshot(self):
        return SimpleNamespace(
            running=True,
            host="127.0.0.1",
            port=8765,
            has_extension_activity=True,
            last_activity_age_seconds=4.2,
            last_title="A Research Paper",
            last_url="https://example.org/paper",
            last_heading="3. Methodology",
        )


class FakeNoteStore:
    storage_path = Path("C:/AITrans/research_notes.sqlite3")

    def count(self) -> int:
        return 12


def _window(qtbot) -> SettingsWindow:
    window = SettingsWindow(
        FakeSettingsManager(),
        credential_store=FakeCredentialStore(),
        browser_bridge=FakeBridge(),
        research_note_store=FakeNoteStore(),
    )
    qtbot.addWidget(window)
    return window


def test_settings_navigation_exposes_product_categories(qtbot) -> None:
    window = _window(qtbot)
    scroll = apply_compact_settings_layout(window)

    assert scroll is not None
    names = tuple(window._settings_category_names)
    assert names == (
        "基础",
        "AI 模型",
        "划词与阅读",
        "浏览器集成",
        "外观",
        "研究数据",
        "高级",
    )
    assert not window.translation_group.isHidden()
    assert window.ai_group.isHidden()

    window._settings_nav_list.setCurrentRow(names.index("浏览器集成"))
    assert not window.browser_bridge_group.isHidden()
    assert window.translation_group.isHidden()

    ensure_settings_widget_visible(window, window.ai_group)
    assert window._settings_nav_list.currentRow() == names.index("AI 模型")
    assert not window.ai_group.isHidden()


def test_browser_and_research_runtime_status_are_user_visible(qtbot) -> None:
    window = _window(qtbot)
    apply_compact_settings_layout(window)
    window.refresh_runtime_status()

    assert "正在运行" in window.browser_bridge_status_label.text()
    assert window.browser_bridge_endpoint_label.text() == "127.0.0.1:8765"
    assert "已检测到浏览器扩展活动" in window.browser_extension_activity_label.text()
    assert "A Research Paper" in window.browser_current_page_label.text()
    assert "3. Methodology" in window.browser_current_page_label.text()
    assert window.browser_current_page_label.toolTip() == "https://example.org/paper"
    assert window.research_note_count_label.text() == "12 条"
    assert "research_notes.sqlite3" in window.research_note_path_edit.text()
    assert window.open_research_notes_button.isEnabled()


def test_focus_ai_settings_selects_ai_models_page(qtbot) -> None:
    window = _window(qtbot)
    apply_compact_settings_layout(window)

    window.focus_ai_settings()

    assert window._settings_category_names[window._settings_nav_list.currentRow()] == "AI 模型"
    assert window.ai_provider_combo.hasFocus() or window.ai_provider_combo.focusPolicy()
