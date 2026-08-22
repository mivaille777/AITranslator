from __future__ import annotations

from backend.evaluation.dataset import load_evaluation_dataset


def test_seed_agent_evaluation_dataset_loads() -> None:
    cases = load_evaluation_dataset("backend/evaluation/datasets/smoke.jsonl")

    assert [case.case_id for case in cases] == [
        "translate-selection",
        "explain-selection",
        "save-note-confirmation",
    ]
    assert cases[0].expected_tool_name == "translate_selection"
    assert cases[2].expected_status == "confirmation_required"
