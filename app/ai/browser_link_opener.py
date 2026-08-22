"""Explicit browser chooser for Ctrl-clicked AI chat links."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Iterable
from urllib.parse import urlsplit

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget


_ALLOWED_LINK_SCHEMES = frozenset({"http", "https"})


@dataclass(frozen=True, slots=True)
class BrowserChoice:
    """One user-selectable browser target."""

    label: str
    executable: str = ""


_BROWSER_SPECS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Microsoft Edge", ("msedge.exe",)),
    ("Google Chrome", ("chrome.exe",)),
    ("Mozilla Firefox", ("firefox.exe",)),
    ("Brave", ("brave.exe",)),
    ("Opera", ("opera.exe", "launcher.exe")),
    ("Vivaldi", ("vivaldi.exe",)),
)


def _registry_app_path(executable_name: str) -> str:
    """Best-effort Windows App Paths lookup without introducing hard deps."""

    try:
        import winreg
    except Exception:
        return ""

    subkey = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable_name}"
    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    views = (
        getattr(winreg, "KEY_WOW64_64KEY", 0),
        getattr(winreg, "KEY_WOW64_32KEY", 0),
        0,
    )
    for root in roots:
        for view in views:
            try:
                with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view) as key:
                    value, _kind = winreg.QueryValueEx(key, None)
            except OSError:
                continue
            candidate = str(value or "").strip().strip('"')
            if candidate and Path(candidate).is_file():
                return candidate
    return ""


def _common_install_candidates(executable_name: str) -> Iterable[Path]:
    roots = {
        str(os.environ.get("PROGRAMFILES", "")).strip(),
        str(os.environ.get("PROGRAMFILES(X86)", "")).strip(),
        str(os.environ.get("LOCALAPPDATA", "")).strip(),
    }
    relative_paths: dict[str, tuple[str, ...]] = {
        "msedge.exe": (
            "Microsoft/Edge/Application/msedge.exe",
        ),
        "chrome.exe": (
            "Google/Chrome/Application/chrome.exe",
        ),
        "firefox.exe": (
            "Mozilla Firefox/firefox.exe",
        ),
        "brave.exe": (
            "BraveSoftware/Brave-Browser/Application/brave.exe",
        ),
        "opera.exe": (
            "Programs/Opera/opera.exe",
        ),
        "launcher.exe": (
            "Programs/Opera/launcher.exe",
        ),
        "vivaldi.exe": (
            "Vivaldi/Application/vivaldi.exe",
        ),
    }
    for root in roots:
        if not root:
            continue
        for relative in relative_paths.get(executable_name.casefold(), ()):
            yield Path(root) / relative


def _resolve_browser_executable(names: tuple[str, ...]) -> str:
    for name in names:
        candidate = shutil.which(name)
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
        candidate = _registry_app_path(name)
        if candidate:
            return candidate
        for path in _common_install_candidates(name):
            if path.is_file():
                return str(path)
    return ""


def discover_browser_choices() -> tuple[BrowserChoice, ...]:
    """Return system default plus installed browsers, de-duplicated by path."""

    choices: list[BrowserChoice] = [BrowserChoice("系统默认浏览器")]
    seen_paths: set[str] = set()
    for label, executable_names in _BROWSER_SPECS:
        executable = _resolve_browser_executable(executable_names)
        if not executable:
            continue
        normalized = os.path.normcase(os.path.abspath(executable))
        if normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        choices.append(BrowserChoice(label, executable))
    return tuple(choices)


def _normalized_http_url(url: object) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    if parsed.scheme.casefold() not in _ALLOWED_LINK_SCHEMES or not parsed.netloc:
        return ""
    return text


def open_url_with_choice(choice: BrowserChoice, url: str) -> bool:
    """Open a validated URL with one explicit browser choice."""

    safe_url = _normalized_http_url(url)
    if not safe_url:
        return False
    if not choice.executable:
        return bool(QDesktopServices.openUrl(QUrl(safe_url)))
    try:
        subprocess.Popen(
            [choice.executable, safe_url],
            close_fds=True,
        )
    except (OSError, ValueError):
        return False
    return True


def prompt_and_open_url(parent: QWidget | None, url: object) -> bool:
    """Ask which browser to use before opening one Ctrl-clicked chat URL."""

    safe_url = _normalized_http_url(url)
    if not safe_url:
        QMessageBox.warning(
            parent,
            "无法打开链接",
            "仅支持通过浏览器打开 http/https 链接。",
        )
        return False

    choices = discover_browser_choices()
    labels = [item.label for item in choices]
    selected, accepted = QInputDialog.getItem(
        parent,
        "选择浏览器",
        f"使用哪个浏览器打开这个链接？\n\n{safe_url}",
        labels,
        0,
        False,
    )
    if not accepted:
        return False

    try:
        index = labels.index(str(selected))
    except ValueError:
        return False
    opened = open_url_with_choice(choices[index], safe_url)
    if not opened:
        QMessageBox.warning(
            parent,
            "无法打开链接",
            "所选浏览器无法启动，请选择其他浏览器或检查安装状态。",
        )
    return opened


__all__ = [
    "BrowserChoice",
    "discover_browser_choices",
    "open_url_with_choice",
    "prompt_and_open_url",
]
