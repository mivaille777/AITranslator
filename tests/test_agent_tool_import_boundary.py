"""Cold-start import regression for the Agent Tool layer."""

from __future__ import annotations

import subprocess
import sys


def _run_import(code: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_tool_runtime_can_import_before_chat_streaming() -> None:
    _run_import(
        "from app.agent.tool_runtime import AgentToolCoordinator; "
        "from app.ai.chat.streaming import StreamingAIChatTask; "
        "assert AgentToolCoordinator and StreamingAIChatTask"
    )


def test_chat_streaming_can_import_before_tool_runtime() -> None:
    _run_import(
        "from app.ai.chat.streaming import StreamingAIChatTask; "
        "from app.agent.tool_runtime import AgentToolCoordinator; "
        "assert StreamingAIChatTask and AgentToolCoordinator"
    )
