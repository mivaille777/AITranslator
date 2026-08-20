from __future__ import annotations

import subprocess
import sys


def test_desktop_agent_production_imports_in_fresh_process() -> None:
    code = "\n".join(
        [
            "from app.agent.desktop_tool_runtime import DesktopAgentToolCoordinator",
            "from app.ai.desktop_agent_overlay import DesktopAgentOverlayWindow",
            "from app.ai.desktop_agent_controller import DesktopAgentAppController",
            "from app.main import main",
            "assert DesktopAgentToolCoordinator is not None",
            "assert DesktopAgentOverlayWindow is not None",
            "assert DesktopAgentAppController is not None",
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
