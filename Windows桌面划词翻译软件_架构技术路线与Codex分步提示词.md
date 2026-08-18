# Windows 桌面划词翻译 Overlay 软件：整体架构、技术路线与 Codex 分步开发提示词

> 目标平台：Windows 10 / Windows 11  
> 主语言：Python  
> 目标功能：用户在 Word、浏览器、PDF 阅读器、IDE 等应用中选中文字后，通过快捷键或自动划词触发翻译，调用 Google Cloud Translation API，并将译文以类似 QQ 音乐桌面歌词的透明置顶 Overlay 形式显示。  
> 开发原则：**先做稳定闭环，再做自动化；先保证可测试，再增加兼容性；每一步都必须能够独立运行和验收。**

---

## 1. 软件目标与范围

### 1.1 MVP 目标

第一版必须完成以下闭环：

```text
用户在任意应用中选中文字
        ↓
按下全局快捷键（例如 Alt+Q）
        ↓
程序获取当前选中文本
        ↓
调用 Google Cloud Translation
        ↓
获取译文
        ↓
透明、无边框、始终置顶 Overlay 显示译文
        ↓
用户仍可继续操作原应用
```

MVP 不要求一开始实现“鼠标一松开就自动翻译”。

优先确保：

1. Word 可用；
2. Chrome / Edge 网页可用；
3. 普通文本编辑器可用；
4. 翻译请求不会阻塞 GUI；
5. Overlay 不抢焦点；
6. Overlay 可以锁定为鼠标穿透；
7. 程序可以从系统托盘控制；
8. 错误不会导致主程序崩溃。

---

## 2. 总体技术路线

推荐技术栈：

| 层 | 技术 | 用途 |
|---|---|---|
| Python | Python 3.11 或 3.12 | 主语言 |
| GUI | PySide6 / Qt 6 | Overlay、设置页、托盘 |
| Windows API | pywin32 + ctypes | TopMost、窗口样式、焦点、前台窗口 |
| 全局快捷键 | pynput 或 keyboard | Alt+Q 等全局触发 |
| 剪贴板 | pywin32 / Qt Clipboard | 通用选中文本读取 |
| Word 专用 | pywin32 COM | `Word.Application.Selection` |
| Windows UIA | pywinauto / UI Automation | 后续高级选区读取 |
| 翻译服务 | google-cloud-translate | Google Cloud Translation |
| 并发 | QThreadPool + QRunnable | 网络请求异步化 |
| 缓存 | cachetools + SQLite | 内存缓存 + 持久缓存 |
| 配置 | TOML 或 JSON | 用户配置 |
| 凭据 | keyring / 环境变量 | API 凭据 |
| 日志 | logging | 调试、错误记录 |
| 测试 | pytest + pytest-qt | 单元测试、GUI 测试 |
| Mock | unittest.mock / pytest monkeypatch | 模拟 Google API、系统 API |
| 打包 | PyInstaller | Windows exe |
| 安装包 | Inno Setup（可选） | 正式安装程序 |

---

## 3. 总体软件架构

采用分层、事件驱动架构。

```text
┌──────────────────────────────────────────────────────┐
│                    Desktop Apps                      │
│ Word / Chrome / Edge / PDF / VS Code / Notepad ... │
└─────────────────────────┬────────────────────────────┘
                          │
                          │ 用户选中文字
                          ▼
┌──────────────────────────────────────────────────────┐
│                    Input Layer                       │
│                                                      │
│ GlobalHotkeyManager                                  │
│ MouseListener                                        │
│ ForegroundWindowDetector                             │
└─────────────────────────┬────────────────────────────┘
                          │ TriggerEvent
                          ▼
┌──────────────────────────────────────────────────────┐
│                 Selection Layer                      │
│                                                      │
│ SelectionManager                                     │
│   ├─ WordSelectionProvider                           │
│   ├─ UIASelectionProvider                            │
│   └─ ClipboardSelectionProvider                      │
└─────────────────────────┬────────────────────────────┘
                          │ SelectedText
                          ▼
┌──────────────────────────────────────────────────────┐
│                Translation Layer                     │
│                                                      │
│ TranslationManager                                   │
│   ├─ TextNormalizer                                  │
│   ├─ RequestDeduplicator                             │
│   ├─ TranslationCache                                │
│   ├─ GoogleTranslationProvider                       │
│   └─ RequestVersionController                        │
└─────────────────────────┬────────────────────────────┘
                          │ TranslationResult
                          ▼
┌──────────────────────────────────────────────────────┐
│                   Overlay Layer                      │
│                                                      │
│ OverlayManager                                       │
│   ├─ OverlayWindow                                   │
│   ├─ PositionManager                                 │
│   ├─ StyleManager                                    │
│   └─ Win32OverlayAdapter                             │
└─────────────────────────┬────────────────────────────┘
                          │
                          ▼
                 屏幕透明悬浮译文

┌──────────────────────────────────────────────────────┐
│                 Application Layer                    │
│                                                      │
│ AppController                                        │
│ TrayManager                                          │
│ SettingsManager                                      │
│ Logger                                               │
│ ErrorBus                                             │
└──────────────────────────────────────────────────────┘
```

---

## 4. 推荐项目目录

