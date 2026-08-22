import { afterEach, describe, expect, it, vi } from "vitest"

import { getAgentObservabilitySummary, getRecentAgentRuns } from "./agent-observability"

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("agent observability api", () => {
  it("reads the persisted summary contract", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          sample_size: 4,
          completed_runs: 3,
          failed_runs: 1,
          cancelled_runs: 0,
          confirmation_required_runs: 0,
          success_rate: 0.75,
          schema_valid_rate: 1,
          retry_rate: 0.25,
          failure_rate: 0.25,
          timeout_rate: 0,
          fallback_rate: 0.25,
          average_total_duration_ms: 120,
          p95_total_duration_ms: 220,
          average_planning_duration_ms: 20,
          average_tool_duration_ms: 40,
          average_synthesis_duration_ms: 60,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    )
    vi.stubGlobal("fetch", fetchMock)

    const summary = await getAgentObservabilitySummary(25)

    expect(summary.sample_size).toBe(4)
    expect(summary.schema_valid_rate).toBe(1)
    expect(summary.p95_total_duration_ms).toBe(220)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "/api/agent/observability/summary?limit=25",
    )
  })

  it("unwraps recent persisted runs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            runs: [
              {
                run_id: "run-1",
                trace_id: "trace-1",
                session_id: "session-1",
                created_at: "2026-08-22T00:00:00+00:00",
                status: "completed",
                intent: "translate_selection",
                ui_mode: "translation",
                tool_name: "translate_selection",
                provider: "stub",
                model: "stub-model",
                total_duration_ms: 100,
                planning_duration_ms: 20,
                tool_duration_ms: 30,
                synthesis_duration_ms: 50,
                retry_count: 0,
                failure_count: 0,
                timeout_count: 0,
                fallback_reason: "",
                event_count: 7,
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    )

    const runs = await getRecentAgentRuns(3)

    expect(runs).toHaveLength(1)
    expect(runs[0]?.tool_name).toBe("translate_selection")
  })
})
