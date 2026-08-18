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
from app.ai.prompts import (
    POLISH_STYLE_INSTRUCTIONS,
    build_polish_prompt,
    build_translate_prompt,
)
from app.ai.provider import AITextProvider, DeepSeekTextProvider


__all__ = [
    "AIAuthenticationError",
    "AIConfigurationError",
    "AIConnectionError",
    "AIError",
    "AIRateLimitError",
    "AIResponseError",
    "AITimeoutError",
    "AITextAction",
    "AITextProvider",
    "AITextRequest",
    "AITextResult",
    "DEFAULT_DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
    "DeepSeekClient",
    "DeepSeekTextProvider",
    "POLISH_STYLE_INSTRUCTIONS",
    "SUPPORTED_DEEPSEEK_MODELS",
    "build_polish_prompt",
    "build_translate_prompt",
]