```text
desktop_translator/
│
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ controller.py
│  │
│  ├─ input/
│  │  ├─ hotkey_manager.py
│  │  ├─ mouse_listener.py
│  │  └─ foreground_window.py
│  │
│  ├─ selection/
│  │  ├─ base.py
│  │  ├─ manager.py
│  │  ├─ clipboard_provider.py
│  │  ├─ word_provider.py
│  │  └─ uia_provider.py
│  │
│  ├─ translation/
│  │  ├─ base.py
│  │  ├─ manager.py
│  │  ├─ google_provider.py
│  │  ├─ cache.py
│  │  ├─ normalizer.py
│  │  └─ request_guard.py
│  │
│  ├─ overlay/
│  │  ├─ window.py
│  │  ├─ manager.py
│  │  ├─ positioning.py
│  │  └─ win32_adapter.py
│  │
│  ├─ ui/
│  │  ├─ tray.py
│  │  └─ settings_window.py
│  │
│  ├─ infrastructure/
│  │  ├─ config.py
│  │  ├─ logging.py
│  │  ├─ credentials.py
│  │  └─ errors.py
│  │
│  └─ models/
│     ├─ selection.py
│     ├─ translation.py
│     └─ events.py
│
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ gui/
│  └─ manual/
│
├─ scripts/
│  ├─ smoke_test.py
│  └─ verify_environment.py
│
├─ config/
│  └─ default.toml
│
├─ logs/
├─ pyproject.toml
├─ README.md
└─ .gitignore
```

---

# 5. 核心设计原则

## 5.1 Selection 与 Translation 解耦

`SelectionManager` 只负责回答：

```text
“当前用户选中了什么文本？”
```

它不应该知道：

- Google API；
- Overlay；
- 目标语言；
- GUI；
- 缓存。

---

## 5.2 Translation 与 Overlay 解耦

Translation 层只接收：

```text
source_text
source_language
target_language
request_id
```

输出：

```text
TranslationResult
```

它不应该直接操作窗口。

---

## 5.3 所有网络请求必须异步

禁止：

```text
GUI 主线程
    ↓
Google API
    ↓
等待网络
```

必须：

```text
GUI
 ↓
任务队列
 ↓
Worker Thread
 ↓
Google API
 ↓
Signal
 ↓
GUI 更新
```

---

## 5.4 必须处理过期翻译结果

例如：

```text
Request 101 = A
Request 102 = B
Request 103 = C
```

即使返回顺序是：

```text
103 → 102 → 101
```

界面最终也只能显示：

```text
C 的译文
```

因此必须设计：

```text
request_id
latest_request_id
```

旧请求返回时直接丢弃。

---

## 5.5 自动划词必须有 Debounce

自动模式不得在每次鼠标变化时调用翻译。

推荐：

```text
MouseUp
 ↓
200~300 ms debounce
 ↓
读取 Selection
 ↓
文本有效？
 ↓
文本与上次不同？
 ↓
Translate
```

---

# 6. Selection Provider 策略

最终推荐顺序：

```text
SelectionManager
       │
       ├─ 如果前台应用是 Word
       │       ↓
       │   Word COM Provider
       │
       ├─ 否则尝试
       │       ↓
       │   UI Automation Provider
       │
       └─ 失败后
               ↓
         Clipboard Provider
```

MVP 初期可以只实现：

```text
Clipboard Provider
```

第二阶段增加：

```text
Word COM
```

第三阶段再实现：

```text
UI Automation
```

---

# 7. Clipboard 获取策略

Clipboard Provider 的工作流程：

```text
保存当前剪贴板
      ↓
向前台应用发送 Ctrl+C
      ↓
短暂等待
      ↓
读取新剪贴板
      ↓
校验是否为文本
      ↓
恢复用户原剪贴板
      ↓
返回 SelectedText
```

需要重点测试：

1. 原剪贴板内容不会被永久覆盖；
2. 空选区不会错误读取历史剪贴板；
3. Ctrl+C 没有效果时能够超时退出；
4. 不要无限等待剪贴板；
5. 多次触发时不会互相覆盖状态。

---

# 8. Overlay 设计

Overlay 必须支持两种状态。

## 8.1 解锁状态

用于：

- 拖动；
- 调整位置；
- 修改字体；
- 设置透明度。

```text
ClickThrough = False
```

## 8.2 锁定状态

用于正常阅读。

```text
ClickThrough = True
TopMost = True
NoActivate = True
```

此时鼠标点击应该穿过 Overlay 操作下面的 Word / 浏览器。

---

# 9. Overlay 显示模式

至少设计两种：

### 模式 A：桌面歌词模式

固定在：

```text
顶部
中上
中部
中下
底部
```

推荐作为默认模式。

### 模式 B：鼠标附近模式

使用当前鼠标坐标：

```text
overlay_x = mouse_x + offset
overlay_y = mouse_y + offset
```

同时必须做屏幕边界检测，避免窗口跑出屏幕。

---

# 10. Translation Manager 数据流

```text
SelectedText
     ↓
TextNormalizer
     ↓
Empty Check
     ↓
Duplicate Check
     ↓
Cache Lookup
   ↙       ↘
 Hit       Miss
 ↓          ↓
返回      Worker Thread
           ↓
        Google API
           ↓
        Result
           ↓
      Request Guard
           ↓
       Cache Store
           ↓
      TranslationResult
```

---

# 11. 缓存策略

## L1：内存 LRU Cache

Key：

```text
(source_lang, target_lang, normalized_text)
```

优点：

- 极快；
- 同一会话重复划词无需请求 API。

## L2：SQLite Cache

用于：

- 软件重启后复用；
- 降低 Google API 调用次数；
- 后续提供历史翻译。

MVP 可以先只有 L1。

---

# 12. 错误处理策略

所有错误必须转成统一错误对象。

建议分类：

```text
SelectionError
TranslationError
NetworkError
CredentialError
OverlayError
ConfigurationError
```

