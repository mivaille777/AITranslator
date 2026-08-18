# AITranslator

AITranslator 是一款面向 Windows 的桌面划词翻译与 AI 阅读助手。项目在传统桌面翻译基础上逐步演进为一个由 LangGraph 编排的轻量 AI Agent：用户可以划词翻译、手动编辑原文实时翻译，也可以围绕当前阅读上下文进入多轮 AI 对话。

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
- 支持托盘运行、设置管理和翻译结果缓存。
- 使用 Google Translate 网页翻译服务，无需配置 Google Cloud 凭据。

## LangGraph Agent architecture

AITranslator 使用 LangGraph 作为应用层任务编排框架，而不是把 LangGraph 仅作为模型调用包装器。当前架构分成两个图层。

### 1. Execution Graph

```text
START
  |
prepare
  |
  +-------------------+
  |                   |
translation         chat
  |                   |
Google/Web         LLM stream
translation        custom token stream
  |                   |
  +--------- END ------+
```

`app/agent/workflow.py` 定义共享 `AgentWorkflowState` 和 `AITranslatorAgentGraph`：

- `translation` 节点负责确定性的翻译执行；
- `chat` 节点负责上下文对话和模型流式生成；
- Chat token 通过 LangGraph `custom` stream 输出，再由 Qt Signal 增量渲染到悬浮窗。

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

这种模式属于 Human-in-the-loop、Intent Routing、UI Tool Orchestration 与 Stateful Multi-turn Workflow 的组合。SQLite 负责长期会话历史；LangGraph checkpointer 负责当前进程内可暂停/恢复的短期 Workspace 状态；Qt Controller 负责实际 UI 副作用、请求版本控制和取消操作。

这种分层使后续增加 RAG、工具调用、网页/文档检索、任务规划或多 Agent 节点时，可以复用同一个“Agent 提议 → 用户批准 → Workspace Tool → 子任务 → 返回主会话”模式，而无需重写悬浮窗和底层 Provider。

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
