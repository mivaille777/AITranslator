from __future__ import annotations

from PySide6.QtWidgets import QFormLayout

from app.ui.compact_settings import apply_compact_settings_layout
from app.ui.design_tokens import SETTINGS, SPACING
from app.ui.settings import SettingsWindow


class MinimalSettingsManager:
    overlay_theme = "dark"

    def get(self, _section: str, _key: str, default=None):
        return default


class EmptyCredentialStore:
    def get(self, _provider: str):
        return None

    def set(self, _provider: str, _api_key: str) -> None:
        return None


def test_settings_navigation_and_forms_use_design_tokens(qtbot) -> None:
    window = SettingsWindow(
        MinimalSettingsManager(),
        credential_store=EmptyCredentialStore(),
    )
    qtbot.addWidget(window)

    scroll = apply_compact_settings_layout(window)

    assert scroll is not None
    assert window._settings_nav_list.width() == SETTINGS.navigation_rail_width
    assert window.minimumWidth() == SETTINGS.navigation_minimum_width
    assert window.minimumHeight() == SETTINGS.minimum_height
    assert window.maximumHeight() == SETTINGS.maximum_height

    form = window.translation_group.layout()
    assert isinstance(form, QFormLayout)
    assert form.horizontalSpacing() == SPACING.md
    assert form.verticalSpacing() == SPACING.sm
    margins = form.contentsMargins()
    assert margins.left() == SPACING.md
    assert margins.top() == SPACING.lg
    assert margins.right() == SPACING.md
    assert margins.bottom() == SPACING.md