禁止业务层直接弹系统异常堆栈。

用户界面只显示可理解信息，例如：

```text
未检测到选中文本
网络连接失败
Google Translation 凭据无效
翻译请求超时
```

完整异常写日志。

---

# 13. 日志设计

开发阶段建议：

```text
DEBUG
INFO
WARNING
ERROR
```

至少记录：

```text
应用启动
快捷键触发
前台应用名称
Selection Provider
文本长度
request_id
cache hit / miss
API 请求耗时
API 成功 / 失败
Overlay 更新
异常
```

注意：

默认日志不要完整记录用户选中的敏感文本。

推荐只记录：

```text
text_length
text_hash
```

---

# 14. 推荐状态机

```text
IDLE
 │
 │ Trigger
 ▼
CAPTURING
 │
 ├─ failed → IDLE
 │
 ▼
TRANSLATING
 │
 ├─ cached → DISPLAYING
 │
 ├─ error  → ERROR → IDLE
 │
 ▼
DISPLAYING
 │
 │ next trigger
 ▼
CAPTURING
```

自动模式增加：

```text
WAITING_DEBOUNCE
```

---

# 15. 测试体系

必须同时拥有四类测试。

## 15.1 Unit Test

测试单模块：

```text
TextNormalizer
Cache
RequestGuard
Config
Provider fallback
Position calculation
```

## 15.2 Integration Test

测试链路：

```text
Fake Selection
    ↓
Fake Translation
    ↓
Overlay Manager
```

以及：

```text
Clipboard
    ↓
Selection Manager
```

## 15.3 GUI Test

使用 `pytest-qt`：

```text
Overlay show / hide
text update
lock / unlock
position
style
```

## 15.4 Manual Acceptance Test

真实测试：

```text
Word
Chrome
Edge
Notepad
PDF Reader
VS Code
```

---

# 16. Codex 总体工作规则

建议在每个 Codex 提示词开头都包含以下约束：

```text
你正在开发一个 Windows Python 桌面划词翻译软件。

请严格遵守：

1. 不要跨越本步骤范围实现后续功能。
2. 修改前先检查当前仓库结构和已有代码。
3. 优先复用已有实现，不创建重复模块。
4. 所有新增核心逻辑必须有 pytest 测试。
5. Windows 特定 API 必须封装，不允许散落在业务代码中。
6. Google API 必须支持 mock，自动测试不得真实消耗 API 配额。
7. GUI 主线程不得执行网络请求。
8. 所有异常必须被捕获并转换为项目统一异常类型。
9. 完成本步骤后必须运行测试。
10. 测试不通过时继续修复，直到通过。
11. 不要在本步骤完成前开始下一阶段。
12. 最后输出：
   - 修改了哪些文件；
   - 设计说明；
   - 执行了哪些测试；
   - 测试结果；
   - 仍存在的限制。
```

---

# 17. 分阶段 Codex 开发提示词

---

## Step 0：初始化工程与开发环境

### 目标

建立一个：

```text
可安装
可启动
可测试
可持续扩展
```

的 Python 项目骨架。

### 给 Codex 的提示词

```text
请初始化本项目的 Python 工程结构。

目标平台：
Windows 10 / Windows 11。

Python：
3.11 或 3.12。

技术栈：
PySide6
pywin32
pynput
google-cloud-translate
cachetools
pytest
pytest-qt

本步骤只完成：

1. 建立 app、tests、config、scripts 等目录。
2. 配置 pyproject.toml。
3. 创建最小 QApplication 启动入口。
4. 创建统一日志初始化模块。
5. 创建默认配置文件。
6. 创建 verify_environment 脚本。
7. 创建 pytest 基础配置。
8. 添加 README 中的开发环境启动说明。

暂时不要实现：
Selection
Google API
Overlay
全局快捷键
鼠标监听

验收要求：

A. 安装依赖成功。
B. python -m app.main 可以正常启动并退出。
C. pytest 可以执行。
D. verify_environment 能输出：
   Python 版本
   Windows 版本
   PySide6 可导入
   pywin32 可导入
   google-cloud-translate 可导入
E. 所有测试通过。

完成后给出修改文件列表和测试结果。
```

### 自动验证

```text
pytest
python -m app.main
python scripts/verify_environment.py
```

### 通过标准

- QApplication 可启动；
- 无 ImportError；
- pytest 基础测试通过；
- 目录结构固定。

---

## Step 1：实现基础 Overlay 窗口

### 目标

先完全不考虑翻译。

只验证：

> Python 能否显示一个类似 QQ 音乐歌词的透明置顶窗口。

### 给 Codex 的提示词

```text
请实现 Overlay 基础窗口。

本步骤只实现显示层，不接入 Selection 和 Translation。

要求：

1. 使用 PySide6。
2. 创建 OverlayWindow。
3. 无系统标题栏。
4. 支持透明背景。
5. 窗口保持 TopMost。
6. 默认显示测试文本：
   “Overlay test / 悬浮翻译测试”
7. 提供：
   show_text(text)
   hide_overlay()
   show_overlay()
8. 窗口支持自动根据文本调整尺寸。
9. 文字支持自动换行。
10. 多显示器环境下不能因为非法坐标导致异常。
11. Windows 特定行为通过单独 Win32OverlayAdapter 封装。

本步骤不要实现：
鼠标穿透
全局快捷键
翻译
剪贴板
自动划词

请增加 pytest / pytest-qt 测试：

- OverlayWindow 可以创建。
- show_text 后文本发生变化。
- hide/show 状态正确。
- 空文本不会导致异常。
- 超长文本可以显示。

最终提供一个 manual overlay demo 入口用于人工查看。

完成后运行全部测试。
```

