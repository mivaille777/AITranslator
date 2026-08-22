import { afterEach, describe, expect, it, vi } from "vitest"

import { getAgentRuntimeConfig } from "./agent-runtime-config"

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("agent runtime config api", () => {
  it("reads safe model routing and prompt metadata", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) =>
      new Response(
        JSON.stringify({
          model_routes: [
            { role: "planner", provider: "deepseek", model: "deepseek-v4-flash", thinking_enabled: false },
            { role: "agent_synthesis", provider: "deepseek", model: "deepseek-v4-pro", thinking_enabled: false },
          ],
          prompts: [
            { name: "agent.planner", version: "1.1.0", prompt_id: "agent.planner@1.1.0" },
            { name: "chat.reading", version: "1.1.0", prompt_id: "chat.reading@1.1.0" },
          ],
          planner_context_max_chars: 18000,
          chat_context_max_chars: 24000,
          document_content_trust: "untrusted_data",
          planner_argument_policy: "tool_schema_allowlist",
          write_confirmation_required: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    )
    vi.stubGlobal("fetch", fetchMock)

    const config = await getAgentRuntimeConfig()

    expect(config.model_routes[0]?.role).toBe("planner")
    expect(config.model_routes[1]?.model).toBe("deepseek-v4-pro")
    expect(config.prompts[0]?.prompt_id).toBe("agent.planner@1.1.0")
    expect(config.document_content_trust).toBe("untrusted_data")
    expect(config.write_confirmation_required).toBe(true)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/agent/runtime/config")
  })
})
