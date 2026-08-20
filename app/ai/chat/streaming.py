"""Streaming conversational AI execution for Overlay chat."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from threading import Event
from typing import Any, Iterator

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
from PySide6.QtCore import QObject, QRunnable, Signal

from app.agent.workflow import DEFAULT_AGENT_GRAPH
from app.ai.chat.models import ChatRequest, ChatResult
from app.ai.chat.service import (
    AIChatService,
    CHAT_SYSTEM_PROMPT,
    build_chat_prompt,
)
from app.ai.chat.task import AIChatTaskFailure
from app.ai.errors import (
    AIAuthenticationError,
    AIConfigurationError,
    AIConnectionError,
    AIError,
    AIRateLimitError,
    AIResponseError,
    AITimeoutError,
)


@dataclass(frozen=True, slots=True)
class AIChatStreamChunk:
    """One ordered UI update from a LangGraph chat stream."""

    request_id: int
    session_id: str
    delta: str
    accumulated_text: str


class StreamingAIChatService(AIChatService):
    """Stream Chat Completions while reusing the configured provider client."""

    def stream(self, request: ChatRequest) -> Iterator[str]:
        validated = self._validate_request(request)
        prompt = build_chat_prompt(validated)
        wrapper = self._client()
        sdk_client = getattr(wrapper, "_client", None)
        completions = getattr(getattr(sdk_client, "chat", None), "completions", None)
        create = getattr(completions, "create", None)

        # Custom injected providers used in tests/integrations may expose only
        # the stable non-streaming wrapper. Keep them compatible rather than
        # making streaming a hard provider requirement.
        if not callable(create):
            result = self.execute(validated)
            if result.output_text:
                yield result.output_text
            return

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


class StreamingAIChatTaskSignals(QObject):
    chunk = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal(object)


class StreamingAIChatTask(QRunnable):
    """Execute the chat branch of the shared LangGraph on a Qt worker."""

    def __init__(
        self,
        chat_service: StreamingAIChatService | Any,
        request: ChatRequest,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self.chat_service = chat_service
        self.request = request
        self.logger = logger or logging.getLogger("desktop_translator")
        self.signals = StreamingAIChatTaskSignals()
        self._cancel_event = Event()
        self.setAutoDelete(False)

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """Request cooperative cancellation of the LangGraph chat node."""

        self._cancel_event.set()

    def run(self) -> None:
        final_result: ChatResult | None = None
        try:
            if self.is_cancelled:
                return
            for part in DEFAULT_AGENT_GRAPH.stream_chat(
                self.chat_service,
                self.request,
                cancel_event=self._cancel_event,
            ):
                if self.is_cancelled:
                    continue
                part_type = str(part.get("type", "")) if isinstance(part, dict) else ""
                data = part.get("data") if isinstance(part, dict) else None

                if part_type == "custom" and isinstance(data, dict):
                    if data.get("kind") != "chat_chunk":
                        continue
                    self.signals.chunk.emit(
                        AIChatStreamChunk(
                            request_id=int(data.get("request_id", self.request.request_id)),
                            session_id=str(data.get("session_id", self.request.session_id)),
                            delta=str(data.get("delta", "")),
                            accumulated_text=str(data.get("accumulated_text", "")),
                        )
                    )
                    continue

                if part_type != "updates" or not isinstance(data, dict):
                    continue
                for update in data.values():
                    if not isinstance(update, dict):
                        continue
                    candidate = update.get("chat_result")
                    if isinstance(candidate, ChatResult):
                        final_result = candidate

            if self.is_cancelled:
                return
            if final_result is None:
                raise AIResponseError("LangGraph chat workflow produced no result.")
            self.signals.succeeded.emit(final_result)
        except AIError as exc:
            if not self.is_cancelled:
                self.signals.failed.emit(
                    AIChatTaskFailure(
                        request_id=self.request.request_id,
                        error=exc,
                    )
                )
        except Exception as exc:
            if not self.is_cancelled:
                error = AIResponseError("AI chat LangGraph execution failed.")
                error.__cause__ = exc
                self.signals.failed.emit(
                    AIChatTaskFailure(
                        request_id=self.request.request_id,
                        error=error,
                    )
                )
        finally:
            self.signals.finished.emit(self)


__all__ = [
    "AIChatStreamChunk",
    "StreamingAIChatService",
    "StreamingAIChatTask",
    "StreamingAIChatTaskSignals",
]
