"""Voice check — detects AI-slop phrases in summarized output.

This is a static-rule guardrail. Phrases are sourced from frankx-voice.ts in the
FrankX repo; OSS users override via SBO_BANNED_PHRASES_FILE env var.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_BANNED_PHRASES: tuple[str, ...] = (
    "delve into",
    "dive into",
    "it's worth noting",
    "it is worth noting",
    "certainly",
    "absolutely",
    "as an ai",
    "i would be happy to",
    "happy to help",
    "let me know if",
    "feel free to",
    "in conclusion",
    "in summary",
    "to summarize",
    "in essence",
    "ultimately",
    "moreover",
    "furthermore",
)


def _load_banned_phrases() -> tuple[str, ...]:
    """Allow OSS users to override via env or file. Default = built-in list."""
    env = os.environ.get("SBO_BANNED_PHRASES_FILE")
    if env and Path(env).exists():
        return tuple(
            line.strip().lower()
            for line in Path(env).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        )
    return DEFAULT_BANNED_PHRASES


def find_slop_phrases(text: str) -> tuple[str, ...]:
    """Return a tuple of banned phrases found in text (case-insensitive)."""
    text_lower = text.lower()
    phrases = _load_banned_phrases()
    hits: list[str] = []
    for p in phrases:
        if re.search(rf"\b{re.escape(p)}\b", text_lower):
            hits.append(p)
    return tuple(hits)


def score_voice(text: str) -> float:
    """Return 1.0 for clean text; penalize by 0.1 per banned phrase, floor 0.0."""
    hits = find_slop_phrases(text)
    return max(0.0, 1.0 - 0.1 * len(hits))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python voice_check.py <file>")
        sys.exit(2)

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"Error: file not found: {path}")
        sys.exit(1)

    content = path.read_text(encoding="utf-8", errors="ignore")
    hits = find_slop_phrases(content)
    score = score_voice(content)

    if hits:
        print(f"Voice check failed (score: {score:.2f}): found slop phrases: {', '.join(hits)}")
        sys.exit(1)

    print(f"Voice check passed (score: {score:.2f})")
    sys.exit(0)
