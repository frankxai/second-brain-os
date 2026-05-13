"""Dual-write — produces both raw (private/) and summary (brain/) files for one conversation.

Path shape:
- private/chat-history/{platform}/YYYY-MM-DD-{conversation-id}.md
- brain/_inbox/{platform}/YYYY-MM-DD-{slug}.md

Both files carry full frontmatter. The brain file links to the private file by relative
path (the MCP server cannot resolve it; the link is for human reference in Obsidian).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
from slugify import slugify

from sbo_ingestion.handlers.claude_ai import Conversation
from sbo_ingestion.summarize import Summary


@dataclass(frozen=True)
class DualWriteResult:
    private_path: Path
    brain_path: Path


def _date_from(iso: str) -> str:
    if not iso:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return iso[:10]


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def write_pair(
    convo: Conversation,
    summary: Summary,
    *,
    brain_root: Path,
    private_root: Path,
) -> DualWriteResult:
    """Write the dual-write pair. Creates parent directories as needed."""
    date = _date_from(convo.created_at)
    platform_dir = convo.platform.replace(".", "-")  # claude.ai -> claude-ai

    # Private (raw)
    private_dir = private_root / "chat-history" / platform_dir
    private_dir.mkdir(parents=True, exist_ok=True)
    private_filename = f"{date}-{convo.uuid}.md"
    private_path = private_dir / private_filename
    private_post = frontmatter.Post(
        content=convo.to_raw_markdown(),
        source=convo.platform,
        conversation_id=convo.uuid,
        title=convo.title,
        created_at=convo.created_at,
        updated_at=convo.updated_at,
        imported=_now_iso(),
        message_count=len(convo.messages),
    )
    private_path.write_text(frontmatter.dumps(private_post), encoding="utf-8")

    # Brain (summary)
    brain_dir = brain_root / "_inbox" / platform_dir
    brain_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(summary.title)[:80] or "untitled"
    brain_filename = f"{date}-{slug}.md"
    brain_path = brain_dir / brain_filename
    brain_body = _render_brain_body(summary)
    # Reference the private file by name relative to the private vault (informational only)
    private_ref = f"chat-history/{platform_dir}/{private_filename}"
    brain_post = frontmatter.Post(
        content=brain_body,
        source=convo.platform,
        conversation_id=convo.uuid,
        imported=_now_iso(),
        private_file=private_ref,
        status="triage",
        tags=["draft", "needs-triage"],
    )
    brain_path.write_text(frontmatter.dumps(brain_post), encoding="utf-8")

    return DualWriteResult(private_path=private_path, brain_path=brain_path)


def _render_brain_body(summary: Summary) -> str:
    lines: list[str] = [f"# {summary.title}", "", f"**TL;DR:** {summary.tldr}", ""]
    if summary.insights:
        lines.append("## Insights")
        lines.extend(f"- {x}" for x in summary.insights)
        lines.append("")
    if summary.decisions:
        lines.append("## Decisions made")
        lines.extend(f"- {x}" for x in summary.decisions)
        lines.append("")
    if summary.open_questions:
        lines.append("## Open questions")
        lines.extend(f"- {x}" for x in summary.open_questions)
        lines.append("")
    if summary.people_mentioned:
        lines.append("## People mentioned")
        for p in summary.people_mentioned:
            lines.append(f"- **{p.name}** — {p.context}")
        lines.append("")
    if summary.suggested_destinations:
        lines.append("## Suggested destinations")
        lines.extend(f"- `{x}`" for x in summary.suggested_destinations)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
