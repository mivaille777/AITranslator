"""Minimal DeepSeek API connectivity smoke test.

Stage 1 only validates that AITranslator can reach the DeepSeek OpenAI-compatible
API. It intentionally does not modify translation providers or UI behavior.

Usage (PowerShell):
    $env:DEEPSEEK_API_KEY="your_api_key"
    python scripts/deepseek_smoke_test.py
"""

from __future__ import annotations

import os
import sys

from openai import OpenAI


MODEL = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com"


def main() -> int:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("Missing DEEPSEEK_API_KEY environment variable.")
        return 1

    client = OpenAI(
        api_key=api_key,
        base_url=BASE_URL,
        timeout=15.0,
        max_retries=1,
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a concise assistant.",
            },
            {
                "role": "user",
                "content": "Reply with exactly: DeepSeek API OK",
            },
        ],
        temperature=0,
        extra_body={
            "thinking": {
                "type": "disabled",
            },
        },
    )

    text = response.choices[0].message.content or ""
    print(text.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
