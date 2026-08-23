# LangSmith Studio for AITrans

AITrans exposes the production `ReadingAgentGraph` to LangSmith Studio for local graph visualization and debugging. This is a developer-only path; the normal FastAPI/Tauri startup path does not depend on Studio.

## 1. Install the Studio development dependency

From the repository root:

```powershell
cd D:\AITranslator
conda activate aitrans
python -m pip install -e ".[studio]"
langgraph --help
```

`langgraph-cli[inmem]` provides the lightweight local Agent Server used by `langgraph dev`.

## 2. Configure LangSmith access

Create a LangSmith API key in your LangSmith account and expose it only in the current shell:

```powershell
$env:LANGSMITH_API_KEY="lsv2_..."
$env:LANGSMITH_TRACING="false"
```

`langgraph.json` also defaults `LANGSMITH_TRACING` to `false`. This keeps AITrans reading content and graph traces local while using Studio as the local development UI. Do not commit API keys.

## 3. Start the local Agent Server

```powershell
cd D:\AITranslator
conda activate aitrans
langgraph dev
```

The default local Agent Server is available at:

```text
http://127.0.0.1:2024
```

Open Studio:

```text
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

Select the `reading_agent` graph and use **Graph** mode.

## 4. What you should see

Stage 10.5 currently exposes:

```text
START
  ↓
prepare_conversation
  ↓
execute_single_step
  ↓
finalize_conversation
  ↓
END
```

Stage 10.6 will expand `execute_single_step` into explicit routing/planning/tool branches.

## 5. Running the graph from Studio

The public graph state is deliberately JSON-serializable. Runtime-only objects such as cancellation controls and event callbacks are passed through LangGraph runtime context and do not appear in Studio state.

Studio may render a form from the graph state schema. For precise testing, choose **View Raw** and start with:

```json
{
  "agent_state": {
    "session_id": "studio-session",
    "user_input": "总结一下",
    "selected_text": "Bayesian optimization uses a probabilistic surrogate to select informative evaluations.",
    "browser_context": {
      "source_language": "en",
      "target_language": "zh-CN",
      "resource_title": "LangSmith Studio Sample",
      "source_kind": "desktop",
      "request_id": 1,
      "client_id": "langsmith-studio",
      "client_surface": "main"
    }
  }
}
```

The graph will fill the remaining `AgentState` defaults. If the selected action needs an LLM/provider, AITrans must have the same provider credentials/configuration that the normal backend uses.

## 6. Privacy boundary

`LANGSMITH_TRACING=false` is the default Studio development mode for AITrans. Do not enable remote tracing for private reading content unless you intentionally want that data sent to LangSmith.

The SQLite Conversation store remains the AITrans source of truth. Studio threads/checkpoints are debugging state and must not replace the production Conversation lifecycle.
