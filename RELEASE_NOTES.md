# AITranslator v0.1.0

发布日期：2026-08-18

这是 AITranslator 的首个公开版本，一个面向 Windows 的桌面划词翻译工具。它可以在 Word、Chrome、记事本等应用中捕获选中文本，并通过悬浮窗快速显示中文翻译结果。

## 主要功能

- 自动划词翻译默认开启，释放鼠标后自动提交翻译。
- 保留 Alt+Q 全局快捷键，支持手动触发翻译。
- 支持 Word COM、Windows UI Automation 和剪贴板多级选区获取。
- 默认使用 Google Translate Web 后端，无需配置 Google Cloud 账户或凭据。
- 深色圆角悬浮窗，支持拖动、锁定、置顶和多屏安全定位。
- 支持显示/隐藏原文、复制译文、源语言选择和右键菜单。
- 支持背景透明度与字体透明度分别调节。
- 支持字体大小、主题、悬浮窗位置和触发模式设置。
- 支持异步翻译、最新请求优先、内存 LRU 缓存和可选 SQLite 缓存。
- 复制、加载、翻译完成和悬停状态提供轻量交互动画。
- 统一日志记录和异常保护，不记录用户原文或凭据。

## Windows EXE

发布包使用 PyInstaller GUI onedir 模式构建，不弹出控制台窗口。

启动方式：

1. 下载完整的 AITranslator 文件夹。
2. 运行其中的 AITranslator.exe。
3. 程序启动后会显示系统托盘图标。

请不要只复制 EXE 文件，Qt 插件和 Windows 原生依赖位于同级目录及 _internal 目录中。

用户配置、缓存和日志默认位于：

    %APPDATA%\AITranslator\

## 验证结果

- Python 3.11.7 开发环境验证通过。
- PySide6、pywin32、pynput 和 UI Automation 依赖验证通过。
- PyInstaller EXE smoke test 通过。
- EXE 启动后能够创建配置目录和日志目录。
- 退出后未发现本次构建产生的残留进程。
- pytest：143 passed。

## 已知限制

- 翻译服务使用 Google Translate Web 兼容接口，需要网络连接。
- Web 接口属于非官方接口，可能受到访问频率限制或接口变化影响。
- 当前版本不包含 Google Cloud Translation SDK，也不读取 Google Cloud 凭据。
- 当前发布包是 onedir 目录格式，暂未提供安装程序和代码签名。
- Word 的高级选区读取依赖本机已安装并运行 Microsoft Word。
- 不同应用对文本选区的支持能力不同，程序会自动尝试其他选区提供器。

## 欢迎反馈与改进

AITranslator 仍处于早期版本，欢迎其他 GitHub 成员提出问题、改进建议和功能贡献。你可以通过 Issue 反馈使用问题，也可以提交 Pull Request 改进选区获取、翻译速度、界面交互、兼容性或打包流程。

提交反馈时，如果方便，请附上：

- Windows 版本和应用版本。
- 复现步骤。
- 相关的安全日志片段。
- 是否使用了自动划词、Word、Chrome 或其他特定应用。

请勿在 Issue 或日志中上传原文内容、账号信息、访问令牌或其他敏感凭据。
