"""Shared pytest configuration."""

from __future__ import annotations

import os

# Keep the bootstrap tests usable on headless CI while remaining harmless on
# Windows desktops that have a normal display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
