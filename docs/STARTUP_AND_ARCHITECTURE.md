# AITranslator 启动与前后端设计

这份说明对应当前 `WebReBuild` 代码：FastAPI 负责本地业务能力，React/Vite 负责工作区 UI，Tauri 负责 Windows 桌面窗口和翻译 Overlay。

## 一条命令启动

在仓库根目录执行：

```powershell
.\scripts\start.ps1
```

默认行为：

1. 使用 Conda 环境 `aitrans`；
2. 检查 Python 3.11/3.12、FastAPI 后端依赖、Node.js、前端依赖和 Rust；
3. 仅在依赖缺失时执行 `pip install -e ".[dev]"` 或 `npm ci`；
4. 启动 `http://127.0.0.1:8766` 的 FastAPI；
5. 等待 `/health` 返回成功后启动 Tauri 桌面前端；
6. Tauri 根据 `apps/desktop/src-tauri/tauri.conf.json` 自动拉起 Vite。

日常只启动浏览器版前端时：

```powershell
.\scripts\start.ps1 -Mode Web -OpenBrowser
```

只启动后端时：

```powershell
.\scripts\start.ps1 -Mode Backend
```

如果依赖已经准备好，希望启动过程完全不修改环境：

```powershell
.\scripts\start.ps1 -SkipInstall
```

已有后端在运行时，脚本会复用通过 `/health` 检查的实例，不会重复占用 8766 端口。关闭脚本创建的对应 PowerShell 窗口即可停止服务。

## 后端设计

### 分层

```text
backend/main.py                  FastAPI 应用、CORS、生命周期
        │
        ├── backend/api/           HTTP/WebSocket 路由与请求校验
        ├── backend/models/        Pydantic 请求/响应模型
        ├── backend/services/      翻译、阅读、对话、研究笔记、Agent 服务
        └── config/*.sqlite3       本地状态、缓存和研究数据
```

后端只监听 loopback 地址 `127.0.0.1`。它是桌面端的本地业务边界，不承担公网部署、用户登录或跨用户数据隔离。Web 开发模式允许 `localhost`/`127.0.0.1` 的任意 Vite 端口，避免切换端口后出现误导性的 CORS 错误。

### API 内容

| 能力 | 路由 | 前端页面 |
| --- | --- | --- |
| 存活检查 | `GET /health` | 顶部系统状态 |
| 翻译 | `GET/POST /api/translation/*` | Translation |
| 浏览器上下文 | `GET /api/browser/*` | Translation、Reading |
| 统一阅读选区 | `GET /api/reading/selection` | Translation、Reading、Chat |
| 原生 Overlay | `/api/overlay/*` | Tauri Overlay |
| 快捷 AI 动作 | `/api/quick-actions/*` | Reading、Chat |
| 研究笔记 | `/api/research/*` | Research |
| Companion Chat | `/api/companion/*`、流式接口 | Chat |
| 对话历史 | `/api/conversations/*` | Chat 历史面板 |
| Agent 工具 | `/api/agent/*` | Chat / Agent 工作区 |

每一层的职责保持单向：路由只做协议适配，服务层做业务规则，SQLite/本地文件只由服务层访问。这样可以让 UI 在不复制业务逻辑的情况下切换为 Tauri、浏览器开发模式或后续的原生窗口。

### 生命周期与数据边界

- FastAPI lifespan 启动 Browser Selection Bridge，并在退出时关闭服务和连接；
- Translation、Quick Actions、Companion、Research Notes 和 Conversation Store 通过依赖工厂按需创建；
- Research Notes 与 Chat History 分库存储，避免删除聊天时误删研究证据；
- 浏览器桥只监听 `127.0.0.1`，页面状态接口不主动暴露完整正文；
- 网页、PDF 和文档内容作为不可信参考上下文传入 Agent，不作为系统指令执行。

## 前端设计

### 信息架构

```text
WindowFrame
└── WorkspaceShell
    ├── WorkspaceHeader / backend + browser status
    ├── Translation       输入、语言、Provider、翻译结果
    ├── Reading           当前选区、来源、上下文、快捷动作
    ├── AI Chat            General / Reading-grounded 对话、历史、流式输出
    ├── Research           Source → Section → Notes 证据库
    └── Settings           Provider、Overlay、桌面交互偏好

overlay.html
└── OverlayView           原生划词翻译悬浮窗与 Compact Chat
```

主窗口入口是 `apps/desktop/src/main.tsx`，使用 `HashRouter` 和 React Query；`overlay.html` 是独立 Vite 输入，不把 Overlay 的首屏负载混进主工作区。

### 视觉方向

前端采用“深墨色工作台 + 纸张阅读面”的安静实验室风格：

- 左侧深色导航用于稳定定位，当前工作区用低对比度高亮表示；
- 右侧内容区使用半透明白色面板，适合长文本和研究证据阅读；
- Translation 采用左右双栏，输入与结果在同一视线内完成；
- Reading 先呈现来源身份，再呈现选区和上下文，降低 AI 答案脱离原文的风险；
- Chat 将上下文固定在侧栏，消息区只负责推理过程，输入区固定在底部；
- Research 以来源为一级对象，Section 和 Note 是其下的证据层级；
- 页面切换、流式输出、选区更新和 Overlay 状态变化使用短时、可中断的动效，并尊重 `prefers-reduced-motion`。

### 前端状态边界

| 状态 | 归属 | 说明 |
| --- | --- | --- |
| API 查询、轮询、缓存 | React Query | health、browser、research、conversation |
| 当前翻译输入与语言 | Translation workspace hook | 只影响 Translation/Overlay 相关交互 |
| 当前会话、流式消息 | Companion runtime | 由后端 conversation ID 作为最终依据 |
| Overlay 几何与 Tauri IPC | `src/desktop` | 浏览器开发模式使用安全 fallback |
| 研究笔记持久化 | FastAPI + SQLite | 前端只提交确定性 Save/Edit/Delete 操作 |

前端组件不直接读 SQLite，也不在浏览器端拼接 Agent 规则。用户可见的错误、后端离线状态和流式取消状态都由统一 UI 组件呈现，确保桌面窗口和 Web 开发模式行为一致。

## 目录与演进建议

- 新增后端能力：`backend/models` → `backend/services` → `backend/api` → `apps/desktop/src/api` → 对应 feature 页面；
- 新增页面：先加入 `workspace-navigation.ts`，再在 `App.tsx` 用 `lazy` 路由接入；
- 新增可复用控件：优先放进 `src/shared/ui` 或 `src/shared/components`，不要把 API 调用写进通用按钮；
- 新增桌面能力：放进 `src/desktop`，并为浏览器模式提供 no-op 或降级适配器；
- 每次改动至少验证 `python -m pytest -q --ignore=tests/manual`、`npm run test` 和 `npm run build`。
