"""Ingestion orchestrator. CLI entry point.

Three modes:

- ``agent`` (default): write raw + stub summary with ``status: needs-summary``.
  No Anthropic API call. A coding-agent session (Claude Code, Cursor, Codex,
  ChatGPT, Gemini CLI) is expected to fill the stub later via ``/distill-inbox``.
  This is the recommended mode: it uses the reasoning loop you've already paid
  for, produces better cross-referenced summaries, and stays inspectable.

- ``api``: call the Anthropic API directly. Costs ~$0.005/conversation on Haiku.
  Use when you don't have a coding-agent session handy or want batch automation.

- ``dry-run``: write raw + stub summary with explicit "skipped, not coming back"
  copy. No API call, no agent expected. Use to smoke-test installation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import click

from sbo_ingestion import audit
from sbo_ingestion.dual_write import DualWriteResult, write_index, write_pair
from sbo_ingestion.handlers import chatgpt as chatgpt_handler
from sbo_ingestion.handlers import claude_ai as claude_ai_handler
from sbo_ingestion.handlers import memories as memories_handler
from sbo_ingestion.summarize import Summary, summarize


Mode = Literal["agent", "api", "dry-run"]
DEFAULT_MODE: Mode = "agent"


def _agent_stub_summary(convo) -> Summary:  # type: ignore[no-untyped-def]
    """Stub Summary written in agent mode. The /distill-inbox agent fills the real one."""
    return Summary(
        title=convo.title or "(untitled conversation)",
        tldr=(
            "(agent-mode: summary pending. Run `/distill-inbox` in Claude Code "
            "— or the equivalent prompt in ChatGPT / Cursor / Codex / Gemini "
            "— to fill this stub. The raw conversation is at the path in "
            "frontmatter `private_file`.)"
        ),
        insights=(),
        decisions=(),
        open_questions=(
            "Run /distill-inbox to surface real insights, decisions, and open questions.",
        ),
        people_mentioned=(),
        suggested_destinations=(),
    )


def _dry_run_summary(convo) -> Summary:  # type: ignore[no-untyped-def]
    """Stub Summary written in dry-run mode. No follow-up expected."""
    return Summary(
        title=convo.title or "(untitled conversation)",
        tldr=(
            "(dry-run: summarization skipped; raw conversation written to private/ "
            "and a stub written to brain/_inbox/. Re-ingest with --mode agent (or "
            "--mode api) to produce a real summary.)"
        ),
        insights=(),
        decisions=(),
        open_questions=("Re-ingest with --mode agent to surface real insights.",),
        people_mentioned=(),
        suggested_destinations=(),
    )


def _detect_format(path: Path) -> str:
    """Detect export format from file extension and content shape."""
    if path.suffix == ".jsonl":
        return "claude.ai"
    if path.suffix == ".json":
        try:
            with path.open("r", encoding="utf-8") as f:
                head = f.read(2048)
            if head.lstrip().startswith("["):
                return "chatgpt"
            if "chat_messages" in head:
                return "claude.ai"
        except Exception:
            pass
    raise ValueError(
        f"Unknown export format: {path}. Expected .jsonl (Claude.ai) "
        f"or .json (ChatGPT conversations.json)."
    )


def _resolve_mode(
    mode: Mode | None,
    *,
    dry_run: bool,
    api_key: str,
) -> Mode:
    """Resolve the effective mode from explicit --mode + legacy flags.

    Precedence: explicit ``mode`` wins. Otherwise ``--dry-run`` implies dry-run,
    ``--api-key`` (without dry-run) implies api, fallback is DEFAULT_MODE (agent).
    """
    if mode is not None:
        return mode
    if dry_run:
        return "dry-run"
    if api_key:
        return "api"
    return DEFAULT_MODE


def _find_memories(export_path: Path, memories_path: Path | None) -> Path | None:
    """Resolve the memories.json to ingest: explicit path wins, else auto-detect
    a ``memories.json`` sibling next to the conversations export. Returns None if
    neither is present."""
    if memories_path is not None:
        return memories_path if memories_path.exists() else None
    sibling = export_path.parent / "memories.json"
    return sibling if sibling.exists() else None


def ingest(
    export_path: Path,
    *,
    brain_root: Path,
    private_root: Path,
    api_key: str = "",
    mode: Mode | None = None,
    dry_run: bool = False,
    memories_path: Path | None = None,
) -> list[DualWriteResult]:
    """Ingest one export file. Returns list of dual-write results.

    Mode resolution:
      - explicit ``mode`` wins
      - else ``dry_run=True`` -> "dry-run"
      - else ``api_key`` non-empty -> "api"
      - else default "agent"

    Also emits a newest-first ``_INDEX.md`` corpus map per platform, and — if a
    ``memories.json`` is given via ``memories_path`` or auto-detected next to the
    export — a high-signal ``_memory-export.md``.

    Writes an entry to ``private_root/_distill/audit.jsonl`` for every
    conversation processed. The audit log lives inside the private vault and
    is never read by MCP.
    """
    effective_mode = _resolve_mode(mode, dry_run=dry_run, api_key=api_key)

    if effective_mode == "api" and not api_key:
        raise ValueError("api_key is required when mode='api'.")

    fmt = _detect_format(export_path)
    if fmt == "claude.ai":
        convos = list(claude_ai_handler.parse_export(export_path))
    elif fmt == "chatgpt":
        convos = list(chatgpt_handler.parse_export(export_path))
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    results: list[DualWriteResult] = []
    for convo in convos:
        if effective_mode == "api":
            summary = summarize(convo, api_key=api_key)
        elif effective_mode == "dry-run":
            summary = _dry_run_summary(convo)
        else:  # agent
            summary = _agent_stub_summary(convo)

        result = write_pair(
            convo, summary, brain_root=brain_root, private_root=private_root
        )
        # Stamp status: needs-summary for agent mode (the rest stay "triage")
        if effective_mode == "agent":
            _mark_needs_summary(result.brain_path)

        audit.record_ingest(
            private_root,
            conversation_id=convo.uuid,
            mode=effective_mode,
            fmt=fmt,
            raw_path=result.private_path,
            brain_path=result.brain_path,
            private_root_for_rel=private_root,
            brain_root_for_rel=brain_root,
        )
        results.append(result)

    # Corpus map: newest-first {date, title, summary} table per platform.
    if convos:
        write_index(convos, brain_root=brain_root, platform=convos[0].platform)

    # High-signal memory export, if the source export shipped a memories.json.
    found = _find_memories(export_path, memories_path)
    if found is not None:
        platform = convos[0].platform if convos else fmt
        memories_handler.write_memory_export(found, brain_root=brain_root, platform=platform)

    return results


def _mark_needs_summary(brain_path: Path) -> None:
    """Update brain file frontmatter to set status=needs-summary.

    Called only for agent-mode ingests. The /distill-inbox agent looks for this
    marker to know which inbox items are waiting for distillation.
    """
    import frontmatter  # local import keeps import-time light

    post = frontmatter.load(brain_path)
    post["status"] = "needs-summary"
    # Tag for inbox filtering in Obsidian
    tags = list(post.get("tags", []) or [])
    if "needs-summary" not in tags:
        tags.append("needs-summary")
    if "needs-triage" in tags:
        tags.remove("needs-triage")
    post["tags"] = tags
    brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")


@click.command()
@click.argument("export_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--brain-root",
    type=click.Path(path_type=Path),
    envvar="SBO_BRAIN_VAULT_ROOT",
    required=True,
    help="Path to your brain/ vault. Default: $SBO_BRAIN_VAULT_ROOT env var.",
)
@click.option(
    "--private-root",
    type=click.Path(path_type=Path),
    envvar="SBO_PRIVATE_VAULT_ROOT",
    required=True,
    help="Path to your private/ vault. Default: $SBO_PRIVATE_VAULT_ROOT env var.",
)
@click.option(
    "--mode",
    "mode_flag",
    type=click.Choice(["agent", "api", "dry-run"], case_sensitive=False),
    default=None,
    help=(
        "Ingestion mode. Default: 'agent' (recommended). "
        "'agent' writes raw + stub; you fill the stub via /distill-inbox in any "
        "coding-agent session — no extra API cost. "
        "'api' calls Anthropic directly (~$0.005/convo on Haiku). "
        "'dry-run' writes stubs with no follow-up expected; for smoke-testing."
    ),
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default="",
    help="Anthropic API key. Default: $ANTHROPIC_API_KEY env var. "
    "If set without --mode, implies --mode api.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Legacy alias for --mode dry-run. Kept for back-compat.",
)
@click.option(
    "--memories",
    "memories_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to the export's memories.json (the AI's cross-conversation memory). "
    "If omitted, a memories.json sibling next to EXPORT_PATH is auto-detected.",
)
def cli(
    export_path: Path,
    brain_root: Path,
    private_root: Path,
    mode_flag: str | None,
    api_key: str,
    dry_run: bool,
    memories_path: Path | None,
) -> None:
    """Ingest an AI chat export into your SBO vaults."""
    if not brain_root.exists():
        click.echo(f"[error] brain vault not found at {brain_root}", err=True)
        sys.exit(1)
    if not private_root.exists():
        click.echo(f"[error] private vault not found at {private_root}", err=True)
        sys.exit(1)

    effective_mode = _resolve_mode(
        mode_flag,  # type: ignore[arg-type]
        dry_run=dry_run,
        api_key=api_key,
    )

    if effective_mode == "api" and not api_key:
        click.echo(
            "[error] mode=api requires --api-key (or $ANTHROPIC_API_KEY)",
            err=True,
        )
        sys.exit(1)

    click.echo(f"[sbo] ingesting {export_path}")
    click.echo(f"[sbo] brain:   {brain_root}")
    click.echo(f"[sbo] private: {private_root}")
    click.echo(f"[sbo] mode:    {effective_mode}")
    if effective_mode == "agent":
        click.echo("[sbo] AGENT mode: stubs written. Run /distill-inbox in your coding-agent.")
    elif effective_mode == "dry-run":
        click.echo("[sbo] DRY-RUN: no API call; stub summaries; no follow-up expected.")

    results = ingest(
        export_path,
        brain_root=brain_root,
        private_root=private_root,
        api_key=api_key,
        mode=effective_mode,
        memories_path=memories_path,
    )
    click.echo(f"[sbo] wrote {len(results)} conversation pairs")
    for r in results:
        click.echo(f"  raw:     {r.private_path}")
        click.echo(f"  summary: {r.brain_path}")
    click.echo(f"[sbo] audit:   {private_root}/_distill/audit.jsonl")


if __name__ == "__main__":
    cli()