### 手工验收

运行 Demo，打开 Word。

必须看到：

```text
Word
+
悬浮测试文字
```

然后切换：

```text
Word
Chrome
Explorer
```

Overlay 仍在最上层。

### 通过标准

- 无边框；
- 透明；
- TopMost；
- 文本清晰；
- 切换应用不消失；
- 测试通过。

---

## Step 2：实现 Overlay 锁定、鼠标穿透和不抢焦点

### 目标

达到 QQ 音乐桌面歌词最重要的窗口行为。

### Codex 提示词

```text
基于现有 OverlayWindow，实现 Windows Overlay 行为增强。

要求：

1. 增加 lock_overlay()。
2. 增加 unlock_overlay()。
3. lock 状态：
   - Always On Top
   - 鼠标穿透
   - 尽可能不激活窗口
   - 不影响下面应用接收鼠标输入
4. unlock 状态：
   - 可被鼠标操作
   - 支持拖动窗口
5. Windows API 逻辑全部放入 Win32OverlayAdapter。
6. 不要把 Win32 常量散落到 GUI 业务逻辑。
7. 状态需要可查询：
   is_locked

自动测试无法完全模拟 Windows 鼠标穿透，因此：

A. 对 Win32OverlayAdapter 使用 mock 做单元测试。
B. 提供 manual_test_overlay_lock.py。
C. 在人工测试脚本中明确输出当前状态。

人工验收步骤：
1. 打开 Notepad。
2. Overlay 放在 Notepad 上方。
3. 锁定 Overlay。
4. 点击 Overlay 所在区域。
5. Notepad 应收到点击。
6. 解锁 Overlay。
7. Overlay 可以拖动。

完成后运行全部自动测试。
```

### 通过标准

人工测试中：

```text
LOCKED
→ 点击穿透

UNLOCKED
→ 可以拖动
```

---

## Step 3：实现系统托盘

### 目标

让应用具备桌面工具基本形态。

### Codex 提示词

```text
实现系统托盘 TrayManager。

功能：

1. 应用启动后显示托盘图标。
2. 菜单包含：
   - 启用翻译
   - 暂停翻译
   - 锁定 Overlay
   - 解锁 Overlay
   - 显示测试字幕
   - 隐藏字幕
   - 退出
3. TrayManager 不直接操作底层窗口。
4. 使用 Qt Signal 或 AppController 协调。
5. 退出必须正确停止 QApplication。

增加 pytest-qt 测试：
- TrayManager 可以创建。
- Action 存在。
- lock/unlock signal 可以触发。
- exit action 可以调用退出逻辑。

暂时不要加入翻译和快捷键。
```

### 通过标准

系统托盘中能控制：

```text
Overlay Show
Overlay Hide
Lock
Unlock
Exit
```

---

## Step 4：实现全局快捷键

### 目标

按：

```text
Alt + Q
```

能够向应用发出：

```text
TranslationTriggerEvent
```

暂时不用翻译。

### Codex 提示词

```text
实现 GlobalHotkeyManager。

默认快捷键：
Alt+Q。

要求：

1. 全局快捷键在 Word、Chrome、Notepad 获得焦点时仍可触发。
2. GlobalHotkeyManager 只负责产生 TriggerEvent。
3. 不允许直接调用 Overlay。
4. 支持 start() / stop()。
5. 应用退出时正确停止 listener。
6. 防止一个按键动作重复产生大量事件。
7. 快捷键配置从 ConfigManager 获取。

测试：
- 使用 mock 模拟按键回调。
- 验证 TriggerEvent 只生成一次。
- start/stop 可重复调用且不会泄漏 listener。
- 非目标组合键不触发。

增加 manual_hotkey_test：
每按一次 Alt+Q，在日志记录：
HOTKEY_TRIGGERED

暂时不要获取 Selection。
```

### 手工验收

分别在：

```text
Word
Chrome
Notepad
```

按 Alt+Q。

日志必须出现：

```text
HOTKEY_TRIGGERED
```

---

## Step 5：实现 Clipboard Selection Provider

### 目标

完成：

```text
用户选中文字
+
Alt+Q
↓
Python 得到 selected_text
```

这是第一个关键里程碑。

### Codex 提示词

```text
实现 Selection 抽象层和 ClipboardSelectionProvider。

需要建立：

SelectionProvider 抽象接口
SelectionManager
ClipboardSelectionProvider
SelectedText 数据模型

Clipboard Provider 的策略：

1. 保存当前剪贴板状态。
2. 向当前前台应用发送 Ctrl+C。
3. 等待剪贴板发生变化，但必须有超时。
4. 获取文本。
5. 验证不是空字符串。
6. 恢复用户原剪贴板。
7. 失败时抛出统一 SelectionError。
8. 不允许无限轮询。
9. 不允许因为异常导致剪贴板不恢复。

重点处理：
- 没有选中文本；
- 剪贴板被其他程序占用；
- Ctrl+C 无效果；
- 原剪贴板为空；
- 原剪贴板为文本；
- 连续触发。

SelectionManager 当前只使用 ClipboardSelectionProvider。

把 GlobalHotkeyManager 接到 SelectionManager。

暂时不要调用 Google Translation。

成功获取文本后：
Overlay 显示：
“Selected: <文本>”

测试要求：

1. Clipboard OS 访问封装为 ClipboardAdapter，方便 mock。
2. Keyboard Ctrl+C 封装为 CopyCommandAdapter。
3. 自动测试不得真实修改用户剪贴板。
4. 测试成功获取文本。
5. 测试空文本。
6. 测试超时。
7. 测试异常后恢复 clipboard。
8. 测试 SelectionManager 正确返回 SelectedText。

完成后运行全部测试。
```

