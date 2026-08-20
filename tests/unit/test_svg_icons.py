"""Contract tests for the AITrans semantic SVG icon system."""

from __future__ import annotations

import pytest

from app.ui.svg_icons import icon_names, svg_source


_REQUIRED_ICONS = {
    "menu",
    "copy",
    "add",
    "back",
    "delete",
    "stop",
    "refresh",
    "undo",
    "history",
    "settings",
    "sparkle",
    "document",
    "note",
    "library",
    "info",
    "power",
}


def test_svg_registry_contains_core_product_icons() -> None:
    assert _REQUIRED_ICONS.issubset(set(icon_names()))


def test_svg_source_is_local_vector_markup_with_requested_tint() -> None:
    source = svg_source("copy", "#60A5FA")

    assert source.startswith("<svg")
    assert 'viewBox="0 0 24 24"' in source
    assert '#60a5fa' in source.lower()
    assert "Segoe UI" not in source
    assert "<text" not in source


def test_svg_source_sanitizes_invalid_colors() -> None:
    source = svg_source("menu", 'red\" onload="boom')

    assert "onload" not in source
    assert "#f8fafc" in source.lower()


def test_unknown_semantic_icon_fails_explicitly() -> None:
    with pytest.raises(KeyError):
        svg_source("definitely-missing")
