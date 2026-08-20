from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def _run_fresh_import(code: str) -> subprocess.CompletedProcess[str]:
    project_root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )


def test_agent_workflow_can_be_imported_before_translation_package() -> None:
    result = _run_fresh_import(
        "from app.agent.workflow import DEFAULT_AGENT_GRAPH; "
        "from app.translation.task import TranslationTask; "
        "assert DEFAULT_AGENT_GRAPH is not None; "
        "assert TranslationTask is not None"
    )

    assert result.returncode == 0, result.stderr
    assert "partially initialized module" not in result.stderr
    assert "circular import" not in result.stderr.lower()


def test_translation_package_can_be_imported_before_agent_workflow() -> None:
    result = _run_fresh_import(
        "from app.translation import TranslationTask; "
        "from app.agent.workflow import DEFAULT_AGENT_GRAPH; "
        "assert TranslationTask is not None; "
        "assert DEFAULT_AGENT_GRAPH is not None"
    )

    assert result.returncode == 0, result.stderr
    assert "partially initialized module" not in result.stderr
    assert "circular import" not in result.stderr.lower()
