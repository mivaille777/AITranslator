"""Explicit real-network smoke test for the Google web provider.

The script bypasses TranslationCache and FastAPI so it tests only the provider
and its browser-style GTX request contract.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.models.translation import TranslationRequest
from app.translation.google_web_provider import (
    DEFAULT_WEB_ENDPOINT,
    GOOGLE_WEB_ENDPOINT,
    GoogleWebTranslationProvider,
)

DEFAULT_TEXT = "The proposed method uses a Gaussian process to guide local search."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Make one explicit real Google Translate web request."
    )
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--source-language", default="en")
    parser.add_argument("--target-language", default="zh-CN")
    parser.add_argument(
        "--endpoint",
        choices=("googleapi", "google"),
        default="googleapi",
        help="googleapi=translate.googleapis.com, google=translate.google.com",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(None if argv is None else list(argv))
    endpoint = (
        DEFAULT_WEB_ENDPOINT
        if arguments.endpoint == "googleapi"
        else GOOGLE_WEB_ENDPOINT
    )
    request = TranslationRequest(
        source_text=arguments.text,
        source_language=arguments.source_language,
        target_language=arguments.target_language,
    )

    provider = GoogleWebTranslationProvider(endpoint=endpoint)
    try:
        print(f"provider = {provider.name}")
        print(f"endpoint = {provider.endpoint}")
        print(f"tk = {provider._token(request.source_text)}")
        result = provider.translate(request)
        print(f"translated_text = {result.translated_text}")
        print(f"source_language = {result.source_language}")
        print(f"target_language = {result.target_language}")
        return 0
    except Exception as exc:
        print(f"error_type = {type(exc).__name__}")
        print(f"error = {exc}")
        raise
    finally:
        provider.close()


if __name__ == "__main__":
    raise SystemExit(main())
