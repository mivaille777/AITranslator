"""Small provider-neutral tool registry for AITranslator agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


ToolHandler = Callable[..., "ToolResult"]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Serializable observation returned by one deterministic agent tool."""

    name: str
    ok: bool
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    handler: ToolHandler


class AgentToolRegistry:
    """Register and invoke deterministic tools by stable names."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, name: str, handler: ToolHandler, *, description: str = "") -> None:
        normalized = str(name).strip()
        if not normalized:
            raise ValueError("tool name is required")
        if not callable(handler):
            raise TypeError("tool handler must be callable")
        self._tools[normalized] = ToolSpec(
            name=normalized,
            description=str(description).strip(),
            handler=handler,
        )

    def invoke(self, name: str, **kwargs: Any) -> ToolResult:
        normalized = str(name).strip()
        spec = self._tools.get(normalized)
        if spec is None:
            return ToolResult(
                name=normalized or "unknown",
                ok=False,
                content="Tool is not registered.",
            )
        try:
            result = spec.handler(**kwargs)
        except Exception as exc:
            return ToolResult(
                name=normalized,
                ok=False,
                content=f"{type(exc).__name__}: {exc}",
            )
        if isinstance(result, ToolResult):
            return result
        return ToolResult(name=normalized, ok=True, content=str(result or ""))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def describe(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools.values())


__all__ = ["AgentToolRegistry", "ToolHandler", "ToolResult", "ToolSpec"]
