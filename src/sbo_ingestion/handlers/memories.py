"""Claude.ai memories.json handler — the single highest-signal artifact in an export.

The export's memories.json is the AI's OWN pre-distilled, cross-conversation memory of
the user: facts, preferences, and context it accumulated across every chat. That's a
compression the model already paid reasoning tokens for, so downstream agents should
weight it far more heavily than any single raw conversation.

Shape is tolerant by design — Claude has shipped several. We handle:
- a top-level list of memory entries
- a dict with a "memories" (or "items"/"entries"/"records") list
- a flat dict of {key: value} facts
- a bare string
Each entry may be a string, or a dict carrying the text under text/content/memory/value/summary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

# Keys an entry-dict might stash its text under, in priority order.
_TEXT_KEYS = ("text", "content", "memory", "summary", "value", "description")
# Keys a wrapper-dict might stash the memory list under, in priority order.
_LIST_KEYS = ("memories", "items", "entries", "records", "data")

_HEADER = (
    "This file is the AI's own pre-distilled, cross-conversation memory of the user, "
    "lifted verbatim from the export's `memories.json`. It is the single highest-signal "
    "artifact in the whole export: the model already compressed thousands of messages "
    "into these standing facts and preferences. **Agents distilling this vault should "
    "weight these memories heavily** — treat them as durable ground truth about the "
    "user, not as one conversation among many. Verify against raw chats only when a "
    "memory looks stale or contradicts a newer one."
)


@dataclass(frozen=True)
class MemoriesResult:
    brain_path: Path
    memory_count: int


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _entry_to_text(entry: object) -> str:
    """Coerce one memory entry (str or dict of varied shape) into a text line."""
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        for key in _TEXT_KEYS:
            val = entry.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        # Flat {key: value} fact with no known text key — render as "key: value".
        pairs = [f"{k}: {v}" for k, v in entry.items() if isinstance(v, (str, int, float))]
        if pairs:
            return "; ".join(pairs)
    return str(entry).strip()


def extract_memories(obj: object) -> list[str]:
    """Flatten a parsed memories.json object into a list of memory text lines.

    Tolerant of dict/list/str shapes; drops empties; preserves order.
    """
    raw: list[object]
    if isinstance(obj, list):
        raw = list(obj)
    elif isinstance(obj, dict):
        for key in _LIST_KEYS:
            val = obj.get(key)
            if isinstance(val, list):
                raw = list(val)
                break
        else:
            # No wrapper list — treat the dict itself as {key: value} facts.
            raw = [{k: v} for k, v in obj.items()]
    elif isinstance(obj, str):
        raw = [obj]
    else:
        raw = []

    lines = [_entry_to_text(e) for e in raw]
    return [ln for ln in lines if ln]


def parse_memories(path: Path) -> list[str]:
    """Load and flatten a memories.json file into memory text lines."""
    with path.open("r", encoding="utf-8") as f:
        try:
            obj = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}") from e
    return extract_memories(obj)


def _render_body(memories: list[str]) -> str:
    lines: list[str] = ["# AI cross-conversation memory export", "", _HEADER, ""]
    if memories:
        lines.append("## Memories")
        lines.extend(f"- {m}" for m in memories)
    else:
        lines.append("_(No memories found in the export's memories.json.)_")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_memory_export(
    path: Path,
    *,
    brain_root: Path,
    platform: str = "claude.ai",
) -> MemoriesResult:
    """Parse memories.json and render brain/_inbox/{platform}/_memory-export.md.

    Creates parent directories as needed. The file leads with the underscore-prefix
    naming used by other inbox scaffolding so it sorts to the top and reads as meta.
    """
    memories = parse_memories(path)
    platform_dir = platform.replace(".", "-")  # claude.ai -> claude-ai
    brain_dir = brain_root / "_inbox" / platform_dir
    brain_dir.mkdir(parents=True, exist_ok=True)
    brain_path = brain_dir / "_memory-export.md"

    post = frontmatter.Post(
        content=_render_body(memories),
        source=platform,
        kind="memory-export",
        imported=_now_iso(),
        memory_count=len(memories),
        status="reference",
        weight="high",
        tags=["memory-export", "high-signal"],
    )
    brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return MemoriesResult(brain_path=brain_path, memory_count=len(memories))
