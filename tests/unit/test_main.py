"""Tests for the Step0 Qt application bootstrap."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.main import APPLICATION_NAME, create_application


def test_create_application_returns_qapplication(qapp: QApplication) -> None:
    application = create_application(["test-app"])

    assert application is qapp
    assert isinstance(application, QApplication)
    assert application.applicationName() == APPLICATION_NAME


def test_smoke_entry_point_exits_cleanly() -> None:
    workspace_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"

    result = subprocess.run(
        [sys.executable, "-m", "app.main", "--smoke-test"],
        cwd=workspace_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, (
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
