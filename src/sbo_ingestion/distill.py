"""CLI support for `/distill-inbox`.

The distill step runs inside a coding-agent session rather than in Python: the
agent reads a stub, opens the raw conversation it points at, writes a real
summary back, and marks the stub done. That design is what makes distillation
use the active agent's context without making a separate paid API call.

It leaves two things that must not be left to the agent's discretion. Finding
the stubs that still need work is fiddly frontmatter parsing, and recording the
audit event is the kind of bookkeeping an agent skips when a run gets long. Both
live here. Completion first saves the note atomically, then records an idempotent
audit event. A marker on the note makes an interrupted audit recoverable on retry.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import click
import frontmatter

from sbo_ingestion import audit
from sbo_ingestion import distill_packet

NEEDS_SUMMARY = "needs-summary"
# Frontmatter sits at the top of the file; this is generous for it.
FRONTMATTER_PEEK = 2048
DONE_STATUS = "triage"
PENDING_RECEIPT = "distill_pending_receipt"


def find_stubs(brain_root: Path, *, limit: int = 0) -> list[dict]:
    """Stubs still awaiting a summary, with the private file each one points at.

    Cheap-checks each file before parsing it. Full YAML parsing of every stub took
    250s across a real 5,311-conversation vault — long enough that listing the work
    cost more than doing a batch of it. Most files are already distilled, and a
    substring test rules them out without a parser.
    """
    inbox = brain_root / "_inbox"
    if not inbox.exists():
        return []

    needle = f"status: {NEEDS_SUMMARY}"
    pending = []
    for path in sorted(inbox.rglob("*.md")):
        with path.open("r", encoding="utf-8") as handle:
            head = handle.read(FRONTMATTER_PEEK)
        if needle not in head and PENDING_RECEIPT not in head:
            continue
        post = frontmatter.load(path)
        if post.get("status") != NEEDS_SUMMARY and not post.get(PENDING_RECEIPT):
            continue
        pending.append(
            {
                "stub": str(path),
                "conversation_id": post.get("conversation_id", ""),
                "private_file": post.get("private_file", ""),
                "title": post.get("title") or path.stem,
                "receipt_pending": bool(post.get(PENDING_RECEIPT)),
            }
        )
        if limit and len(pending) >= limit:
            break
    return pending


def complete_stub(stub_path: Path, private_root: Path, *, agent: str, model: str = "",
                  source_sha256: str = "") -> Path:
    """Save the note before its receipt, recovering interrupted work on retry."""
    stub_path = stub_path.resolve()
    private_root = private_root.resolve()
    with audit.exclusive_lock(stub_path.with_suffix(".distill.lock")):
        if source_sha256:
            distill_packet.require_complete_coverage(stub_path, private_root, source_sha256)
        post = frontmatter.load(stub_path)
        pending = post.get(PENDING_RECEIPT)
        digest = sha256(post.content.encode("utf-8")).hexdigest()
        vault_digest = sha256(str(private_root).encode("utf-8")).hexdigest()
        if pending:
            string_fields = {"completion_id", "conversation_id", "agent", "model",
                             "summary_sha256", "private_root_sha256"}
            if (not isinstance(pending, dict)
                    or set(pending) != string_fields | {"summary_chars"}
                    or any(not isinstance(pending.get(key), str) for key in string_fields)
                    or type(pending.get("summary_chars")) is not int
                    or pending["summary_chars"] < 0
                    or not pending["completion_id"]):
                raise click.ClickException("Invalid pending completion marker; restore the note before retrying")
            if (post.get("status") != DONE_STATUS
                    or pending["summary_sha256"] != digest
                    or pending["private_root_sha256"] != vault_digest
                    or pending["conversation_id"] != str(post.get("conversation_id", ""))):
                raise click.ClickException("Pending completion changed; restore its note and vault before retrying")
        else:
            if post.get("status") != NEEDS_SUMMARY:
                raise click.ClickException(f"{stub_path.name} is not awaiting a summary")
            pending = {
                "completion_id": uuid4().hex,
                "conversation_id": str(post.get("conversation_id", "")),
                "agent": agent,
                "model": model,
                "summary_chars": len(post.content),
                "summary_sha256": digest,
                "private_root_sha256": vault_digest,
            }
            post[PENDING_RECEIPT] = pending
            if source_sha256:
                post["distill_source_sha256"] = source_sha256
                post["distill_source_coverage"] = "complete"
            post["status"] = DONE_STATUS
            tags = [t for t in (post.get("tags") or []) if t != NEEDS_SUMMARY]
            post["tags"] = tags or ["triage"]
            audit.atomic_write_text(stub_path, frontmatter.dumps(post))

        receipt = audit.record_distill(
            private_root,
            **{key: value for key, value in pending.items()
               if key not in {"summary_sha256", "private_root_sha256"}},
        )
        del post[PENDING_RECEIPT]
        audit.atomic_write_text(stub_path, frontmatter.dumps(post))
        return receipt


@click.group()
def cli() -> None:
    """Support commands for the /distill-inbox agent workflow."""


@cli.command("list")
@click.option(
    "--brain-root",
    envvar="SBO_BRAIN_VAULT_ROOT",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option("--limit", type=int, default=0, help="Cap the number returned; 0 means all.")
def list_pending(brain_root: Path, limit: int) -> None:
    """Print stubs awaiting a summary as JSON, newest last."""
    click.echo(json.dumps(find_stubs(brain_root, limit=limit), indent=2))


@cli.command("complete")
@click.argument("stub", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--private-root",
    envvar="SBO_PRIVATE_VAULT_ROOT",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option("--agent", required=True, help="Which agent distilled it, e.g. claude-code.")
@click.option("--model", default="", help="Model name, when the agent knows it.")
@click.option("--source-sha256", default="", help="Require complete packet coverage of this unchanged source.")
def complete(stub: Path, private_root: Path, agent: str, model: str, source_sha256: str) -> None:
    """Flip a stub to distilled and append its audit event."""
    try:
        receipt = complete_stub(stub, private_root, agent=agent, model=model, source_sha256=source_sha256)
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"[sbo] distilled {stub.name} -> {receipt}")


@cli.command("plan")
@click.option("--brain-root", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--private-root", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--max-notes", type=click.IntRange(1, 10), default=3)
@click.option("--source-budget", type=click.IntRange(256, 128_000), default=18_000)
def plan(brain_root: Path, private_root: Path, max_notes: int, source_budget: int) -> None:
    """Select a small metadata-only distillation batch; large sources stay pending."""
    click.echo(json.dumps(distill_packet.plan_batch(find_stubs(brain_root, limit=100),
                     private_root, max_notes=max_notes, source_budget=source_budget), separators=(",", ":")))


@cli.command("packet")
@click.argument("stub", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--brain-root", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--private-root", required=True, type=click.Path(file_okay=False, path_type=Path))
@click.option("--offset", type=click.IntRange(min=0), default=0)
@click.option("--max-bytes", type=click.IntRange(256, 32_000), default=6000)
@click.option("--source-sha256", default="")
def packet_command(stub: Path, brain_root: Path, private_root: Path, offset: int,
                   max_bytes: int, source_sha256: str) -> None:
    """Read one bounded private source packet locally; never expose this through MCP."""
    try:
        result = distill_packet.packet(stub, brain_root=brain_root, private_root=private_root,
                   offset=offset, max_bytes=max_bytes, expected_sha256=source_sha256)
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


if __name__ == "__main__":
    cli()
