from __future__ import annotations

from app.agent.desktop_tool_runtime import DesktopAgentToolCoordinator
from app.agent.tools.local_workspace import LocalWorkspaceTools


def test_workspace_can_list_search_and_read_but_not_escape(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("Desktop Agent\nLangGraph runtime\n", encoding="utf-8")
    package = root / "app"
    package.mkdir()
    (package / "main.py").write_text("from langgraph.graph import StateGraph\n", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("do not expose", encoding="utf-8")

    tools = LocalWorkspaceTools()
    assert tools.select_workspace(str(root)).ok

    listing = tools.list_directory()
    assert listing.ok
    assert "README.md" in listing.content
    assert "app" in listing.content

    search = tools.search_files("StateGraph")
    assert search.ok
    assert "app/main.py:1" in search.content

    read = tools.read_file("README.md")
    assert read.ok
    assert "LangGraph runtime" in read.content

    escaped = tools.read_file("../secret.txt")
    assert not escaped.ok
    assert "工作区" in escaped.content
    assert "do not expose" not in escaped.content


def test_desktop_tool_runtime_routes_workspace_commands(tmp_path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    coordinator = DesktopAgentToolCoordinator()

    plan = coordinator.plan_message("打开工作区")
    assert plan.handled
    assert plan.tool_name == "select_workspace"
    assert plan.requires_file_picker

    opened = coordinator.execute_message("打开工作区", selected_file=str(root))
    assert opened.handled
    assert "已授权" in opened.assistant_message

    plan = coordinator.plan_message("读取文件内容 pyproject.toml")
    assert plan.tool_name == "read_file"
    outcome = coordinator.execute_message("读取文件内容 pyproject.toml")
    assert outcome.requires_llm
    assert "name='demo'" in outcome.tool_context
