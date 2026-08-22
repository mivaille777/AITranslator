from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from backend.evaluation.dataset import load_evaluation_dataset
from backend.evaluation.runner import evaluate_agent_batch
from backend.services.agent_trace_store_service import AgentTraceStoreService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate persisted Agent runs against a deterministic JSONL benchmark."
    )
    parser.add_argument(
        "--dataset",
        default="backend/evaluation/datasets/smoke.jsonl",
        help="JSONL file containing expected intent/tool/status/latency criteria.",
    )
    parser.add_argument(
        "--mapping",
        required=True,
        help="JSON object mapping evaluation case_id to persisted run_id.",
    )
    parser.add_argument(
        "--db",
        default="",
        help="Optional path to agent_observability.sqlite3. Uses the app default when omitted.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_evaluation_dataset(args.dataset)
    mapping_payload = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
    if not isinstance(mapping_payload, dict):
        raise ValueError("--mapping must contain a JSON object of case_id -> run_id.")
    mapping = {str(key): str(value) for key, value in mapping_payload.items()}
    store = AgentTraceStoreService(storage_path=args.db or None)

    batch = evaluate_agent_batch(
        cases,
        resolve_run=lambda case: store.get_run(mapping.get(case.case_id, "")),
    )
    print(
        json.dumps(
            {
                "total_cases": batch.total_cases,
                "passed_cases": batch.passed_cases,
                "pass_rate": batch.pass_rate,
                "average_score": batch.average_score,
                "results": [asdict(result) for result in batch.results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if batch.pass_rate == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