### 手工验收矩阵

| 应用 | 操作 | 结果 |
|---|---|---|
| Notepad | 选英文 + Alt+Q | Overlay 显示 Selected |
| Word | 选英文 + Alt+Q | 成功 |
| Chrome | 网页选英文 + Alt+Q | 成功 |
| Edge | 网页选英文 + Alt+Q | 成功 |
| VS Code | 选代码注释 + Alt+Q | 成功 |

### 通过标准

至少：

```text
Notepad
Word
Chrome
```

全部成功。

---

## Step 6：实现 Google Translation Provider，但先完全 Mock

### 目标

建立 Translation 层，而不是马上连真实 API。

### Codex 提示词

```text
实现 Translation 抽象层。

建立：

TranslationProvider
TranslationManager
TranslationRequest
TranslationResult
TranslationError

建立 GoogleTranslationProvider，但自动测试阶段必须可完全 mock。

TranslationManager 输入：

source_text
source_language
target_language

默认：
source_language = auto
target_language = zh-CN

要求：

1. GUI 不直接知道 Google SDK。
2. Google SDK 只允许存在于 GoogleTranslationProvider。
3. API 返回值转换成统一 TranslationResult。
4. Google SDK 异常转换为 TranslationError。
5. 自动测试不得访问真实网络。
6. 使用 FakeTranslationProvider 测试 TranslationManager。

先将完整流程接通：

Hotkey
 ↓
Selection
 ↓
FakeTranslationProvider
 ↓
Overlay

Fake Translation 可以返回：
“[TEST TRANSLATION] <source text>”

测试：
- TranslationManager success
- provider error
- empty source
- unsupported result
- AppController 完整链路

完成后运行全部测试。
```

### 通过标准

完全断网时：

```text
选中文字
Alt+Q
```

Overlay 能显示：

```text
[TEST TRANSLATION] ...
```

说明软件架构闭环成立。

---

## Step 7：真实接入 Google Cloud Translation

### 目标

将 Fake Provider 替换为真实 Provider。

### Codex 提示词

```text
在现有 TranslationProvider 架构下完成 Google Cloud Translation 真实接入。

要求：

1. 使用官方 Python SDK。
2. 凭据不得硬编码。
3. 优先从标准环境变量 / CredentialManager 获取。
4. 程序启动时不强制请求 Google。
5. 第一次翻译时初始化 client 或使用安全 lazy initialization。
6. 设置网络错误处理。
7. 将所有 Google SDK 异常转换为 TranslationError。
8. 日志不能记录 API 密钥或凭据内容。
9. 自动测试继续全部使用 mock。
10. 增加一个显式 manual_real_google_test.py，只有人工执行时才真实调用 API。
11. 如果没有凭据，程序不能崩溃，应显示 CredentialError。

目标：
英文 → 简体中文。

完成后：
- 运行所有自动测试。
- 明确说明真实 API 测试如何执行。
```

### 手工验收

选中：

```text
The proposed method uses a Gaussian process to guide local search.
```

应该返回合理中文译文。

### 通过标准

```text
Word
 ↓
Alt+Q
 ↓
Google API
 ↓
中文译文
 ↓
Overlay
```

真实链路跑通。

---

## Step 8：异步翻译与防 GUI 卡死

### 目标

将真实 API 完全移出 GUI 主线程。

### Codex 提示词

```text
重构 TranslationManager，使所有真实翻译请求运行于 Qt Worker Thread。

推荐：
QThreadPool
QRunnable
Qt Signal

要求：

1. GUI 主线程不能执行 Google 网络调用。
2. AppController 提交 TranslationTask。
3. Worker 完成后通过 Signal 返回 TranslationResult。
4. Worker 抛出的异常转成失败 Signal。
5. Overlay 只能在 GUI 主线程更新。
6. 连续触发 20 次不能导致程序崩溃。
7. 应用退出时不得因为后台线程无限阻塞。

增加测试：

A. 使用一个人为 sleep 的 FakeSlowProvider。
B. 发起翻译后 GUI event loop 仍可以响应。
C. 验证结果最后通过 signal 返回。
D. 验证 provider 抛异常不会杀死主程序。

增加 manual_async_test：
模拟 1~2 秒 Translation delay，
期间用户必须仍能拖动 Overlay / 操作托盘。
```

### 通过标准

翻译请求等待时：

```text
Overlay
托盘
GUI
```

仍然流畅。

---

## Step 9：Request ID 防止旧结果覆盖新结果

### 目标

解决并发请求乱序问题。

### Codex 提示词

```text
实现 RequestVersionController。

每个翻译请求必须生成单调递增 request_id。

AppController 保存：
latest_request_id

当 worker 返回时：

if result.request_id != latest_request_id:
    discard

只有最新请求结果可以更新 Overlay。

要求：
1. request_id 线程安全。
2. TranslationResult 必须携带 request_id。
3. 旧结果被丢弃时记录 DEBUG 日志。
4. 不要取消线程作为唯一解决方案，因为网络请求可能无法及时取消。

自动测试：

模拟：
request 1 delay = 500ms
request 2 delay = 300ms
request 3 delay = 50ms

返回顺序：
3 → 2 → 1

最终 Overlay 必须保持 request 3 的内容。

该测试必须自动化。
```

### 通过标准

乱序并发测试 100% 通过。

---

## Step 10：加入缓存

