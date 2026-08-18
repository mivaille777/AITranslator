"""Minimal DeepSeek API connectivity smoke test.

The smoke test now exercises the shared Stage 2 DeepSeekClient instead of
calling the provider SDK directly. It still performs a real network request
and therefore requires DEEPSEEK_API_KEY.

Usage (PowerShell):
    $env:DEEPSEEK_API_KEY="your_api_key"
    python scripts/deepseek_smoke_test.py
"""

from __future__ import annotations

from app.ai.client import DeepSeekClient
from app.ai.errors import AIError


def main() -> int:
    client: DeepSeekClient | None = None
    try:
        client = DeepSeekClient()
        text = client.complete(
            system_prompt="You are a concise assistant.",
            user_prompt="Reply with exactly: DeepSeek API OK",
            temperature=0.0,
        )
    except AIError as exc:
        print(f"DeepSeek smoke test failed: {exc}")
        return 1
    finally:
        if client is not None:
            client.close()

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
