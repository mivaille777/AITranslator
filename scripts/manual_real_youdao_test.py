"""Manual real-network smoke test for the Youdao web translation provider.

Run from repository root:
    python scripts/manual_real_youdao_test.py
    python scripts/manual_real_youdao_test.py "Hello world" --source en --target zh-CN

This script intentionally tests the provider directly so an old TranslationCache
entry cannot hide a real network/provider problem.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# When Python executes ``scripts/foo.py`` directly, ``scripts`` becomes
# sys.path[0] rather than the repository root. Add the root explicitly so the
# top-level ``app`` package is importable without requiring PYTHONPATH changes.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.models.translation import TranslationRequest
from app.translation.youdao_web_provider import YoudaoWebTranslationProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="?", default="Hello world")
    parser.add_argument("--source", default="en")
    parser.add_argument("--target", default="zh-CN")
    args = parser.parse_args()

    provider = YoudaoWebTranslationProvider()
    try:
        print(f"provider = {provider.name}")
        print(f"endpoint = {provider.endpoint}")
        result = provider.translate(
            TranslationRequest(
                source_text=args.text,
                source_language=args.source,
                target_language=args.target,
                request_id=1,
            )
        )
        print(f"translated_text = {result.translated_text}")
        print(f"source_language = {result.source_language}")
        print(f"target_language = {result.target_language}")
        return 0
    finally:
        provider.close()


if __name__ == "__main__":
    raise SystemExit(main())
