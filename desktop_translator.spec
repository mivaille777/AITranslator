# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build for the Windows Desktop Translator."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).resolve()
default_config = project_root / "config" / "default.toml"

# Only the shipped, non-sensitive defaults are copied into the read-only
# bundle. user.toml, SQLite cache files, logs, and credentials stay outside
# the application directory and are never included in this build.
datas = [(str(default_config), "config")]

# app imports are deliberately collected so the spec keeps working when a
# later step adds a provider or UI module loaded through a factory. The
# Windows input, COM, and Credential Manager modules are listed explicitly
# because some of their imports are runtime-selected by pynput/pywin32.
hiddenimports = sorted(
    {
        *collect_submodules("app"),
        *collect_submodules("pynput"),
        *collect_submodules("win32com"),
        "certifi",
        "pywintypes",
        "pythoncom",
        "win32api",
        "win32clipboard",
        "win32con",
        "win32cred",
        "win32com.client",
        "win32com.client.dynamic",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
    }
)


a = Analysis(
    [str(project_root / "app" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytestqt"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name="AITranslator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    exclude_binaries=True,
    disable_windowed_traceback=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    a.zipfiles,
    a.dependencies,
    strip=False,
    upx=False,
    name="AITranslator",
)
