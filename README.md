# AITranslator

AITranslator is a Windows 10/11 desktop translation assistant that translates
selected text without interrupting the current application. It is designed
for reading papers, documentation, web pages, and other foreign-language
content.

主要功能：

- 全局快捷键 Alt+Q 触发翻译
- 自动划词翻译（默认开启）
- 支持 Word、Chrome、Edge、Notepad 等常用 Windows 应用
- 深色悬浮翻译卡片、原文显示、复制、语言选择和右键菜单
- Google Translate Web 后端，无需 Google Cloud 凭据
- 内存缓存和可选 SQLite 缓存
- 系统托盘运行、窗口拖动、置顶、透明度和字体大小设置

本项目欢迎其他 GitHub 成员提出问题、提交改进建议或贡献代码。欢迎
通过 Issues 反馈使用体验，也欢迎提交 Pull Request 一起完善功能和稳定性。

## Current status

Step0 provides the installable Python package skeleton, a minimal PySide6
application bootstrap, centralized logging, environment verification, and
pytest configuration.

Step1 adds a transparent, frameless, always-on-top overlay with wrapped text,
safe multi-screen positioning, and a manual demo. Step2 adds Windows overlay
locking, mouse click-through, no-activate behavior, and unlocked dragging.
Step3 adds a system tray menu and an application controller that coordinates
tray commands with the overlay. Step4 adds the configurable global `Alt+Q`
trigger and `TranslationTriggerEvent`. Step5 adds clipboard-based selection
and clipboard restoration. On Windows, selection uses native Ctrl+C and
native plain-text clipboard access to avoid browser-private Chromium MIME
conflicts, uses a temporary random clipboard sentinel, and retries a missed
copy once. The normal application is single-instance so multiple hotkey
listeners cannot race over the clipboard. Step6 adds the translation
abstraction and an offline Fake Provider. Step7 adds the Google Translate web
endpoint and an explicit manual real-web test; no Google account credentials
are used.
Step8 moves translation requests into `QThreadPool`/`QRunnable` workers. Results
and failures return through Qt signals, so the Overlay and tray remain on the GUI
thread while a provider request is running. Shutdown clears queued work and only
waits for a bounded interval.
Step9 adds thread-safe monotonic request IDs. Only the newest request may update
the Overlay; late results and failures are discarded with debug logging.
Step10 adds a thread-safe in-memory LRU cache for successful translations. Cache
keys use source language, target language, and normalized text; caching can be
disabled in `config/default.toml` with `translation.cache_enabled = false`.
Step11 normalizes input whitespace and line endings, preserves punctuation and
Unicode, and rejects empty or overlong text before any cache or API request.
Step12 adds a Windows Word COM selection provider before the clipboard fallback;
successful Word selection reads do not modify the clipboard.
Step13 adds a bounded Windows UI Automation TextPattern provider between Word
and Clipboard. UIA runs in a daemon worker with a configurable timeout and
automatically falls back when the focused control does not support text
selection. The selected provider is recorded without logging selected text.
Step14 adds an optional mouse-drag selection mode. It listens only for a left
button drag and release, suppresses clicks and duplicate callbacks from one
gesture, and can be enabled or disabled from the system tray. Repeating the
same selected text is allowed and creates a new translation request. The
`Alt+Q` mode remains available independently.
Step15 adds `PositionManager` with desktop bottom/center/top, mouse-follow,
and custom-fixed modes. Placement uses the active screen's available geometry,
supports negative-coordinate secondary monitors, and keeps the overlay inside
the work area under normal Windows DPI scaling.
Step16 adds a non-modal settings page opened from the tray. It merges the
read-only shipped defaults with `config/user.toml`, persists only whitelisted
non-sensitive settings, and applies language, trigger, cache, position, lock,
and Overlay style changes while the application is running. Malformed or
missing user values fall back to safe defaults.
The translation layer now uses the Google Translate web-compatible endpoint as
its only translation service. The adapter keeps the token generator separate,
reuses its HTTP connection for repeated short requests, and does not use
Google account cookies or credentials.
Step17 adds bounded error handling around Qt, worker, Overlay, tray, selection,
and global listener boundaries. Listener health checks can restart a dead
hotkey or mouse listener, user-facing errors hide after three seconds, and
unexpected failures retain a sanitized traceback in `logs/app.log`.
Step18 extends the cache with an optional SQLite L2. Requests query L1 memory
first and SQLite second; successful provider results are written to SQLite and
then L1. The default stores only a normalized-text SHA-256 hash, languages,
translated text, provider, and timestamps. Full source text is stored only
when `cache.history_enabled = true` is explicitly enabled.
Step19 redesigns the Overlay with the reference dark-blue rounded-card style,
subtle shadow, border, and a matching right-click QMenu. The Overlay menu can
copy the original/translated text, hide or lock the window, toggle topmost
display, change background opacity and text opacity independently, change font
size, switch theme, open settings/about, and exit. The existing font family is
preserved; font size and opacity changes are applied immediately and saved to
`config/user.toml`.
Step20 adds a compact header inspired by the supplied desktop-translation
reference: a preset source-language selector, a translation-copy button, and
an overflow menu. The target language in this selector is fixed to Chinese.
Translations show only the translated text by default; `显示原文` in the menu
reveals the source row, and multiline results grow the same card automatically.
Step21 adds the reference interaction timing: the card fades/slides in over
160 ms, provider loading uses a looping dot indicator, new results fade in over
150 ms, hover emphasis settles over 120 ms, and source-row height changes use a
200 ms ease-out transition. Copying shows a temporary check-mark acknowledgement.
The Windows packaging configuration builds a PyInstaller GUI onedir bundle
without a console window. The bundle contains only config/default.toml;
per-user settings, the SQLite cache, and logs are created below
%APPDATA%\AITranslator when the frozen application starts.

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

