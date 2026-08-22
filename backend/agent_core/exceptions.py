class AgentRuntimeError(Exception):
    """Base exception for agent runtime failures."""


class AgentToolError(AgentRuntimeError):
    """Raised when an agent tool execution fails."""


class AgentCancelledError(AgentRuntimeError):
    """Raised when cooperative Agent cancellation is observed."""


class AgentBudgetExceededError(AgentRuntimeError):
    """Raised when the total Agent execution budget is exhausted."""


class AgentToolTimeoutError(AgentToolError):
    """Raised when a safe read/compute tool exceeds its execution timeout."""
