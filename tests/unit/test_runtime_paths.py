"""Tests for source and frozen-runtime data paths."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.config import ConfigManager
from app.infrastructure import paths


def test_development_paths_stay_in_the_workspace(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(paths.DATA_DIRECTORY_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setattr(paths.sys, "frozen", False, raising=False)

    assert paths.data_root() == paths.PROJECT_ROOT
    assert paths.bundled_default_config_path() == (
        paths.PROJECT_ROOT / "config" / "default.toml"
    )
    assert paths.logs_dir() == Path.cwd() / "logs"


def test_frozen_paths_use_explicit_writable_data_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime-data"
    monkeypatch.setenv(paths.DATA_DIRECTORY_ENVIRONMENT_VARIABLE, str(runtime_root))
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)

    assert paths.data_root() == runtime_root
    assert paths.bundled_default_config_path() == (
        tmp_path / "bundle" / "config" / "default.toml"
    )
    assert paths.user_config_path() == runtime_root / "config" / "user.toml"
    assert paths.logs_dir() == runtime_root / "logs"

    paths.ensure_runtime_directories()

    assert (runtime_root / "config").is_dir()
    assert (runtime_root / "logs").is_dir()


def test_frozen_relative_cache_path_is_writable_user_data(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime-data"
    bundle_root = tmp_path / "bundle"
    bundle_config = bundle_root / "config"
    bundle_config.mkdir(parents=True)
    default_config = bundle_config / "default.toml"
    default_config.write_text(
        '[cache]\nsqlite_path = "config/translation_cache.sqlite3"\n',
        encoding="utf-8",
    )

    monkeypatch.setenv(paths.DATA_DIRECTORY_ENVIRONMENT_VARIABLE, str(runtime_root))
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(bundle_root), raising=False)

    config = ConfigManager(default_config)

    assert config.translation_cache_path == (
        runtime_root / "config" / "translation_cache.sqlite3"
    )