## Verify the environment

```powershell
python scripts/verify_environment.py
```

The command reports the Python and Windows versions and verifies imports for
PySide6, pywin32, pynput, cachetools, certifi, and uiautomation.

## Run

Normal startup enters the Qt event loop and can be interrupted with `Ctrl+C`:

```powershell
python -m app.main
```

Only one normal application process should be running. If another instance
is already active, the second process exits and records
`application_already_running` in the log. `--smoke-test` is exempt so it can
be used while the application is running.

For a non-interactive startup check, use the smoke mode. It creates the
QApplication, enters the event loop, and exits cleanly immediately:

```powershell
python -m app.main --smoke-test
```

To view the Step1 overlay manually:

```powershell
python scripts/manual_overlay_demo.py
```

The demo displays `Overlay test / 悬浮翻译测试` in a transparent, frameless
window. Switch between Word, Chrome, and Explorer to verify that it remains
above the active application. Stop the demo with `Ctrl+C` in the terminal.

To manually verify Step2 lock and drag behavior:

```powershell
python scripts/manual_test_overlay_lock.py
```

Open Notepad and place it beneath the overlay. In the control panel, click
`Lock overlay`, then click the overlay area: Notepad should receive the click.
The console and control panel must show `LOCKED`. Click `Unlock overlay`, then
hold the left mouse button on the overlay and drag it: the overlay should move,
and the state should show `UNLOCKED`.

To manually verify Step3, start the normal application:

```powershell
python -m app.main
```

Right-click the `Desktop Translator` tray icon. The menu can enable or pause
translation, lock or unlock the Overlay, show or hide the test subtitle, and
exit the application. Translation remains a placeholder until later steps;
the `Alt+Q` trigger is implemented in Step4.

To manually verify Step4 without selection or translation:

```powershell
python scripts/manual_hotkey_test.py
```

Keep the console visible, switch to Word, Chrome, or Notepad, and press
`Alt+Q`. Each accepted action should print `HOTKEY_TRIGGERED` and write the
same event to `logs/app.log`. Stop the test with `Ctrl+C`.

To manually verify Step5 and Step6, select text in Notepad, Word, or Chrome and press
`Alt+Q` while the normal application is running:

```powershell
python -m app.main
```

The application should temporarily copy the selection and restore the previous
clipboard contents. Step7 sends the text to the Google Translate web endpoint
and shows the Chinese result in the Overlay. No account credentials are
required.

## Step7 real Google Web test

The manual script performs one real request using the default sentence from the
architecture plan; it is not run by pytest:

```powershell
python scripts/manual_real_google_test.py
```

The adapter follows the request shape used by Zotero PDF Translate: it sends
`client`, `sl`, `tl`, `hl`, repeated `dt`, `source`, `ssel`, `tsel`, `kc`, `tk`,
and `q` parameters. It keeps a warm HTTP connection and has no artificial
inter-request delay by default. The endpoint is unofficial and may be
rate-limited or changed by Google; do not treat it as a free, unlimited, or
contractual API.