### 目标

重复文本不再请求 Google。

### Codex 提示词

```text
实现 TranslationCache。

本阶段只做内存 LRU Cache。

Key：
source_language
target_language
normalized_text

要求：

1. 使用固定最大容量。
2. TranslationManager 请求 Provider 前先检查 cache。
3. Provider 成功后写 cache。
4. Provider 失败不得缓存错误。
5. cache hit 时仍然生成正确 TranslationResult。
6. 日志记录 CACHE_HIT / CACHE_MISS。
7. 配置中允许关闭缓存。

自动测试：

1. 相同文本翻译两次。
2. Fake Provider 调用次数必须为 1。
3. 不同目标语言必须 miss。
4. normalize 后相同文本应命中。
5. 超过容量验证 LRU eviction。
```

### 通过标准

同一句话连续翻译：

```text
第一次：API
第二次：Cache
```

---

## Step 11：实现 Text Normalizer 和输入保护

### 目标

避免垃圾请求。

### Codex 提示词

```text
实现 TextNormalizer。

至少处理：

1. 去除首尾空白。
2. Windows 换行统一。
3. 连续多余空白合理处理。
4. 空字符串直接拒绝。
5. 只有空白直接拒绝。
6. 设置最大文本长度。
7. 超长文本不直接传 API，应返回明确错误或按照配置策略处理。
8. 不要错误删除正常句子中的必要标点。

增加测试覆盖：
英文
中文
多段文本
换行
空白
超长文本
Unicode
emoji

TranslationManager 必须只处理 normalized text。
```

---

## Step 12：实现 Word 专用 Selection Provider

### 目标

Word 中优先不使用 Ctrl+C。

### Codex 提示词

```text
实现 WordSelectionProvider。

使用 Windows COM Automation。

要求：

1. 检测当前前台程序是否为 WINWORD.EXE。
2. 如果是 Word，尝试直接获取当前 Selection.Text。
3. Word Provider 成功时不修改 Clipboard。
4. Word COM 获取失败时不能终止整个流程。
5. SelectionManager fallback 到 Clipboard Provider。
6. Word API 调用全部封装在 WordSelectionProvider。
7. 不允许把 COM 对象传到不安全线程长期保存。
8. 做好 COM 异常转换。

SelectionManager 顺序：

Word foreground?
    ↓ yes
WordProvider
    ↓ fail
ClipboardProvider

自动测试：
全部 mock COM。

人工测试：
1. Word 选英文。
2. Clipboard 预先放入固定文本 ABC。
3. Alt+Q。
4. 翻译成功。
5. Clipboard 仍然是 ABC。

这一步的核心验收是：
Word 翻译不污染剪贴板。
```

---

## Step 13：实现 Windows UI Automation Provider

### 目标

减少 Clipboard fallback 使用频率。

### Codex 提示词

```text
增加 UIASelectionProvider。

要求：

1. 从当前 focused element 获取可用的文本 selection。
2. UIA Provider 必须有明确 timeout。
3. UIA 不支持当前控件时快速失败。
4. 不允许 UIA 阻塞主程序。
5. 所有 UIA 异常转换为 SelectionError。
6. SelectionManager 使用 provider chain：

WordProvider
    ↓
UIAProvider
    ↓
ClipboardProvider

7. 日志记录本次最终使用的 provider。

自动测试：
使用 mock，不依赖真实桌面 UI。

人工兼容性测试：
Chrome
Edge
Notepad
VS Code
常用 PDF 阅读器

必须记录每个应用：
UIA Success
或
Clipboard Fallback
```

### 通过标准

即使 UIA 对某个应用失败：

```text
整体翻译仍然成功
```

Fallback 比“所有应用都必须 UIA 成功”更重要。

---

## Step 14：实现自动划词模式

### 目标

实现：

```text
鼠标选择
↓
松开
↓
自动翻译
```

### Codex 提示词

```text
在现有稳定快捷键翻译基础上，实现可选的自动划词模式。

要求：

1. 使用 MouseListener。
2. 仅关注左键拖动后释放。
3. 单纯点击不得触发翻译。
4. 必须有 debounce，默认 250ms。
5. debounce 时间可配置。
6. 自动模式可以在系统托盘关闭。
7. 快捷键模式永远保留。
8. 自动触发仍然经过 SelectionManager。
9. 与上次 normalized text 相同则不重复触发。
10. Overlay 自身被拖动时不能触发翻译。
11. 程序暂停状态不得触发。

建议状态：

MOUSE_DOWN
DRAGGING
MOUSE_UP
WAITING_DEBOUNCE
CAPTURE_SELECTION

自动测试：

- click only → no trigger
- drag + release → one trigger
- repeated mouse events → debounce 后 only one trigger
- same text → no duplicate
- paused → no trigger

人工测试：
Word 连续划选 20 个句子。
不能出现明显重复翻译或事件风暴。
```

---

## Step 15：Overlay 定位与多屏支持

### 目标

完成正式显示体验。

### Codex 提示词

```text
实现 PositionManager。

支持模式：

1. desktop_lyrics_bottom
2. desktop_lyrics_center
3. desktop_lyrics_top
4. mouse_follow
5. custom_fixed_position

要求：

1. 使用当前 screen geometry。
2. 鼠标模式不能超出屏幕。
3. Windows DPI scaling 125%、150%、200% 时位置合理。
4. 多显示器时优先使用鼠标所在屏幕。
5. 用户手工拖动位置后可以保存。
6. 所有坐标计算放在 PositionManager，而不是 OverlayWindow。

自动测试：
使用模拟 screen geometry 测试：

1920x1080
2560x1440
3840x2160
双屏
负坐标副屏

必须保证最终 rectangle 在目标 screen 可视范围内。
```

