# AITranslator

AITranslator 是一款面向 Windows 的桌面划词翻译与 AI 阅读助手。项目在传统桌面翻译基础上逐步演进为一个由 LangGraph 编排的轻量 Desktop Context Agent：用户可以划词翻译、手动编辑原文实时翻译、围绕当前阅读上下文进入多轮 AI 对话，并让 Agent 调用本地文档与 Web 工具。

## 功能

- 自动检测选中文本并翻译，自动划词翻译默认开启。
- 支持使用 `Alt+Q` 快捷键手动触发翻译，`Ctrl+C` 永远保留为系统复制快捷键。
- 支持 Word、Chrome、Edge、记事本等常见 Windows 应用。
- 通过悬浮窗展示原文/译文，支持直接编辑原文并实时翻译。
- 支持源语言、目标语言独立切换和语言互换；目标语言不会出现 `Auto`。
- Auto 检测完成后显示实际检测语言，例如 `EN·Auto`，并允许直接互换语言方向。
- 支持拖动、边缘/四角缩放、字体随窗口缩放、置顶、隐藏和恢复显示。
- 支持 AI Chat、多轮历史会话、SQLite 会话持久化、模型切换和 Markdown 渲染。
- AI 回答支持流式输出、停止生成、单条复制和重新生成。
- 历史会话支持搜索、重命名、删除和切换。
- AI 可以通过 Human-in-the-loop 工作流提议进入翻译工作区；用户确认后切换，翻译期间仍可通过紧凑 Agent Dock 继续对话，说“翻译完了”即可返回完整 Chat。
- File / Document Agent Tool 支持 PDF、DOCX、TXT、Markdown：`open_file`、`read_document`、`extract_document_text`、`search_document`、`summarize_document`。
- Web Agent Tool 支持 `web_search` 与 `web_read`；网页正文与搜索摘要作为 Tool Observation 注入 Chat，而不是伪装成用户消息。
- 支持托盘运行、设置管理和翻译结果缓存。
- 使用 Google Translate 网页翻译服务，无需配置 Google Cloud 凭据。

## LangGraph Agent architecture

AITranslator 使用 LangGraph 作为应用层任务编排框架，而不是把 LangGraph 仅作为模型调用包装器。当前主要由三个 Agent 图层组成。

### 1. Chat Execution Graph

```text
ChatRequest
   |
prepare
   |
 chat
   |
LLM custom token stream
   |
  END
```

`app/agent/workflow.py` 提供共享 Chat 执行图和 LangGraph `custom` stream。Qt worker 在后台运行 Graph，token 再通过 Qt Signal 增量渲染到悬浮窗。

普通 Google/Web 翻译在生产路径中保持确定性的 `TranslationTask -> TranslationManager -> Provider`，不把带有 SQLite/HTTP connection/Lock 的运行时服务对象放入 Agent State。LangGraph 负责“何时使用翻译能力和工作区”，而不是替代稳定的翻译 Provider 执行层。

### 2. Workspace Agent Graph

```text
User message
    |
classify workspace intent
    |
    +----------------------+------------------+
    |                      |                  |
request translation   continue chat     finish translation
    |                      |                  |
LangGraph interrupt        |           return_to_chat
    |
Human approve / reject
    |
open_translation UI Tool
    |
Translation workspace + compact Agent Dock
```

`app/agent/workspace.py` 把翻译界面视为 Agent 可以申请使用的 Workspace Capability：

- Agent 识别到“我要你帮我翻译东西”等翻译任务意图时，不会直接切换 UI；
- `interrupt()` 暂停 Workspace Graph，并向用户请求确认；
- 用户回复“确定”后，使用同一个 LangGraph thread 恢复执行并产生 `open_translation` UI command；
- Qt Controller 是 UI Tool 的确定性执行器，LangGraph 本身不直接操作 QWidget；
- 翻译界面底部保留紧凑 Agent Dock，因此翻译任务进行期间仍可继续多轮 AI 对话；
- Dock 中的普通 AI 问题会携带当前最新原文和译文作为 ChatContext；
- 用户说“翻译完了 / 结束翻译”等结束意图后，Graph 产生 `return_to_chat`，恢复同一个 SQLite 会话的完整 Chat 页面。

### 3. Agent Tool Graph

```text
User message
    |
Tool intent classification
    |
    +---------------- Document ----------------+
    | open_file / read_document                |
    | extract_document_text / search_document  |
    | summarize_document                       |
    +------------------------------------------+
    |
    +------------------- Web ------------------+
    | web_search / web_read                    |
    +------------------------------------------+
    |
AgentToolRegistry.invoke()
    |
Tool Observation
    |
ChatRequest.tool_context
    |
LLM grounded answer
```

`app/agent/tool_runtime.py` 与 `app/agent/tools/` 提供统一 Tool Registry：

- `open_file`：打开 PDF、DOCX、TXT 或 Markdown；没有路径时由 Qt Controller 打开系统文件选择器；
- `read_document`：读取当前文档的有界文本片段；
- `extract_document_text`：提取当前文档正文，设置最大文本边界；
- `search_document`：在当前文档片段中检索关键词并返回带位置标签的证据；
- `summarize_document`：确定性准备摘要证据，再交给 LLM 做推理总结；
- `web_search`：通过公开搜索页面检索 Web 结果；
- `web_read`：读取公开网页正文，并阻止 localhost、私网、保留地址等潜在 SSRF 目标。

PDF/DOCX 解析、文档检索、Web Search 和 Web Read 都通过现有 QThreadPool 在 GUI 线程之外执行。Tool Observation 被单独放入 `ChatRequest.tool_context`，系统提示明确把文档/网页内容视为不可信数据，从而降低网页或文档中的 prompt injection 影响。当前打开文档只保存在进程内存，不会自动把本地文件正文写入 SQLite 会话数据库。

这种模式属于 Human-in-the-loop、Intent Routing、Tool Routing、UI Tool Orchestration 与 Stateful Multi-turn Workflow 的组合。SQLite 负责长期会话历史；LangGraph checkpointer 负责当前进程内可暂停/恢复的短期 Workspace 状态；Qt Controller 负责实际 UI 副作用、请求版本控制和取消操作。

## Agent Tool examples

```text
用户：打开文档
Agent：弹出文件选择器 -> open_file

用户：总结这个文档
Agent：summarize_document -> Tool Observation -> LLM 总结

用户：在文档里搜索 Safety Gate
Agent：search_document("Safety Gate") -> LLM 基于匹配片段回答

用户：联网搜索 LangGraph ToolNode 最新资料
Agent：web_search("LangGraph ToolNode 最新资料") -> LLM 综合搜索结果回答

用户：读取网页 https://example.com/article
Agent：web_read(url) -> LLM 基于网页正文回答
```

## DeepSeek / OpenAI-compatible AI

Install dependencies:

```powershell
python -m pip install -e "."
```

Configure the API key temporarily:

```powershell
$env:DEEPSEEK_API_KEY="your_api_key"
```

Run the smoke test:

```powershell
python scripts/deepseek_smoke_test.py
```

The API key is intentionally not stored in the normal application configuration file.

## 欢迎使用

欢迎使用 AITranslator。希望它能让你的阅读、学习和工作更加顺畅。

## 改进建议

欢迎其他 GitHub 用户提出改进意见、报告问题或提交 Pull Request。

## Development environment

The supported baseline is Python 3.11. Create and activate an isolated virtual
environment from PowerShell:

```powershell
python -m venv AITranslator
.\AITranslator\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If PowerShell blocks activation for the current session, use:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Run

```powershell
python -m app.main
```
