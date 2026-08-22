# AITranslator

AITranslator 是一款面向 Windows 的 **桌面划词翻译、上下文阅读与科研辅助 Agent**。项目已经从传统悬浮翻译工具逐步演进为一个轻量的 Personal Academic Companion：用户可以在浏览器、PDF、Word 和其他 Windows 应用中划词，快速完成翻译、解释、总结、上下文分析与研究笔记沉淀，并围绕当前阅读材料继续多轮 AI 对话。

当前主要开发分支：`LLM_API_Calling`。

## 核心能力

### 1. Zero-keyboard Selection Capture

自动鼠标划词路径不再依赖模拟 `Ctrl+C / Ctrl+V`。

当前自动选区链路：

```text
Browser DOM Selection Bridge
        ↓ fallback
Browser / PDF UIA retry
        ↓ fallback
Word COM / Windows UI Automation
        ↓
Translation + Reading Context
```

- 普通 Chrome / Edge 网页优先通过浏览器扩展直接读取 `window.getSelection()`。
- Word 优先通过 COM 读取当前 Selection。
- Chrome / Edge 内置 PDF Viewer 通过专门的 Browser/PDF UIA retry provider 获取 TextPattern / TextPattern2 selection。
- 其他 Windows 应用通过 UI Automation 获取选区。
- 自动划词生产路径保证不注入 synthetic `Ctrl+C`、不模拟 `Ctrl+V`、不修改系统剪贴板。
- 兼容路径仍保留 `Alt+Q` 和显式 Clipboard fallback，用于手动触发场景。

### 2. Browser Selection Bridge & Reading Context

浏览器扩展位于：

```text
browser_extension/aitrans_selection_bridge/
```

扩展会把当前网页的结构化阅读信息发送到仅监听 `127.0.0.1` 的本地 Bridge：

```text
selected text
page URL
page title
section heading
context before
context after
frame URL
```

AI Chat 顶部会显示 **Reading Context Card**，让用户明确知道 Agent 当前基于哪篇网页 / PDF、哪一节和哪一段文本回答。

Reading Context 会随以下事件更新：

- 切换浏览器 Tab / 页面；
- 打开新的本地 PDF；
- 在当前页面重新划词；
- 切换 AI Chat 会话；
- 从 Browser / PDF / Word / Desktop selection 切换到新的阅读来源。

浏览器 Bridge 只绑定 loopback 地址，不监听局域网接口；页面状态 API 不暴露选中的正文内容。

### 3. Translation Overlay

- 自动划词翻译默认开启。
- 支持 `Alt+Q` 手动触发翻译；系统 `Ctrl+C` 保持原生复制语义。
- 支持直接编辑原文，停顿后自动翻译，`Ctrl+Enter` 可立即翻译。
- 支持源语言、目标语言独立切换和互换；目标语言不会出现 `Auto`。
- Auto 检测后显示实际检测语言，例如 `EN·Auto`。
- 支持拖动、边缘/四角缩放、置顶、锁定、隐藏、恢复和多屏定位。
- 生产 Overlay 已取消早期 `900 × 520` 固定最大尺寸限制，由当前屏幕可用区域作为实际几何边界。
- 正文透明度与 GUI Chrome 层分离，浅色网页 / 白色 PDF 背景下顶部按钮、Chat Toolbar 和操作控件仍保持可读。

### 4. Context-aware Quick Actions

划词翻译后可以直接使用高频阅读动作：

```text
[译] [解释] [总结] [笔记]
```

对应：

- 结合上下文翻译；
- 解释这段；
- 总结这段；
- 加入研究笔记。

完整 AI 菜单还提供：

- AI 翻译；
- AI 润色；
- 分析段落作用；
- 研究笔记库；
- 最近研究笔记。

Reading Actions 直接使用当前 `ReadingContext`，不会重新复制文本，也不会经过 Workspace Tool Planner 误判成 UI 切换请求。

