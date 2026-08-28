from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.evaluation.dataset import load_evaluation_dataset
from backend.evaluation.quality_gate import (
    evaluate_regression_quality,
    load_quality_thresholds,
)
from backend.evaluation.regression_fixture import load_regression_fixture
from backend.evaluation.runner import evaluate_agent_batch

DEFAULT_DATASET = "backend/evaluation/datasets/regression.jsonl"
DEFAULT_FIXTURE = "backend/evaluation/fixtures/regression_traces.json"
DEFAULT_THRESHOLDS = "backend/evaluation/datasets/regression_quality_gate.json"
DEFAULT_REPORT = "test-results/agent-regression.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic Agent trajectory regression cases and fail when "
            "the configured quality gate is not satisfied."
        )
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--fixture", default=DEFAULT_FIXTURE)
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_evaluation_dataset(args.dataset)
    fixture = load_regression_fixture(args.fixture)
    thresholds = load_quality_thresholds(args.thresholds)

    dataset_ids = tuple(case.case_id for case in cases)
    fixture_ids = tuple(case.case_id for case in fixture.cases)
    fixture_alignment_pass = dataset_ids == fixture_ids

    batch = evaluate_agent_batch(
        cases,
        resolve_run=lambda case: fixture.get_run(case.case_id),
        resolve_events=fixture.get_events,
    )
    quality = evaluate_regression_quality(batch, thresholds)
    passed = fixture_alignment_pass and quality.passed

    report = {
        "passed": passed,
        "dataset": str(args.dataset),
        "fixture": str(args.fixture),
        "thresholds": str(args.thresholds),
        "fixture_alignment_pass": fixture_alignment_pass,
        "dataset_case_ids": list(dataset_ids),
        "fixture_case_ids": list(fixture_ids),
        "quality_gate": asdict(quality),
        "batch": asdict(batch),
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
