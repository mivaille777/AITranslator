"""Sandboxed local workspace tools for Codex-style desktop file exploration."""

from __future__ import annotations

from pathlib import Path
import fnmatch
import os
from threading import RLock

from app.agent.tools.base import ToolResult


DEFAULT_LIST_LIMIT = 200
DEFAULT_SEARCH_LIMIT = 40
DEFAULT_READ_CHARS = 60_000
MAX_SINGLE_FILE_BYTES = 4 * 1024 * 1024
MAX_MULTI_FILE_CHARS = 80_000
_TEXT_SUFFIXES = frozenset(
    {
        ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".kts",
        ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".go", ".rs", ".rb",
        ".php", ".swift", ".m", ".mm", ".scala", ".sh", ".bash", ".zsh",
        ".ps1", ".bat", ".cmd", ".toml", ".yaml", ".yml", ".json", ".xml",
        ".ini", ".cfg", ".conf", ".properties", ".env", ".txt", ".md",
        ".markdown", ".rst", ".csv", ".sql", ".html", ".htm", ".css",
        ".scss", ".less", ".vue", ".svelte", ".ipynb",
    }
)
_IGNORED_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", "node_modules", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", ".idea", ".vscode", "dist", "build",
        ".venv", "venv", "env",
    }
)


class LocalWorkspaceTools:
    """Read/search files beneath one explicitly selected workspace root.

    Every path is canonicalized before access. Symlinks/junctions that resolve
    outside the selected root are rejected, which keeps broad Agent file access
    useful without silently granting the whole machine.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._root: Path | None = None

    @property
    def root(self) -> Path | None:
        with self._lock:
            return self._root

    @property
    def root_display(self) -> str:
        root = self.root
        return str(root) if root is not None else ""

    def select_workspace(self, path: str) -> ToolResult:
        candidate = Path(str(path or "")).expanduser()
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            return ToolResult("select_workspace", False, "工作区目录不存在或无法访问。")
        if not resolved.is_dir():
            return ToolResult("select_workspace", False, "请选择一个目录作为 Agent 工作区。")
        with self._lock:
            self._root = resolved
        return ToolResult(
            "select_workspace",
            True,
            f"已授权当前会话访问工作区：{resolved}",
            {"workspace_root": str(resolved)},
        )

    def clear_workspace(self) -> ToolResult:
        with self._lock:
            self._root = None
        return ToolResult("clear_workspace", True, "已清除当前本地工作区授权。")

    def _resolve(self, relative_path: str = ".", *, must_exist: bool = True) -> Path:
        root = self.root
        if root is None:
            raise ValueError("当前没有已授权的本地工作区。请先选择工作区目录。")
        raw = str(relative_path or ".").strip() or "."
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            resolved = candidate.resolve(strict=must_exist)
        except (OSError, RuntimeError) as exc:
            raise ValueError("目标路径不存在或无法解析。") from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError("Agent 只能访问当前已授权工作区内部的路径。") from exc
        return resolved

    def list_directory(self, path: str = ".", max_entries: int = DEFAULT_LIST_LIMIT) -> ToolResult:
        try:
            directory = self._resolve(path)
        except ValueError as exc:
            return ToolResult("list_directory", False, str(exc))
        if not directory.is_dir():
            return ToolResult("list_directory", False, "目标不是目录。")
        limit = min(1000, max(1, int(max_entries)))
        items: list[str] = []
        try:
            children = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for child in children[:limit]:
                try:
                    resolved = child.resolve(strict=True)
                    resolved.relative_to(self.root)  # type: ignore[arg-type]
                except (OSError, RuntimeError, ValueError):
                    continue
                marker = "[D]" if child.is_dir() else "[F]"
                size = ""
                if child.is_file():
                    try:
                        size = f" · {child.stat().st_size} B"
                    except OSError:
                        size = ""
                items.append(f"{marker} {child.name}{size}")
        except OSError as exc:
            return ToolResult("list_directory", False, f"目录读取失败：{type(exc).__name__}")
        relative = directory.relative_to(self.root) if directory != self.root else Path(".")
        return ToolResult(
            "list_directory",
            True,
            f"工作区目录：{relative}\n" + ("\n".join(items) if items else "（空目录）"),
            {"workspace_root": self.root_display, "path": str(relative), "entries": len(items)},
        )

    def glob_files(self, pattern: str = "**/*", max_results: int = DEFAULT_SEARCH_LIMIT) -> ToolResult:
        root = self.root
        if root is None:
            return ToolResult("glob_files", False, "当前没有已授权的本地工作区。请先选择工作区目录。")
        normalized = str(pattern or "**/*").strip() or "**/*"
        limit = min(500, max(1, int(max_results)))
        matches: list[str] = []
        for current_root, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if name not in _IGNORED_DIRS]
            base = Path(current_root)
            for name in files:
                path = base / name
                try:
                    resolved = path.resolve(strict=True)
                    relative = resolved.relative_to(root)
                except (OSError, RuntimeError, ValueError):
                    continue
                posix = relative.as_posix()
                if fnmatch.fnmatch(posix, normalized) or fnmatch.fnmatch(name, normalized):
                    matches.append(posix)
                    if len(matches) >= limit:
                        break
            if len(matches) >= limit:
                break
        return ToolResult(
            "glob_files",
            True,
            "\n".join(matches) if matches else "没有找到匹配文件。",
            {"workspace_root": str(root), "pattern": normalized, "matches": len(matches)},
        )

    @staticmethod
    def _looks_textual(path: Path) -> bool:
        return path.suffix.lower() in _TEXT_SUFFIXES or path.name.lower() in {
            "dockerfile", "makefile", "license", "readme", "procfile"
        }

    def read_file(self, path: str, max_chars: int = DEFAULT_READ_CHARS) -> ToolResult:
        try:
            resolved = self._resolve(path)
        except ValueError as exc:
            return ToolResult("read_file", False, str(exc))
        if not resolved.is_file():
            return ToolResult("read_file", False, "目标不是普通文件。")
        if not self._looks_textual(resolved):
            return ToolResult(
                "read_file",
                False,
                "该文件不是可直接读取的文本/代码文件；PDF、DOCX 请使用文档工具。",
            )
        try:
            size = resolved.stat().st_size
            if size > MAX_SINGLE_FILE_BYTES:
                return ToolResult("read_file", False, "文件过大，请先使用搜索工具定位相关内容。")
            text = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult("read_file", False, f"文件读取失败：{type(exc).__name__}")
        safe_max = min(120_000, max(1_000, int(max_chars)))
        content = text[:safe_max]
        relative = resolved.relative_to(self.root)  # type: ignore[arg-type]
        return ToolResult(
            "read_file",
            True,
            content,
            {
                "workspace_root": self.root_display,
                "path": relative.as_posix(),
                "returned_chars": len(content),
                "total_chars": len(text),
                "truncated": len(content) < len(text),
            },
        )

    def read_files(self, paths: list[str] | tuple[str, ...]) -> ToolResult:
        requested = [str(item).strip() for item in paths if str(item).strip()]
        if not requested:
            return ToolResult("read_files", False, "没有提供要读取的文件。")
        blocks: list[str] = []
        total = 0
        for path in requested[:12]:
            result = self.read_file(path, max_chars=20_000)
            if not result.ok:
                blocks.append(f"### {path}\n[读取失败] {result.content}")
                continue
            remaining = MAX_MULTI_FILE_CHARS - total
            if remaining <= 0:
                break
            content = result.content[:remaining]
            blocks.append(f"### {path}\n{content}")
            total += len(content)
        return ToolResult(
            "read_files",
            True,
            "\n\n".join(blocks),
            {"workspace_root": self.root_display, "requested": len(requested), "returned_chars": total},
        )

    def search_files(
        self,
        query: str,
        pattern: str = "**/*",
        max_results: int = DEFAULT_SEARCH_LIMIT,
    ) -> ToolResult:
        root = self.root
        if root is None:
            return ToolResult("search_files", False, "当前没有已授权的本地工作区。请先选择工作区目录。")
        needle = str(query or "").strip()
        if not needle:
            return ToolResult("search_files", False, "本地搜索关键词不能为空。")
        limit = min(200, max(1, int(max_results)))
        lowered = needle.lower()
        matches: list[str] = []
        for current_root, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if name not in _IGNORED_DIRS]
            base = Path(current_root)
            for name in files:
                path = base / name
                try:
                    resolved = path.resolve(strict=True)
                    relative = resolved.relative_to(root)
                except (OSError, RuntimeError, ValueError):
                    continue
                if not self._looks_textual(resolved):
                    continue
                posix = relative.as_posix()
                if not (fnmatch.fnmatch(posix, pattern) or fnmatch.fnmatch(name, pattern)):
                    continue
                try:
                    if resolved.stat().st_size > MAX_SINGLE_FILE_BYTES:
                        continue
                    text = resolved.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for line_number, line in enumerate(text.splitlines(), 1):
                    if lowered in line.lower():
                        excerpt = " ".join(line.strip().split())[:360]
                        matches.append(f"{posix}:{line_number}: {excerpt}")
                        if len(matches) >= limit:
                            break
                if len(matches) >= limit:
                    break
            if len(matches) >= limit:
                break
        return ToolResult(
            "search_files",
            True,
            "\n".join(matches) if matches else f"工作区中没有找到“{needle}”。",
            {"workspace_root": str(root), "query": needle, "matches": len(matches)},
        )


__all__ = ["LocalWorkspaceTools"]
