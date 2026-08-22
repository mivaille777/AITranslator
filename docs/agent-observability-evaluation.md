# Agent Observability & Evaluation

Batch 7 adds a local, privacy-preserving observability store and a deterministic evaluation framework for the WebReBuild Agent runtime.

## 1. Runtime persistence

Every `AgentRuntime.execute()` created by the FastAPI dependency records one terminal run into:

```text
agent_observability.sqlite3
```

The file lives in the same writable application configuration area used by other WebReBuild local stores.

Persisted fields are deliberately limited to runtime metadata:

- `run_id`, `trace_id`, `session_id`
- status / intent / UI mode
- selected tool name
- provider / model identifiers
- planner, tool, synthesis and total latency
- retry / failure / timeout counts
- fallback reason
- redacted lifecycle events

The observability store does **not** persist:

- selected reading text
- surrounding paragraph / document context
- user messages
- model output text
- research note content
- raw provider error bodies

Observability failures are best-effort only. A SQLite or telemetry failure must not change Agent execution, confirmation policy or tool side effects.

## 2. Observability API

```text
GET /api/agent/observability/recent?limit=20
GET /api/agent/observability/summary?limit=100
POST /api/agent/evaluation/run/{run_id}
```

The Agent Workspace uses the first two endpoints to display local reliability metrics after terminal runs.

## 3. Evaluation dataset

Seed expectations live at:

```text
backend/evaluation/datasets/smoke.jsonl
```

Each JSONL row defines deterministic expectations such as:

```json
{
  "case_id": "translate-selection",
  "expected_intent": "translate_selection",
  "expected_tool_name": "translate_selection",
  "expected_status": "completed",
  "max_total_duration_ms": 15000,
  "max_retry_count": 1,
  "require_zero_failures": true
}
```

Do not store prompts or expected natural-language answers in this dataset unless they are synthetic/non-sensitive fixtures.

## 4. Mapping benchmark cases to real runs

After executing the registered benchmark tasks through the Agent Workspace or API, create a local mapping file:

```json
{
  "translate-selection": "run-...",
  "explain-selection": "run-...",
  "save-note-confirmation": "run-..."
}
```

Example file name:

```text
outputs/agent-eval-run-map.json
```

Run:

```powershell
conda activate aitrans
cd D:\AITranslator
python scripts/evaluate_agent_runs.py --mapping outputs/agent-eval-run-map.json
```

To evaluate another database or dataset:

```powershell
python scripts/evaluate_agent_runs.py `
  --dataset backend/evaluation/datasets/smoke.jsonl `
  --mapping outputs/agent-eval-run-map.json `
  --db C:\path\to\agent_observability.sqlite3
```

The command prints JSON and exits with:

- `0` when all mapped cases pass
- `1` when at least one case fails or has no mapped persisted run

This makes the evaluator suitable for a regression gate once a reproducible benchmark environment is available.

## 5. Batch metrics

The batch evaluator reports:

- pass rate
- average score
- intent accuracy
- tool-selection accuracy
- status accuracy
- latency pass rate
- retry-policy pass rate
- failure-policy pass rate

The runtime observability summary separately reports operational metrics such as:

- success / failure rate
- retry rate
- timeout rate
- fallback rate
- average total latency
- P95 total latency
- average planner / tool / synthesis latency

## 6. Recommended regression workflow

1. Run the fixed benchmark prompts against a known code revision and model configuration.
2. Capture the resulting `run_id` values.
3. Evaluate them with the registered JSONL expectations.
4. Save only the aggregate evaluation JSON as a CI artifact when needed.
5. Compare intent/tool accuracy, reliability rates and latency distributions before merging Agent runtime changes.
6. Do not treat model-dependent natural-language quality as deterministic CI unless a separate reviewed judge/evaluation protocol is introduced.
