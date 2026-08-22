from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.agent_core.exceptions import (
    AgentBudgetExceededError,
    AgentToolError,
    AgentToolTimeoutError,
)
from backend.api.agent_dependencies import get_agent_runtime
from backend.main import create_app


class RaisingRuntime:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.events = []

    def execute(self, _state, **_kwargs):
        raise self.error


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (AgentBudgetExceededError("budget exhausted"), 504),
        (AgentToolTimeoutError("tool timed out"), 504),
        (
            AgentToolError(
                "tool failed",
                stage="tool",
                fallback_reason="safe_tool_retries_exhausted",
            ),
            502,
        ),
    ],
)
def test_agent_http_maps_reliability_failures(error: Exception, expected_status: int) -> None:
    runtime = RaisingRuntime(error)
    app = create_app()
    app.dependency_overrides[get_agent_runtime] = lambda: runtime
    client = TestClient(app)

    response = client.post(
        "/api/agent/run",
        json={
            "session_id": "failure-test",
            "user_message": "Explain this",
            "source_text": "Gaussian Process",
            "source_language": "en",
            "target_language": "zh-CN",
        },
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == str(error)
