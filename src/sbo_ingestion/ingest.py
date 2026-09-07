"""Ingestion orchestrator. CLI entry point.

Three modes:

- ``agent`` (default): write raw + stub summary with ``status: needs-summary``.
  No Anthropic API call. A coding-agent session (Claude Code, Cursor, Codex,
  ChatGPT, Gemini CLI) is expected to fill the stub later via ``/distill-inbox``.
  This is the recommended mode: it uses the reasoning loop you've already paid
  for, produces better cross-referenced summaries, and stays inspectable.

- ``api``: call the Anthropic API directly. Costs ~$0.005/conversation on Haiku.
  Only ever selected by an explicit ``--mode api`` — a stray ``ANTHROPIC_API_KEY``
  in the environment must never move a user onto a paid path.

- ``dry-run``: write raw + stub summary with explicit "skipped, not coming back"
  copy. No API call, no agent expected. Use to smoke-test installation.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Literal

import click
from anthropic import AnthropicError

from sbo_ingestion import audit
from sbo_ingestion.dual_write import (
    DualWriteResult,
    _atomic_write_text,
    index_existing_brain_paths,
    write_index,
    write_pair,
)
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


EXPORT_SUFFIXES = (".json", ".jsonl")
_DETECT_HEAD_CHARS = 65536


def _detect_format(path: Path) -> str:
    """Detect export format from file extension and provenance keys.

    Both platforms ship ``.json`` arrays, so shape alone cannot discriminate.
    Claude.ai conversations carry ``chat_messages``; ChatGPT conversations carry
    a ``mapping`` tree. Testing shape first routed every array-shaped Claude
    export into the ChatGPT handler, where it died on the missing key.
    """
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return "claude.ai"
    if suffix == ".zip":
        if chatgpt_handler.conversation_members(path):
            return "chatgpt"
        raise ValueError(f"No ChatGPT conversation members found in ZIP export: {path}")
    if suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            head = f.read(_DETECT_HEAD_CHARS)
        if '"chat_messages"' in head:
            return "claude.ai"
        if '"mapping"' in head:
            return "chatgpt"
    raise ValueError(
        f"Unknown export format: {path}. Expected .jsonl (Claude.ai), .json "
        f"containing 'chat_messages' (Claude.ai) or 'mapping' (ChatGPT), "
        f"or an official ChatGPT export .zip."
    )


def _resolve_export_paths(export_path: Path) -> list[Path]:
    """Expand a file, a directory, or a glob into a sorted list of export files.

    Modern ChatGPT exports ship sharded as ``conversations-000.json`` …
    ``conversations-053.json``; zero-padded names sort into shard order.
    """
    if export_path.is_file():
        return [export_path]
    if export_path.is_dir():
        candidates = list(export_path.iterdir())
    else:
        candidates = list(export_path.parent.glob(export_path.name))
    paths = sorted(p for p in candidates if p.is_file() and p.suffix in EXPORT_SUFFIXES)
    if not paths:
        raise ValueError(f"No .json or .jsonl export files found at {export_path}")
    return paths


def _resolve_mode(mode: Mode | None, *, dry_run: bool) -> Mode:
    """Resolve the effective mode from explicit --mode + the legacy --dry-run flag.

    Precedence: explicit ``mode`` wins, then ``--dry-run``, then DEFAULT_MODE.
    A present API key is deliberately not part of this: ``api`` is a paid path and
    only an explicit ``--mode api`` may select it.
    """
    if mode is not None:
        return mode
    if dry_run:
        return "dry-run"
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
    """Ingest an export file, a directory of shards, or a glob.

    Sharded exports are processed in sorted order as a single run; results and
    audit entries accumulate across shards.

    Mode resolution:
      - explicit ``mode`` wins
      - else ``dry_run=True`` -> "dry-run"
      - else default "agent"

    Also emits a newest-first ``_INDEX.md`` corpus map per platform, and — if a
    ``memories.json`` is given via ``memories_path`` or auto-detected next to the
    export — a high-signal ``_memory-export.md``.

    Writes an entry to ``private_root/_distill/audit.jsonl`` for every
    conversation processed. The audit log lives inside the private vault and
    is never read by MCP.
    """
    effective_mode = _resolve_mode(mode, dry_run=dry_run)

    if effective_mode == "api" and not api_key:
        raise ValueError("api_key is required when mode='api'.")

    results: list[DualWriteResult] = []
    for path in _resolve_export_paths(export_path):
        results.extend(
            _ingest_file(
                path,
                brain_root=brain_root,
                private_root=private_root,
                api_key=api_key,
                effective_mode=effective_mode,
                memories_path=memories_path,
            )
        )
    return results


def _ingest_file(
    export_path: Path,
    *,
    brain_root: Path,
    private_root: Path,
    api_key: str,
    effective_mode: Mode,
    memories_path: Path | None = None,
) -> list[DualWriteResult]:
    """Ingest a single export file with an already-resolved mode."""
    fmt = _detect_format(export_path)
    if fmt == "claude.ai":
        convos = claude_ai_handler.parse_export(export_path)
        selected_members = (export_path.name,)
    elif fmt == "chatgpt":
        convos = chatgpt_handler.parse_export(export_path)
        selected_members = (
            chatgpt_handler.conversation_members(export_path)
            if export_path.suffix.lower() == ".zip"
            else (export_path.name,)
        )
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    results: list[DualWriteResult] = []
    index_convos = []
    platform = fmt
    existing_brain_paths = index_existing_brain_paths(
        brain_root=brain_root,
        platform=fmt,
    )
    for convo in convos:
        platform = convo.platform
        if effective_mode == "api":
            summary = summarize(convo, api_key=api_key)
        elif effective_mode == "dry-run":
            summary = _dry_run_summary(convo)
        else:  # agent
            summary = _agent_stub_summary(convo)

        result = write_pair(
            convo,
            summary,
            brain_root=brain_root,
            private_root=private_root,
            existing_brain_paths=existing_brain_paths,
        )
        # Stamp status: needs-summary for agent mode (the rest stay "triage")
        if effective_mode == "agent" and not result.brain_preserved:
            _mark_needs_summary(result.brain_path, brain_root=brain_root)

        audit.record_ingest(
            private_root,
            conversation_id=convo.uuid,
            mode=effective_mode,
            fmt=fmt,
            raw_path=result.private_path,
            brain_path=result.brain_path,
            source=export_path.name,
            brain_preserved=result.brain_preserved,
            private_root_for_rel=private_root,
            brain_root_for_rel=brain_root,
        )
        results.append(result)
        # Keep only index metadata. Message bodies may be gigabytes across a full
        # export and have already been written to the private vault.
        index_convos.append(replace(convo, messages=()))

    # Corpus map: newest-first {date, title, summary} table per platform.
    if index_convos:
        write_index(index_convos, brain_root=brain_root, platform=platform)

    # High-signal memory export, if the source export shipped a memories.json.
    found = _find_memories(export_path, memories_path)
    if found is not None:
        memories_handler.write_memory_export(found, brain_root=brain_root, platform=platform)

    preserved_count = sum(result.brain_preserved for result in results)
    audit.record_import_receipt(
        private_root,
        source_name=export_path.name,
        source_size=export_path.stat().st_size,
        fmt=fmt,
        selected_members=selected_members,
        conversation_count=len(results),
        brain_created=len(results) - preserved_count,
        brain_preserved=preserved_count,
    )

    return results


def _mark_needs_summary(brain_path: Path, *, brain_root: Path) -> None:
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
    _atomic_write_text(brain_path, frontmatter.dumps(post), root=brain_root)


@click.command()
@click.argument("export_paths", nargs=-1, type=click.Path(path_type=Path))
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
        "'api' calls Anthropic directly (~$0.005/convo on Haiku); it is never "
        "selected implicitly, pass it explicitly. "
        "'dry-run' writes stubs with no follow-up expected; for smoke-testing."
    ),
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default="",
    help="Anthropic API key, used only by --mode api. "
    "Default: $ANTHROPIC_API_KEY env var. Setting it does not enable api mode.",
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
    export_paths: tuple[Path, ...],
    brain_root: Path,
    private_root: Path,
    mode_flag: str | None,
    api_key: str,
    dry_run: bool,
    memories_path: Path | None,
) -> None:
    """Ingest AI chat exports into your SBO vaults.

    EXPORT_PATHS are files, directories, or globs. Sharded exports
    (conversations-000.json ... conversations-053.json) are processed in
    sorted order as one run.
    """
    if not export_paths:
        click.echo("[error] no export path given", err=True)
        sys.exit(1)
    if not brain_root.exists():
        click.echo(f"[error] brain vault not found at {brain_root}", err=True)
        sys.exit(1)
    if not private_root.exists():
        click.echo(f"[error] private vault not found at {private_root}", err=True)
        sys.exit(1)

    effective_mode = _resolve_mode(
        mode_flag,  # type: ignore[arg-type]
        dry_run=dry_run,
    )

    if effective_mode == "api" and not api_key:
        click.echo(
            "[error] mode=api requires --api-key (or $ANTHROPIC_API_KEY)",
            err=True,
        )
        sys.exit(1)

    try:
        files = [f for p in export_paths for f in _resolve_export_paths(p)]
    except ValueError as e:
        click.echo(f"[error] {e}", err=True)
        sys.exit(1)

    click.echo(f"[sbo] ingesting {len(files)} file(s)")
    click.echo(f"[sbo] brain:   {brain_root}")
    click.echo(f"[sbo] private: {private_root}")
    click.echo(f"[sbo] mode:    {effective_mode}")
    if effective_mode == "agent":
        click.echo("[sbo] AGENT mode: stubs written. Run /distill-inbox in your coding-agent.")
    elif effective_mode == "dry-run":
        click.echo("[sbo] DRY-RUN: no API call; stub summaries; no follow-up expected.")

    results: list[DualWriteResult] = []
    try:
        for path in files:
            results.extend(
                ingest(
                    path,
                    brain_root=brain_root,
                    private_root=private_root,
                    api_key=api_key,
                    mode=effective_mode,
                    memories_path=memories_path,
                )
            )
    except AnthropicError as e:
        click.echo(f"[error] Anthropic API call failed: {e}", err=True)
        sys.exit(1)
    click.echo(f"[sbo] wrote {len(results)} conversation pairs")
    for r in results:
        click.echo(f"  raw:     {r.private_path}")
        click.echo(f"  summary: {r.brain_path}")
    click.echo(f"[sbo] audit:   {private_root}/_distill/audit.jsonl")


if __name__ == "__main__":
    cli()