### 5. AI Chat

AI Chat 支持：

- 多轮对话与 SQLite 会话持久化；
- DeepSeek / OpenAI-compatible 模型切换；
- 流式 token 输出；
- 停止生成；
- 单条回复复制与重新生成；
- 历史会话搜索、重命名、删除和切换；
- Reading Context Card；
- 独立 Chat 字体大小选择；
- 输入框随多行输入自适应高度；
- 长回答自动增长，超过可用区域后内部滚动；
- 用户上翻时停止自动追尾，并显示 `↓` 跳转到最新内容按钮；
- AI 回复结束后执行 final transcript reflow，修复 Markdown 长回答末尾被裁切的问题；
- AI 回复中的 `http://` / `https://` 链接支持 `Ctrl + 点击`，点击后先让用户选择浏览器，再打开链接。

Chat resize 与 Translation typography 已隔离：调整 AI Chat 窗口或 Chat 字号不会污染翻译页字号和布局。

### 6. Research Notes / Research Memory

Research Notes 使用独立的本地 SQLite 数据层，与聊天历史分离。

一条 Research Note 可以保存：

```text
文献标题
URL
Section
原文
译文
前后文 Reading Context
AI 阅读结果
AI Action 类型
用户笔记
关联 Conversation
创建 / 更新时间
```

支持：

- 一键加入研究笔记；
- 同一选区 Upsert，避免重复笔记；
- Research Notes Library；
- 搜索；
- 浏览完整笔记；
- 编辑“我的笔记”；
- 删除；
- 打开来源；
- 最近研究笔记快速查看。

保存、读取、编辑和删除研究笔记均为本地确定性操作，不调用 LLM。

## GUI 架构

当前界面按三层组织：

```text
Selection Surface
├─ Translation Overlay
├─ Quick Actions
└─ Toast feedback

Agent Surface
├─ AI Chat
├─ Reading Context Card
├─ Conversation History
└─ Model / Font / Scroll controls

Research Surface
├─ Research Notes Library
├─ Search / Edit / Delete
└─ Source navigation
```

设置页已经从单个长表单重构为：

```text
基础
AI 模型
划词与阅读
浏览器集成
外观
研究数据
高级
```

`浏览器集成` 页面可以查看 Browser Selection Bridge 是否运行、是否检测到扩展活动以及最近页面；`研究数据` 页面可以查看研究笔记数量、数据库位置并直接打开 Research Notes Library。

## LangGraph Agent Architecture

AITranslator 使用 LangGraph 作为应用层任务编排框架，而不是模型调用包装器。

### Chat Execution Graph

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

`app/agent/workflow.py` 提供共享 Chat 执行图。Qt worker 在后台运行 Graph，token 通过 Qt Signal 增量渲染到悬浮窗。

普通翻译仍保持确定性的：

```text
TranslationTask
→ TranslationManager
→ Provider
```

LangGraph 负责 Agent 决策和工作流，而不是替代稳定的翻译 Provider 执行层。

### Workspace Agent Graph

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
```

翻译界面被视为 Agent 可以申请使用的 Workspace Capability。Qt Controller 是 UI Tool 的确定性执行器，LangGraph 不直接操作 QWidget。

### Agent Tool Graph

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
LLM grounded answer
```

Document / Web 内容作为 `Tool Observation` 注入 Chat，系统提示明确将网页、文档和 Reading Context 视为参考数据而不是可执行指令。

## Browser Extension 安装

Chrome：

```text
chrome://extensions
```

Edge：

```text
edge://extensions
```

开启 Developer mode，然后选择 **Load unpacked / 加载已解压的扩展程序**：

```text
browser_extension/aitrans_selection_bridge
```

如果需要访问普通 `file://` 页面，请在扩展详情中开启 **Allow access to file URLs / 允许访问文件网址**。

浏览器内置 PDF 的主要 fallback 是 Windows UI Automation，因此不依赖 content script 一定能够注入 PDF Viewer。

