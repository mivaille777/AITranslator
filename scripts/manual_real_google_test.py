"""Explicit manual test for the real Google Translate web-compatible provider.

This script is intentionally not imported by the application and is never
called by the automated test suite. It performs one real web request when run
by the developer.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from app.models.translation import TranslationRequest
from app.translation.google_web_provider import GoogleWebTranslationProvider

DEFAULT_TEXT = (
    "The proposed method uses a Gaussian process to guide local search."
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Make one explicit real Google Translate web request."
    )
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--source-language", default="en")
    parser.add_argument("--target-language", default="zh-CN")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(
        None if argv is None else list(argv)
    )
    request = TranslationRequest(
        source_text=arguments.text,
        source_language=arguments.source_language,
        target_language=arguments.target_language,
    )

    provider = GoogleWebTranslationProvider()

    try:
        result = provider.translate(request)
    except Exception:
        print("TranslationError: Google web request failed.")
        return 1

    print(result.translated_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
