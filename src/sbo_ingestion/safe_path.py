"""Filesystem safety for values that came out of an export file.

Conversation uuids, titles and timestamps are attacker-influenced. Anything
derived from them and used as a path component goes through
``safe_component``; every resulting write target is re-checked with
``ensure_within`` before the write happens. The second check is not redundant —
it is the backstop for a sanitizer bug.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

MAX_COMPONENT = 80

_ILLEGAL = re.compile("[" + re.escape("<>:\"/\\|?*") + "\\x00-\\x1f\\x7f]")
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def safe_component(value: str, *, fallback: str, max_len: int = MAX_COMPONENT) -> str:
    """Reduce ``value`` to a single, inert filename component.

    Strips directory separators, drive letters and NTFS stream markers (``:``),
    control characters, parent-directory hops, and Windows reserved device
    names; truncates to ``max_len``. Returns ``fallback`` if nothing survives.
    """
    cleaned = unicodedata.normalize("NFC", value or "")
    cleaned = _ILLEGAL.sub("-", cleaned)
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "-")
    cleaned = cleaned.strip(". ")[:max_len].strip(". ")
    if not cleaned or cleaned.split(".")[0].upper() in _RESERVED:
        return fallback
    return cleaned


def ensure_within(root: Path, target: Path) -> Path:
    """Return ``target`` unchanged, or raise if it resolves outside ``root``."""
    resolved = target.resolve()
    root_resolved = root.resolve()
    if root_resolved not in resolved.parents:
        raise ValueError(f"refusing to write outside {root_resolved}: {resolved}")
    return target
