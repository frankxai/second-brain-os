"""Append-only audit log at private/_distill/audit.jsonl.

Records every ingest + distill event. Lives inside the private/ vault — never
touched by MCP, never published. Use this to verify what came in and what got
summarized, by which agent, when. The log is append-only by convention; do not
rewrite past entries.

Schema (one JSON object per line):

  {
    "ts":              ISO-8601 UTC timestamp,
    "action":          "ingest" | "distill",
    "conversation_id": str,
    "mode":            "agent" | "api" | "dry-run"   (ingest only),
    "format":          "claude.ai" | "chatgpt"        (ingest only),
    "raw_path":        relative path to private file  (ingest only),
    "brain_path":      relative path to brain file    (ingest only),
    "model":           model identifier               (distill only, optional),
    "agent":           agent identifier               (distill only, optional),
    "summary_chars":   int                            (distill only, optional)
  }
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _audit_path(private_root: Path) -> Path:
    """Resolve the audit log path under private_root."""
    return private_root / "_distill" / "audit.jsonl"


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def append(private_root: Path, entry: dict[str, Any]) -> Path:
    """Append one JSON object to the audit log. Creates the parent dir as needed.

    Returns the path to the audit log file.
    """
    path = _audit_path(private_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": _now(), **entry}
    line = json.dumps(payload, ensure_ascii=False, sort_keys=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return path


def record_ingest(
    private_root: Path,
    *,
    conversation_id: str,
    mode: str,
    fmt: str,
    raw_path: Path,
    brain_path: Path,
    private_root_for_rel: Path | None = None,
    brain_root_for_rel: Path | None = None,
) -> Path:
    """Convenience wrapper for the canonical ingest event shape."""
    raw_rel = _relpath(raw_path, private_root_for_rel or private_root)
    brain_rel = _relpath(brain_path, brain_root_for_rel or brain_path.parent.parent.parent)
    return append(
        private_root,
        {
            "action": "ingest",
            "conversation_id": conversation_id,
            "mode": mode,
            "format": fmt,
            "raw_path": raw_rel,
            "brain_path": brain_rel,
        },
    )


def record_distill(
    private_root: Path,
    *,
    conversation_id: str,
    agent: str = "unknown",
    model: str = "",
    summary_chars: int = 0,
) -> Path:
    """Convenience wrapper for the canonical distill event shape.

    Called by the /distill-inbox agent after it fills a stub with a real summary.
    """
    entry: dict[str, Any] = {
        "action": "distill",
        "conversation_id": conversation_id,
        "agent": agent,
    }
    if model:
        entry["model"] = model
    if summary_chars:
        entry["summary_chars"] = summary_chars
    return append(private_root, entry)


def _relpath(target: Path, base: Path) -> str:
    """Best-effort relative path; falls back to absolute string."""
    try:
        return str(target.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(target).replace("\\", "/")
