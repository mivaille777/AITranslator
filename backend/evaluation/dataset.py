from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from backend.evaluation.agent_evaluator import AgentEvaluationExpectation


def load_evaluation_dataset(path: str | Path) -> tuple[AgentEvaluationExpectation, ...]:
    dataset_path = Path(path)
    cases: list[AgentEvaluationExpectation] = []
    for line_number, raw_line in enumerate(
        dataset_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"Evaluation case line {line_number} must be an object.")
        case_id = str(payload.get("case_id", "")).strip()
        if not case_id:
            raise ValueError(f"Evaluation case line {line_number} is missing case_id.")
        cases.append(
            AgentEvaluationExpectation(
                case_id=case_id,
                expected_intent=str(payload.get("expected_intent", "") or ""),
                expected_tool_name=str(payload.get("expected_tool_name", "") or ""),
                expected_status=str(payload.get("expected_status", "completed") or "completed"),
                max_total_duration_ms=max(0, int(payload.get("max_total_duration_ms", 0) or 0)),
                max_retry_count=max(0, int(payload.get("max_retry_count", 0) or 0)),
                require_zero_failures=bool(payload.get("require_zero_failures", True)),
            )
        )
    return tuple(cases)


def write_evaluation_dataset(
    path: str | Path,
    cases: Iterable[AgentEvaluationExpectation],
) -> None:
    dataset_path = Path(path)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "case_id": case.case_id,
                "expected_intent": case.expected_intent,
                "expected_tool_name": case.expected_tool_name,
                "expected_status": case.expected_status,
                "max_total_duration_ms": case.max_total_duration_ms,
                "max_retry_count": case.max_retry_count,
                "require_zero_failures": case.require_zero_failures,
            },
            ensure_ascii=False,
        )
        for case in cases
    ]
    dataset_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


__all__ = ["load_evaluation_dataset", "write_evaluation_dataset"]
