class AgentRuntimeError(Exception):
    """Base exception for agent runtime failures."""


class AgentToolError(AgentRuntimeError):
    """Raised when an agent tool execution fails."""
