"""Runtime paths for source and frozen Desktop Translator processes."""

from __future__ import annotations

import os
from pathlib import Path
import sys

APPLICATION_DATA_DIRECTORY_NAME = "AITranslator"
DATA_DIRECTORY_ENVIRONMENT_VARIABLE = "AITRANSLATOR_DATA_DIR"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def is_frozen_application() -> bool:
    """Return whether the process is running from a PyInstaller bundle."""

    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Return the read-only root containing bundled application resources."""

    extracted_root = getattr(sys, "_MEIPASS", None)
    if extracted_root:
        return Path(str(extracted_root))
    return PROJECT_ROOT


def data_root() -> Path:
    """Return the writable per-user application data root."""

    configured_root = os.environ.get(DATA_DIRECTORY_ENVIRONMENT_VARIABLE)
    if configured_root and configured_root.strip():
        return Path(configured_root).expanduser()

    if not is_frozen_application():
        return PROJECT_ROOT

    appdata = os.environ.get("APPDATA")
    if appdata and appdata.strip():
        return Path(appdata) / APPLICATION_DATA_DIRECTORY_NAME

    # APPDATA is normally present on Windows. Keep a deterministic fallback
    # for restricted launchers and packaging smoke tests.
    return Path.home() / APPLICATION_DATA_DIRECTORY_NAME


def bundled_default_config_path() -> Path:
    """Return the read-only default TOML shipped inside the application."""

    return bundle_root() / "config" / "default.toml"


def writable_config_dir() -> Path:
    """Return the directory used for user.toml and the local cache."""

    return data_root() / "config"


def user_config_path() -> Path:
    """Return the writable user configuration path."""

    return writable_config_dir() / "user.toml"


def logs_dir() -> Path:
    """Return the application log directory for the current runtime mode."""

    if is_frozen_application() or os.environ.get(
        DATA_DIRECTORY_ENVIRONMENT_VARIABLE
    ):
        return data_root() / "logs"
    # Preserve the existing developer workflow: logs stay in the workspace.
    return Path.cwd() / "logs"


def ensure_runtime_directories() -> None:
    """Create writable runtime directories without touching credentials."""

    for directory in (writable_config_dir(), logs_dir()):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Individual settings/logging layers retain their own safe
            # fallbacks. A restricted directory must not abort application
            # startup.
            continue


__all__ = [
    "APPLICATION_DATA_DIRECTORY_NAME",
    "DATA_DIRECTORY_ENVIRONMENT_VARIABLE",
    "PROJECT_ROOT",
    "bundle_root",
    "bundled_default_config_path",
    "data_root",
    "ensure_runtime_directories",
    "is_frozen_application",
    "logs_dir",
    "user_config_path",
    "writable_config_dir",
]
