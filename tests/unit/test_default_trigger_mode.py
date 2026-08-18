"""Tests for the shipped automatic-selection default."""

from __future__ import annotations

from app.infrastructure.config import ConfigManager


def test_shipped_defaults_enable_automatic_selection() -> None:
    config = ConfigManager()

    assert config.auto_selection_enabled is True
    assert config.trigger_mode == "auto"
