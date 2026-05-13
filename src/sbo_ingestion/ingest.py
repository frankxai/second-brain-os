"""Ingestion orchestrator. CLI entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from sbo_ingestion.dual_write import DualWriteResult, write_pair
from sbo_ingestion.handlers import chatgpt as chatgpt_handler
from sbo_ingestion.handlers import claude_ai as claude_ai_handler
from sbo_ingestion.summarize import summarize


def _detect_format(path: Path) -> str:
    """Detect export format from file extension and content shape."""
    if path.suffix == ".jsonl":
        return "claude.ai"
    if path.suffix == ".json":
        # Could be ChatGPT conversations.json OR a single Claude.ai conversation
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


def ingest(
    export_path: Path,
    *,
    brain_root: Path,
    private_root: Path,
    api_key: str,
) -> list[DualWriteResult]:
    """Ingest one export file. Returns list of dual-write results."""
    fmt = _detect_format(export_path)
    if fmt == "claude.ai":
        convos = list(claude_ai_handler.parse_export(export_path))
    elif fmt == "chatgpt":
        convos = list(chatgpt_handler.parse_export(export_path))
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    results: list[DualWriteResult] = []
    for convo in convos:
        summary = summarize(convo, api_key=api_key)
        result = write_pair(
            convo, summary, brain_root=brain_root, private_root=private_root
        )
        results.append(result)
    return results


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
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    required=True,
    help="Anthropic API key. Default: $ANTHROPIC_API_KEY env var.",
)
def cli(export_path: Path, brain_root: Path, private_root: Path, api_key: str) -> None:
    """Ingest an AI chat export into your SBO vaults."""
    if not brain_root.exists():
        click.echo(f"[error] brain vault not found at {brain_root}", err=True)
        sys.exit(1)
    if not private_root.exists():
        click.echo(f"[error] private vault not found at {private_root}", err=True)
        sys.exit(1)
    click.echo(f"[sbo] ingesting {export_path}")
    click.echo(f"[sbo] brain: {brain_root}")
    click.echo(f"[sbo] private: {private_root}")
    results = ingest(
        export_path, brain_root=brain_root, private_root=private_root, api_key=api_key
    )
    click.echo(f"[sbo] wrote {len(results)} conversation pairs")
    for r in results:
        click.echo(f"  raw:     {r.private_path}")
        click.echo(f"  summary: {r.brain_path}")


if __name__ == "__main__":
    cli()