## Step8 asynchronous test

To manually verify Step8 without calling Google, run the asynchronous harness:

```powershell
python scripts/manual_async_test.py
```

Press `Alt+Q`, then during the simulated two-second delay use the tray menu to
show the test subtitle and drag the unlocked Overlay. The tray and GUI should
remain responsive; after the delay the Overlay shows the simulated result.

## Step12 Word selection test

On Windows, open Word and select English text. Put a recognizable value such as
`ABC` in the clipboard, then run the normal application and press `Alt+Q`.
Word selection should translate without changing the clipboard. If Word COM
access fails, the application falls back to the existing clipboard provider.

## Step13 UI Automation compatibility test

Run the normal application and select text in each of these foreground
applications: Chrome, Edge, Notepad, VS Code, and a commonly used PDF reader.
Press `Alt+Q` and confirm that translation still succeeds even when the
application does not expose a UI Automation text selection. Check
`logs/app.log` for the provider record:

```text
selection_provider_used provider=word
selection_provider_used provider=uia
selection_provider_used provider=clipboard
```

Word is intentionally tried first. For the other applications, `uia` means
the focused UI Automation TextPattern supplied the selection, while
`clipboard` means the application-specific UIA path was unavailable or timed
out and the safe clipboard fallback handled it. The timeout can be adjusted
in `config/default.toml` with `selection.uia_timeout_ms`.

## Step14 automatic selection test

Automatic mode is on by default. Start the normal application and use the tray
menu only when you want to toggle automatic translation. In Word or Notepad,
drag across text and release;
one translation should be requested. A single click, right-button drag, or a
drag that starts on the Overlay must not trigger translation. Pause translation
from the tray and verify that mouse selection no longer captures text while
paused. Select the same text twice and verify that both selections are
translated. The auto-selection debounce interval only prevents one physical
drag from emitting duplicate release events; it does not compare text. Use the
tray menu to disable automatic selection when manual Alt+Q mode is preferred.

The mode can also be enabled at startup in `config/default.toml`:

```toml
[input]
auto_selection_enabled = true
auto_selection_debounce_ms = 250
```

Run the manual test with:

```powershell
python -m app.main
```

Check `logs/app.log` for `AUTO_SELECTION_TRIGGERED` and
`auto_selection_ignored translation_paused`. The listener is stopped
automatically when the program exits.

## Step15 overlay positioning test

The default position mode is `desktop_lyrics_bottom`. The supported modes are:

```text
desktop_lyrics_bottom
desktop_lyrics_center
desktop_lyrics_top
mouse_follow
custom_fixed_position
```

The current default can be changed in `config/default.toml`. Test the normal
application on a single monitor and then on a second monitor with a negative
X coordinate. For `mouse_follow`, move the cursor near every screen edge and
confirm the Overlay remains fully visible. Unlocking the Overlay and dragging
it records the position as a custom fixed position for the current run.

## Step16 settings test

Start the normal application and right-click the tray icon. Choose `设置` to
edit source/target languages, trigger mode and hotkey, Overlay placement and
style, and cache behavior. Overlay font, background opacity, text opacity,
width, and placement preview
as the controls change. `保存` writes only `config/user.toml`; this file is
local and ignored by Git. Credentials and access tokens are not accepted by
the settings writer.

To reset user settings, stop the application and remove the exact file
`config/user.toml`, then start the application again. The shipped
`config/default.toml` is never overwritten by the settings page.

The settings page exposes the Google web endpoint, timeout, retry count, and
minimum interval. Changing these values clears the in-memory translation cache.
The cache section also controls the SQLite L2 and explicit source-text history
mode. A damaged SQLite file is disabled for the current process and falls back
to the in-memory cache without crashing the application.

## Step19 Overlay right-click menu

Start the normal application and trigger a translation. Right-click directly on
the visible Overlay card. The dark context menu provides copy, visibility,
position, topmost, background opacity, text opacity, font-size, theme, settings,
about, and exit actions. Background opacity affects only the rounded card;
text opacity affects only the displayed translation text.
The font-size submenu includes 12/14/16/18/20/24/28/32 px; selecting a value
does not change the configured font family. The default palette is `dark`, with
`soft` and `contrast` alternatives based on the reference image.

## Step20 Overlay header interactions