---

## Step 16：设置页与配置持久化

### 目标

用户不改代码就能配置软件。

### Codex 提示词

```text
实现 SettingsManager 和 SettingsWindow。

配置项至少：

translation:
    source_language
    target_language

trigger:
    mode
    hotkey
    debounce_ms

overlay:
    position_mode
    font_family
    font_size
    opacity
    max_width
    locked

cache:
    enabled
    max_size

要求：

1. 默认配置与用户配置分离。
2. 缺少配置字段时自动使用默认值。
3. 非法值不能导致应用崩溃。
4. 配置保存后重新启动仍有效。
5. 敏感凭据不写入普通 config。
6. 设置修改后尽可能实时预览 Overlay。

测试：
配置加载
配置合并
非法配置
缺字段
保存
重新读取
```

---

## Step 17：系统稳定性与异常恢复

### 目标

让它从 Demo 变成可长期运行的软件。

### Codex 提示词

```text
进行稳定性阶段改造。

重点检查：

1. Google 请求超时。
2. 网络断开。
3. 网络恢复。
4. API 凭据无效。
5. API quota error。
6. Clipboard busy。
7. UIA error。
8. Word 已关闭。
9. Overlay 被意外隐藏。
10. 快捷键 listener 异常。
11. 多次启动 / 退出。
12. Worker thread 异常。
13. Windows 从睡眠恢复。
14. 多次快速 trigger。

要求：

- 单个模块异常不得导致 QApplication 崩溃。
- 用户可理解错误显示 2~5 秒后自动消失。
- 完整堆栈进入日志。
- 自动测试覆盖主要异常路径。

增加 stress_test：

连续提交至少 100 个 Fake Translation 请求，
随机 latency，
随机 success/failure，
验证：
程序不崩溃；
最终结果符合 latest request；
worker 能正常结束。
```

---

## Step 18：SQLite 持久缓存与历史记录

### 目标

第二阶段功能，可在 MVP 完成后实现。

### Codex 提示词

```text
扩展 TranslationCache。

新增 SQLite L2 Cache。

要求：

L1:
memory LRU

L2:
SQLite

查询顺序：
L1 → L2 → Provider

写入：
Provider success
→ SQLite
→ L1

字段至少：
normalized_text_hash
source_language
target_language
translated_text
created_at
last_used_at

注意：
默认不要永久保存用户完整原文，除非 history 功能明确开启。

增加：
history_enabled 配置。

测试：
跨 TranslationManager 实例仍可 cache hit。
数据库损坏时应用不能崩溃，应 fallback 到 L1。
```

---

## Step 19：打包成 Windows EXE

### 目标

脱离开发环境运行。

### Codex 提示词

```text
为项目增加 Windows 打包配置。

使用 PyInstaller。

要求：

1. 生成 GUI exe。
2. 不弹出 console 窗口。
3. Qt 插件正确打包。
4. pywin32 依赖正常。
5. google-cloud-translate 依赖正常。
6. 配置目录创建正确。
7. logs 目录创建正确。
8. 不把开发机凭据打包进 exe。
9. 退出后进程完全结束。
10. 支持 clean build。

增加 build 脚本。

构建后人工测试：

全新 Windows 用户环境：
1. 启动 exe。
2. 托盘出现。
3. Overlay 正常。
4. 快捷键正常。
5. Word 划词正常。
6. Chrome 划词正常。
7. Google Translation 正常。
8. 退出后任务管理器无残留进程。

输出构建产物和已知限制。
```

---

# 18. 推荐里程碑

## Milestone A：Overlay 可用

完成：

```text
Step 0
Step 1
Step 2
Step 3
```

得到：

```text
QQ音乐式桌面 Overlay
```

---

## Milestone B：本地选区闭环

完成：

```text
Step 4
Step 5
```

得到：

```text
选中文字
+
Alt+Q
↓
Overlay 显示原文
```

---

## Milestone C：真实翻译闭环

完成：

```text
Step 6
Step 7
Step 8
Step 9
Step 10
```

得到：

```text
选中文字
+
Alt+Q
↓
Google Translate
↓
Overlay 译文
```

这是第一个真正可使用版本。

---

## Milestone D：Word 高质量版本

完成：

```text
Step 11
Step 12
```

得到：

```text
Word 中翻译
不污染 Clipboard
```

---

## Milestone E：自动划词

完成：

```text
Step 13
Step 14
```

得到：

```text
鼠标选中
↓
自动翻译
```

---

## Milestone F：正式桌面软件

完成：

```text
Step 15
Step 16
Step 17
Step 19
```

得到：

```text
可配置
可长期运行
可打包
可交付
```

---

# 19. 最终运行架构

```text
                       Windows
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
   Word / Chrome                       Desktop Translator
        │                                   │
        │ Selection                         │
        └───────────────┐                   │
                        ▼                   │
               Global Input Manager         │
                        │                   │
                        ▼                   │
                 SelectionManager           │
                        │                   │
           ┌────────────┼────────────┐      │
           ▼            ▼            ▼      │
        Word COM       UIA       Clipboard  │
           │            │            │      │
           └────────────┴────────────┘      │
                        │                   │
                        ▼                   │
                 TextNormalizer             │
                        │                   │
                        ▼                   │
                TranslationManager          │
                        │                   │
                  Cache Lookup              │
                  /          \              │
                Hit          Miss           │
                 │             │            │
                 │       Worker Thread      │
                 │             │            │
                 │             ▼            │
                 │      Google Translation  │
                 │             │            │
                 └──────┬──────┘            │
                        ▼                   │
                 Request Guard              │
                        │                   │
                        ▼                   │
                TranslationResult           │
                        │                   │
                        ▼                   │
                 OverlayManager             │
                        │                   │
                        ▼                   │
              Transparent TopMost           │
                 Click-Through              │
                    Overlay                 │
                                            │
             Tray / Settings / Logs         │
```

