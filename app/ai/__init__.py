"""AI service integration primitives."""

from app.ai.chunking import DEFAULT_CHUNK_SIZE, merge_chunks, split_text
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
from app.ai.output_guard import OutputValidation, normalize_model_output, validate_model_output
from app.ai.prompts import (
    POLISH_STYLE_INSTRUCTIONS,
    build_polish_prompt,
    build_strict_retry_prompt,
    build_translate_prompt,
)
from app.ai.provider import AITextProvider, DeepSeekTextProvider
from app.ai.service import (
    AITextService,
    DEFAULT_AI_POLISH_STYLE,
    DEFAULT_AI_SOURCE_LANGUAGE,
    DEFAULT_AI_TARGET_LANGUAGE,
)
from app.ai.task import AITextTask, AITextTaskFailure, AITextTaskSignals


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
    "AITextService",
    "AITextTask",
    "AITextTaskFailure",
    "AITextTaskSignals",
    "DEFAULT_AI_POLISH_STYLE",
    "DEFAULT_AI_SOURCE_LANGUAGE",
    "DEFAULT_AI_TARGET_LANGUAGE",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
    "DeepSeekClient",
    "DeepSeekTextProvider",
    "OutputValidation",
    "POLISH_STYLE_INSTRUCTIONS",
    "SUPPORTED_DEEPSEEK_MODELS",
    "build_polish_prompt",
    "build_strict_retry_prompt",
    "build_translate_prompt",
    "merge_chunks",
    "normalize_model_output",
    "split_text",
    "validate_model_output",
]