After a translation is displayed, the header shows the source-to-Chinese
direction, a copy button, and a `...` menu button. The language control is
limited to the left quarter of the header while the remaining space stretches
between it and the two larger action icons. The copy button copies the
translated text. The language button opens the preset source-language list:
automatic detection, English, Japanese, Korean, French, German, Spanish, and
Chinese. Selecting a source language applies it to subsequent translations and
writes the safe choice to `config/user.toml`.

The overflow menu includes `显示原文`; it is off by default. Turning it on
shows the selected source text above the translation and persists the choice.
Short translations keep a compact card, while line-wrapped or multiline
translations expand vertically within the configured maximum width.

## Step21 Overlay interaction animation

The normal translation path displays `翻译中` with an animated dot sequence
before the worker result arrives. The result replaces that state without
blocking the Qt event loop. Showing the card uses a short fade-and-slide-up
transition; replacing the result fades the content in; hovering the card
brightens the header and shadow; and toggling `显示原文` reveals the extra row
with a short height transition. These effects are local to the Overlay and do
not change selection, dragging, locking, or provider behavior.

## Step17 stability stress test

Run the offline stress harness to submit 100 randomized-latency requests with
randomized failures. It verifies that all workers finish and that the newest
successful request remains the final result; it never contacts Google:

```powershell
python scripts/stability_stress_test.py
```

Transient translation errors are shown in the Overlay for three seconds and
then hidden automatically. A listener that dies after startup is checked every
five seconds and restarted when possible.

## Tests

```powershell
pytest
```

The Qt tests use the offscreen platform and do not call any real translation
service.

## Contributing

欢迎改进 AITranslator。提交 Issue 或 Pull Request 时，请尽量说明复现步骤、
运行环境和期望行为。涉及 UI、Windows 输入监听或翻译请求的改动，建议同时
补充或更新测试。

请勿提交以下内容：

- AITranslator 虚拟环境
- config/user.toml、SQLite 缓存、日志
- Google 或其他服务凭据
- 本地临时构建目录

## Included Windows build

The repository includes the PyInstaller onedir build under
dist/AITranslator. Run dist/AITranslator/AITranslator.exe directly on a
compatible Windows machine, or rebuild it with:

    .\scripts\build_windows.ps1 -Clean -RunSmokeTest

Distribute the complete dist/AITranslator directory so the Qt plugins and
native Windows dependencies remain available.

## Build a Windows EXE

Install the build-only dependency into the project virtual environment:

    python -m pip install -e ".[build]"

Run a clean GUI build and the frozen-process smoke test:

    .\scripts\build_windows.ps1 -Clean -RunSmokeTest

The artifact is:

    dist\AITranslator\AITranslator.exe

Distribute the complete dist\AITranslator directory, because the onedir
bundle contains the Qt platform plugins and native Windows support files next
to the executable. The build script checks that default.toml is present,
that no user.toml or common Google credential JSON is included, and that the
smoke process exits successfully after creating its writable config and logs
directories.

For a manual acceptance test on a clean Windows account, start the EXE and
check the tray icon, overlay, global hotkey, Word/Chrome selection, real web
translation, and complete process exit in Task Manager. The current
translation implementation is intentionally Google Translate Web-only:
google-cloud-translate was removed in the earlier Web-only migration and is
therefore not bundled. This build does not read Google Cloud credentials.
The web endpoint requires network access and may be rate-limited or changed by
Google; no code-signing certificate or installer is included yet.

The default cache settings are:

```toml
[translation]
source_language = "auto"
target_language = "zh-CN"
cache_enabled = true
cache_max_size = 128
max_text_length = 5000

[google_web]
enabled = true
endpoint = "https://translate.google.com/translate_a/single"
timeout_ms = 8000
max_retries = 0
min_interval_ms = 0

[cache]
enabled = true
max_size = 128
sqlite_enabled = true
sqlite_path = "config/translation_cache.sqlite3"
history_enabled = false

[trigger]
mode = "auto"
hotkey = "alt+q"
debounce_ms = 250

[selection]
uia_timeout_ms = 250

[overlay]
position_mode = "desktop_lyrics_bottom"
font_family = "Segoe UI"
font_size = 24
opacity = 1.0
background_opacity = 1.0
text_opacity = 1.0
max_width = 900
locked = false
theme = "dark"
show_original = false
margin = 24
custom_position_x = 80
custom_position_y = 80
mouse_offset_x = 16
mouse_offset_y = 16
```
