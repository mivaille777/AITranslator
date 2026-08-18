"""Tests for centralized logging."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.logging import configure_logging


def test_configure_logging_writes_app_log(tmp_path: Path) -> None:
    logger = configure_logging(tmp_path, level="INFO")
    logger.info("bootstrap_test_message")

    for handler in logger.handlers:
        handler.flush()

    log_file = tmp_path / "app.log"
    assert log_file.exists()
    assert "bootstrap_test_message" in log_file.read_text(encoding="utf-8")
