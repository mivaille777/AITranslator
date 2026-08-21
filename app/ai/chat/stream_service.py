"""Provider-facing streaming conversational AI core without UI dependencies."""

from __future__ import annotations

from typing import Any, Iterator

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from app.ai.chat.models import ChatRequest
from app.ai.chat.service import AIChatService, CHAT_SYSTEM_PROMPT, build_chat_prompt
from app.ai.errors import (
    AIAuthenticationError,
    AIConfigurationError,
    AIConnectionError,
    AIError,
    AIRateLimitError,
    AIResponseError,
    AITimeoutError,
)


class ProviderStreamingAIChatService(AIChatService):
    """Stream chat completions without importing Qt, LangGraph, or desktop UI code.

    Providers may expose a stable ``stream`` method on their application-facing
    client wrapper. Older OpenAI-compatible wrappers that only expose the SDK
    client remain supported during migration. Test/integration providers that
    expose neither streaming surface fall back to the non-streaming chat core.
    """

    def stream(self, request: ChatRequest) -> Iterator[str]:
        validated = self._validate_request(request)
        prompt = build_chat_prompt(validated)
        wrapper = self._client()

        stream_method = getattr(wrapper, "stream", None)
        if callable(stream_method):
            received = False
            try:
                for delta in stream_method(
                    system_prompt=CHAT_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                ):
                    if isinstance(delta, str) and delta:
                        received = True
                        yield delta
            except AIError:
                raise
            except Exception as exc:
                raise AIResponseError("AI chat streaming request failed.") from exc
            if not received:
                raise AIResponseError("AI chat provider returned empty streamed content.")
            return

        sdk_client = getattr(wrapper, "_client", None)
        completions = getattr(getattr(sdk_client, "chat", None), "completions", None)
        create = getattr(completions, "create", None)
        if callable(create):
            yield from self._stream_openai_compatible(wrapper, create, prompt)
            return

        result = self.execute(validated)
        if result.output_text:
            yield result.output_text

    def _stream_openai_compatible(
        self,
        wrapper: Any,
        create: Any,
        prompt: str,
    ) -> Iterator[str]:
        model = str(getattr(wrapper, "model", self.model)).strip()
        if not model:
            raise AIConfigurationError("AI chat provider model is unavailable.")

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": True,
        }
        thinking_enabled = bool(getattr(wrapper, "thinking_enabled", False))
        if hasattr(wrapper, "thinking_enabled"):
            payload["extra_body"] = {
                "thinking": {
                    "type": "enabled" if thinking_enabled else "disabled",
                }
            }
        if not thinking_enabled:
            payload["temperature"] = self.temperature
        if self.max_tokens > 0:
            payload["max_tokens"] = self.max_tokens

        received = False
        response_stream: Any | None = None
        try:
            response_stream = create(**payload)
            for event in response_stream:
                try:
                    delta = event.choices[0].delta.content
                except (AttributeError, IndexError, TypeError):
                    continue
                if isinstance(delta, str) and delta:
                    received = True
                    yield delta
        except AuthenticationError as exc:
            raise AIAuthenticationError("AI chat API authentication failed.") from exc
        except RateLimitError as exc:
            raise AIRateLimitError("AI chat API rate limit exceeded.") from exc
        except APITimeoutError as exc:
            raise AITimeoutError("AI chat API request timed out.") from exc
        except APIConnectionError as exc:
            raise AIConnectionError("Unable to connect to the AI chat API.") from exc
        except APIStatusError as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code is None:
                raise AIResponseError("AI chat API request failed.") from exc
            raise AIResponseError(
                f"AI chat API request failed with HTTP status {status_code}."
            ) from exc
        except AIError:
            raise
        except Exception as exc:
            raise AIResponseError("AI chat streaming request failed.") from exc
        finally:
            close = getattr(response_stream, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

        if not received:
            raise AIResponseError("AI chat provider returned empty streamed content.")


__all__ = ["ProviderStreamingAIChatService"]