---

# 20. 版本优先级建议

不要一次性让 Codex 实现所有功能。

推荐严格遵循：

```text
第一优先级
Overlay
↓
快捷键
↓
Clipboard Selection
↓
Fake Translation
↓
Google Translation
↓
Async
↓
Request Guard
↓
Cache
```

到这里形成：

> **稳定 MVP**

然后：

```text
Word COM
↓
UI Automation
↓
自动划词
↓
多屏
↓
设置
↓
持久缓存
↓
打包
```

---

# 21. 不建议第一版实现的功能

建议暂缓：

- OCR；
- 截图翻译；
- LLM 二次润色；
- 多翻译引擎；
- 多用户账号；
- 云同步；
- 浏览器插件；
- 自动更新；
- FastAPI 服务端；
- Agent；
- RAG；
- 翻译历史搜索；
- 富文本格式保留。

原因：

这些功能都不是第一条核心链路的必要条件。

第一阶段唯一关键问题是：

```text
Selection
    ↓
Translation
    ↓
Overlay
```

稳定运行。

---

# 22. MVP 最终验收清单

完成 MVP 后必须逐项确认：

## 启动

- [ ] 双击程序可以启动
- [ ] 系统托盘出现
- [ ] 不出现异常 console
- [ ] 可以正常退出

## Overlay

- [ ] 透明
- [ ] 无边框
- [ ] TopMost
- [ ] 可拖动
- [ ] 可锁定
- [ ] 锁定后鼠标穿透
- [ ] 不抢 Word 焦点
- [ ] 支持长文本换行

## Selection

- [ ] Notepad
- [ ] Word
- [ ] Chrome
- [ ] Edge
- [ ] VS Code

## Translation

- [ ] 英文 → 中文
- [ ] 中文 → 英文
- [ ] 网络失败有提示
- [ ] 凭据失败有提示
- [ ] 同文本缓存命中
- [ ] API 请求不卡 GUI

## 并发

- [ ] 快速连续划词不会崩溃
- [ ] 旧结果不会覆盖新结果
- [ ] 重复请求被抑制

## Clipboard

- [ ] 原剪贴板可以恢复
- [ ] Word COM 模式不污染剪贴板
- [ ] Clipboard busy 不会导致崩溃

## 自动模式

- [ ] 单击不翻译
- [ ] 拖选后翻译
- [ ] Debounce 正常
- [ ] 可以暂停
- [ ] Overlay 拖动不会误触发

---

# 23. 推荐的 Codex 执行方式

每完成一个 Step 后，不要直接让 Codex“继续”。

先要求：

```text
请先执行本阶段所有自动测试，并给出：
1. pytest 结果；
2. 当前 Git diff 摘要；
3. 本阶段人工验收方法；
4. 未完成项；
5. 是否满足本阶段 Exit Criteria。

如果不满足，不允许进入下一阶段。
```

人工验收通过后，再输入：

```text
当前 Step 已通过人工验收。

请先读取当前仓库代码和测试，
不要重构已经稳定工作的模块，
现在只执行 Step N+1。
```

这样可以显著减少 Codex：

```text
一次改太多
↓
引入回归
↓
难以定位问题
```

---

# 24. 推荐 Git 工作流

每个 Step 一个独立 commit：

```text
step-00 project bootstrap
step-01 overlay base
step-02 overlay win32 behavior
step-03 tray
step-04 global hotkey
step-05 clipboard selection
step-06 translation abstraction
step-07 google translation
step-08 async worker
step-09 request guard
step-10 cache
...
```

每个阶段：

```text
开发
↓
pytest
↓
manual acceptance
↓
commit
↓
下一阶段
```

如果某一步出现严重问题：

```text
git revert
```

即可返回最近稳定版本。

---

# 25. 最重要的架构约束

整个项目始终保持：

```text
Input
  ↓
Selection
  ↓
Translation
  ↓
Overlay
```

四层解耦。

最终业务主链可以抽象为：

```text
TriggerEvent
    ↓
SelectedText
    ↓
TranslationRequest
    ↓
TranslationResult
    ↓
OverlayCommand
```

只要坚持这个接口边界，后续即使把：

```text
Google Translation
```

替换成：

```text
DeepL
Gemini
OpenAI
本地模型
```

或者增加：

```text
OCR SelectionProvider
Browser Extension Provider
PDF Provider
```

都不需要重新设计整个软件。

---

# 26. 推荐最终产品演进路径

```text
V0.1
Overlay Demo

V0.2
Alt+Q + Clipboard

V0.3
Google Translation

V0.4
Async + Cache + Request Guard

V0.5
Word COM

V0.6
UI Automation

V0.7
Auto Selection

V0.8
Settings + Multi-monitor

V0.9
Stability + Logging

V1.0
PyInstaller Release
```

第一版真正值得发布的最低标准建议是：

> **V0.4：快捷键选区翻译 + Google Translation + 异步请求 + 缓存 + QQ音乐式 Overlay。**

自动划词可以放到后续版本，因为：

> **稳定的快捷键翻译，比不稳定的“全自动划词”更有产品价值。**
