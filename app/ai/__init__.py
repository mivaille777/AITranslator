"""AI service integration primitives."""

from app.ai.client import (
    DEFAULT_DEEPSEEK_MODEL,
    DEEPSEEK_BASE_URL,
    DeepSeekClient,
    SUPPORTED_DEEPSEEK_MODELS,
)
from app.ai.errors import (
    AIAuthenticationError,
    AIConfigurationError,
    AIConnectionError,
    AIError,
    AIRateLimitError,
    AIResponseError,
    AITimeoutError,
)
from app.ai.models import AITextAction, AITextRequest, AITextResult


__all__ = [
    "AIAuthenticationError",
    "AIConfigurationError",
    "AIConnectionError",
    "AIError",
    "AIRateLimitError",
    "AIResponseError",
    "AITimeoutError",
    "AITextAction",
    "AITextRequest",
    "AITextResult",
    "DEFAULT_DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
    "DeepSeekClient",
    "SUPPORTED_DEEPSEEK_MODELS",
]
