# Stage 20.1 — Agent-backed Literature Synthesis

Stage 20.1 turns the deterministic Stage 20 Evidence Review plan into a natural-language literature synthesis without weakening the evidence boundary.

## Runtime boundary

```text
Evidence Ledger
  -> live provenance revalidation
  -> human Review Gate
  -> deterministic synthesis plan
  -> resolve allowed evidence IDs from live Research Memory
  -> bounded grounded context
  -> LLM synthesis
  -> Claim–Evidence Verification
  -> release OR deterministic Stage 20 fallback
```

The model does **not** run RAG or decide which ledger entries are admissible. It receives only entries that already passed both the human review decision and the current machine provenance status.

## Admission rules

- `accepted + supported` -> consensus context
- `accepted + contested` -> disagreement context
- `accepted + stale|insufficient` -> excluded
- `rejected|unreviewed|needs_review` -> excluded

Immediately before generation, every provenance link is resolved against live Stage 17 Research Memory and its source status is rechecked. This prevents a previously accepted claim from remaining usable after its source becomes stale.

## Grounding and fallback

Each allowed provenance link becomes an `AgentEvidenceItem` with a program-owned citation label. The existing `GroundedSynthesisService` builds a bounded context and the existing `AgentClaimEvidenceVerifier` enforces citation coverage and lexical evidence support.

If the provider is unavailable, the context cannot be built, or verification fails, the generated text is not released. The API returns the deterministic Stage 20 synthesis instead and marks the result as `fallback`.

## API

`POST /api/research/workspaces/{workspace_id}/literature-synthesis/agent`

Request:

```json
{"query": "optional literature-review focus"}
```

The response includes generation status, provider/model, evidence/citation counts, verification metrics, fallback reason, and the deterministic synthesis plan used as the policy baseline.

## CI

`python scripts/run_agent_literature_synthesis_regression.py --report test-results/agent-literature-synthesis-regression.json`

The regression is deterministic and performs no live provider calls.
