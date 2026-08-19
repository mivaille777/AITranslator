from __future__ import annotations

import subprocess
import sys


def test_research_agent_production_imports_in_fresh_process() -> None:
    code = "\n".join(
        [
            "from app.ai.research_agent_overlay import ResearchAgentOverlayWindow",
            "from app.ai.research_agent_controller import ResearchAgentAppController",
            "from app.research.notes import ResearchNoteStore",
            "from app.main import main",
            "assert ResearchAgentOverlayWindow is not None",
            "assert ResearchAgentAppController is not None",
            "assert ResearchNoteStore is not None",
            "assert callable(main)",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