## DeepSeek / OpenAI-compatible AI

安装依赖：

```powershell
python -m pip install -e ".[dev]"
```

可以临时通过环境变量配置 DeepSeek API Key：

```powershell
$env:DEEPSEEK_API_KEY="your_api_key"
```

API Key 不会写入普通应用配置文件；配置过的 Windows Credential Manager 凭据优先于临时环境变量。

## Development Environment

当前支持基线：

```text
Python >= 3.11, < 3.13
推荐 / 主要验证版本：Python 3.11
PySide6 6.7.3
```

PowerShell：

```powershell
python -m venv AITranslator
.\AITranslator\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

如果 PowerShell 阻止当前会话激活：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Run

推荐使用统一启动入口，它会自动检查 `aitrans` Conda 环境、后端健康状态和前端依赖，然后启动 FastAPI + Tauri：

```powershell
.\scripts\start.ps1
```

浏览器开发模式：

```powershell
.\scripts\start.ps1 -Mode Web -OpenBrowser
```

只启动 FastAPI：

```powershell
.\scripts\start.ps1 -Mode Backend
```

如果使用包含 Git 同步和完整验证的旧入口，并且当前改动已经确认需要保留：

```powershell
.\scripts\verify_and_start.ps1 -AllowLocalChanges
```

该参数会跳过 `git fetch/pull`，不会恢复或覆盖本地改动；默认不传入时仍会阻止 dirty working tree 自动同步。

后端接口、前端工作区和启动链路的设计说明见：

```text
docs/STARTUP_AND_ARCHITECTURE.md
```

如果只运行旧版 PySide6 原生入口，仍可使用：

```powershell
python -m app.main
```

生产入口 smoke test：

```powershell
python -m app.main --smoke-test
```

## Tests

本地测试入口：

```powershell
.\scripts\test.ps1
```

首次安装测试依赖：

```powershell
.\scripts\test.ps1 -Install
```

测试脚本会：

- 检查 Python 3.11；
- 设置 `QT_QPA_PLATFORM=offscreen`；
- 运行完整 pytest；
- 排除 `tests/manual`。

仓库同时提供 **Manual Tests** GitHub Actions 工作流，用于阶段性地在全新 `windows-latest + Python 3.11` Runner 上验证完整 pytest 和应用 smoke test。该工作流默认只通过 `workflow_dispatch` 手动运行，不会因为普通功能代码 push 自动执行。

## 安全与隐私边界

- 自动划词生产路径不模拟 `Ctrl+C / Ctrl+V`。
- Browser Selection Bridge 只监听 `127.0.0.1`。
- Research Notes 与 Chat History 都保存在本地 SQLite。
- Web / Document / Reading Context 被视为不可信参考数据，不作为系统指令执行。
- `web_read` 阻止 localhost、私网和保留地址等潜在 SSRF 目标。
- AI 回复链接只允许 `http://` 和 `https://`，且必须由用户 `Ctrl + 点击` 后主动选择浏览器打开。
- 不要把 API Key、访问令牌或敏感原文提交到 GitHub Issue / 日志。

## 当前方向

AITranslator 的长期目标不是单纯“帮用户调用翻译工具”，而是围绕科研阅读形成连续工作流：

```text
Read
→ Understand
→ Translate
→ Discuss
→ Save
→ Retrieve
→ Reuse
```

当前已经完成 Selection、Reading Context、Context-aware Actions、Research Notes 和基础 Research Memory，后续将继续围绕文献搜索、研究笔记检索与 Personal Research Knowledge 扩展。

## 反馈与贡献

欢迎通过 GitHub Issue 报告问题、提出改进建议或提交 Pull Request。反馈 GUI / Selection 问题时，建议附上：

- Windows 与浏览器版本；
- 使用场景（网页 / PDF / Word / 其他应用）；
- 复现步骤；
- 不包含敏感原文的日志片段。
