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

import json
import os
import re
import sys
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Literal, cast
from uuid import uuid4

import click
import frontmatter
from anthropic import AnthropicError
from yaml import YAMLError

from sbo_ingestion import audit
from sbo_ingestion.handlers.claude_ai import Conversation
from sbo_ingestion.dual_write import (
    DualWriteResult,
    _assert_descendant,
    _atomic_write_text,
    _date_from,
    _now_iso,
    _render_brain_body,
    index_existing_brain_paths,
    write_index,
    write_pair,
)
from sbo_ingestion.handlers import chatgpt as chatgpt_handler
from sbo_ingestion.handlers import claude_ai as claude_ai_handler
from sbo_ingestion.handlers import idea_capture as idea_capture_handler
from sbo_ingestion.handlers import kura as kura_handler
from sbo_ingestion.handlers import memories as memories_handler
from sbo_ingestion.summarize import Summary, summarize

Mode = Literal["agent", "api", "dry-run"]
DEFAULT_MODE: Mode = "agent"


class CaptureBatchError(ValueError):
    """A bounded capture batch completed its healthy inputs before failing."""

    def __init__(self, failures: list[str], results: list[DualWriteResult]):
        super().__init__(
            "Capture failures after processing healthy inputs:\n" + "\n".join(failures)
        )
        self.results = results
        self.failures = failures


def _assert_capture_path(path: Path, root: Path) -> None:
    """Reject capture paths outside the boundary or through symbolic links."""
    try:
        _assert_descendant(path, root)
        relative = path.absolute().relative_to(root.absolute())
    except ValueError:
        raise ValueError("Idea capture path escapes its boundary") from None
    if ".." in relative.parts:
        raise ValueError("Idea capture path contains traversal")
    candidate = root.absolute()
    for component in (None, *relative.parts):
        if component is not None:
            candidate /= component
        if candidate.is_symlink():
            raise ValueError("Idea capture paths cannot contain symlinks")


def _read_capture_bytes(path: Path, *, root: Path) -> bytes:
    """Bound reads of saved raw packets and receipts before retrying intake."""
    _assert_capture_path(path, root)
    limit = idea_capture_handler.MAX_IDEA_CAPTURE_SIZE
    try:
        if not path.is_file():
            raise ValueError("Private capture file must be a regular file")
        if path.stat().st_size > limit:
            raise ValueError("Private capture file exceeds size limit")
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        raise ValueError("Private capture file cannot be read") from None
    if len(data) > limit:
        raise ValueError("Private capture file exceeds size limit")
    return data


def _capture_brain_paths(brain_root: Path) -> dict[str, Path]:
    """Find capture notes without reading through links or oversized files."""
    _assert_capture_path(brain_root, brain_root)
    if not brain_root.exists():
        return {}
    indexed: dict[str, Path] = {}
    for path in brain_root.rglob("*.md"):
        if path.name == "_INDEX.md":
            continue
        if any(part.startswith(".") for part in path.relative_to(brain_root).parts):
            continue
        data = _read_capture_bytes(path, root=brain_root)
        try:
            post = frontmatter.loads(data.decode("utf-8"))
        except (UnicodeError, YAMLError):
            raise ValueError("Invalid brain note during capture indexing") from None
        if post.get("source") != "idea-capture":
            continue
        identity = post.get("conversation_id")
        if not isinstance(identity, str) or re.fullmatch(r"idea-[0-9a-f]{16}", identity) is None:
            raise ValueError("Invalid idea capture note identity")
        if identity in indexed:
            raise ValueError("Duplicate idea capture brain notes")
        indexed[identity] = path
    return indexed


def _atomic_write_bytes(path: Path, data: bytes, *, root: Path) -> None:
    """Publish a capture without replacing another writer's private bytes."""
    _assert_capture_path(path, root)
    if path.is_symlink():
        raise ValueError("Private capture path cannot be a symlink")
    if path.exists():
        if not path.is_file() or _read_capture_bytes(path, root=root) != data:
            raise FileExistsError("Conflicting private capture bytes; preserve both inputs")
        return
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    _assert_capture_path(temporary, root)
    try:
        with temporary.open("xb") as handle:
            os.chmod(temporary, 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _assert_capture_path(path, root)
        try:
            os.link(temporary, path)
        except FileExistsError:
            _assert_capture_path(path, root)
            if (
                path.is_symlink()
                or not path.is_file()
                or _read_capture_bytes(path, root=root) != data
            ):
                raise FileExistsError(
                    "Conflicting private capture bytes; preserve both inputs"
                ) from None
    finally:
        temporary.unlink(missing_ok=True)


def _agent_stub_summary(convo: Conversation) -> Summary:
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


def _dry_run_summary(convo: Conversation) -> Summary:
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
    if suffix == ".md" and path.name == "conversation.md":
        return "kura"
    if suffix == ".jsonl":
        return "claude.ai"
    if suffix == ".zip":
        if chatgpt_handler.conversation_members(path):
            return "chatgpt"
        raise ValueError(f"No ChatGPT conversation members found in ZIP export: {path}")
    if suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            head = f.read(_DETECT_HEAD_CHARS)
        if '"rawText"' in head and '"version"' in head and '"tags"' in head:
            return "idea-capture"
        if '"chat_messages"' in head:
            return "claude.ai"
        if '"mapping"' in head:
            return "chatgpt"
    raise ValueError(
        f"Unknown export format: {path}. Expected .jsonl (Claude.ai), .json "
        f"containing 'chat_messages' (Claude.ai) or 'mapping' (ChatGPT), "
        f"or an official ChatGPT export .zip."
    )


def _resolve_export_paths(export_path: Path, failures: list[str] | None = None) -> list[Path]:
    """Expand a file, a directory, or a glob into a sorted list of export files.

    Modern ChatGPT exports ship sharded as ``conversations-000.json`` …
    ``conversations-053.json``; zero-padded names sort into shard order.
    """
    if export_path.is_file():
        return [export_path]
    if export_path.is_dir():
        discovery_failures: list[str] | None = [] if failures is not None else None
        captures = kura_handler.discover(export_path, discovery_failures)
        if discovery_failures and failures is not None:
            failures.extend(discovery_failures)
        if captures or discovery_failures:
            return captures
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
    format: str | None = None,
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
    brain, private = brain_root.resolve(), private_root.resolve()
    if brain.is_relative_to(private) or private.is_relative_to(brain):
        raise ValueError("Brain and private vaults must be separate, non-overlapping roots")

    if effective_mode == "api" and not api_key:
        raise ValueError("api_key is required when mode='api'.")

    normalized_fmt = format.lower().replace("_", "-") if format else None
    if normalized_fmt == "idea-capture":
        if effective_mode != "agent":
            raise ValueError("idea-capture format requires agent mode")
        capture_indexes: dict[str, dict[str, Path]] = {}
        return _ingest_idea_capture(
            export_path,
            brain_root=brain_root,
            private_root=private_root,
            effective_mode=effective_mode,
            brain_indexes=capture_indexes,
        )

    results: list[DualWriteResult] = []
    brain_indexes: dict[str, dict[str, Path]] = {}
    failures: list[str] = []
    for path in _resolve_export_paths(export_path, failures):
        try:
            results.extend(_ingest_file(
                path,
                brain_root=brain_root,
                private_root=private_root,
                api_key=api_key,
                effective_mode=effective_mode,
                memories_path=memories_path,
                brain_indexes=brain_indexes,
                format=format,
            ))
        except (ValueError, OSError) as error:
            if path.name != "conversation.md":
                raise
            failures.append(f"{path}: {error}")
    if failures:
        raise CaptureBatchError(failures, results)
    return results


def _ingest_file(
    export_path: Path,
    *,
    brain_root: Path,
    private_root: Path,
    api_key: str,
    effective_mode: Mode,
    memories_path: Path | None = None,
    brain_indexes: dict[str, dict[str, Path]] | None = None,
    format: str | None = None,
) -> list[DualWriteResult]:
    """Ingest a single export file with an already-resolved mode."""
    normalized_fmt = format.lower().replace("_", "-") if format else None
    if normalized_fmt == "idea-capture":
        return _ingest_idea_capture(
            export_path,
            brain_root=brain_root,
            private_root=private_root,
            effective_mode=effective_mode,
            brain_indexes=brain_indexes,
        )

    fmt = normalized_fmt or _detect_format(export_path)
    if fmt == "kura":
        return _ingest_kura_capture(export_path, brain_root=brain_root, private_root=private_root,
                                    api_key=api_key, effective_mode=effective_mode,
                                    brain_indexes=brain_indexes)
    if fmt == "idea-capture":
        return _ingest_idea_capture(export_path, brain_root=brain_root, private_root=private_root,
                                    effective_mode=effective_mode, brain_indexes=brain_indexes)
    selected_members: tuple[str, ...]
    if fmt == "claude.ai":
        convos = claude_ai_handler.parse_export(export_path)
        selected_members = (export_path.name,)
    elif fmt == "chatgpt":
        convos = chatgpt_handler.parse_export(export_path)
        if export_path.suffix.lower() == ".zip":
            selected_members = tuple(chatgpt_handler.conversation_members(export_path))
        else:
            selected_members = (export_path.name,)
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
        if effective_mode == "api" and convo.uuid not in existing_brain_paths:
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


def _ingest_idea_capture(
    export_path: Path,
    *,
    brain_root: Path,
    private_root: Path,
    effective_mode: Mode,
    brain_indexes: dict[str, dict[str, Path]] | None = None,
) -> list[DualWriteResult]:
    """Ingest a single explicit idea-capture JSON packet."""
    if effective_mode != "agent":
        raise ValueError("idea-capture format requires agent mode")

    _assert_capture_path(export_path, export_path.parent)
    obj, raw_bytes = idea_capture_handler.read_and_validate_packet(export_path)
    semantic_id = idea_capture_handler.compute_semantic_identity(obj)
    convo = idea_capture_handler.create_idea_conversation(obj, semantic_id)

    receipt_dir = private_root / "_distill" / "idea-capture"
    _assert_capture_path(receipt_dir, private_root)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{convo.uuid}.json"
    _assert_capture_path(receipt_path, private_root)
    lock_path = receipt_path.with_suffix(".lock")
    _assert_capture_path(lock_path, private_root)

    with audit.exclusive_lock(lock_path):
        _assert_capture_path(receipt_path, private_root)
        existing_receipt: dict[str, Any] = {}
        if receipt_path.exists():
            receipt_bytes = _read_capture_bytes(receipt_path, root=private_root)
            try:
                existing_receipt = json.loads(receipt_bytes.decode("utf-8"))
            except Exception as e:
                raise ValueError("Corrupt idea capture receipt") from e
            if not isinstance(existing_receipt, dict):
                raise ValueError("Corrupt idea capture receipt")
            if (
                "semantic_id" not in existing_receipt
                or "original_raw_path" not in existing_receipt
                or "original_raw_sha256" not in existing_receipt
                or "variants" not in existing_receipt
            ):
                raise ValueError("Corrupt idea capture receipt fields")
            if existing_receipt.get("semantic_id") != semantic_id:
                raise ValueError("Conflicting idea capture receipt")

            variants_field = existing_receipt["variants"]
            if (
                not isinstance(existing_receipt["original_raw_path"], str)
                or not existing_receipt["original_raw_path"]
                or not isinstance(existing_receipt["original_raw_sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", existing_receipt["original_raw_sha256"]) is None
                or not isinstance(variants_field, dict)
                or any(
                    not isinstance(digest, str)
                    or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                    or not isinstance(relative, str)
                    or not relative
                    for digest, relative in variants_field.items()
                )
            ):
                raise ValueError("Corrupt idea capture receipt fields")

            orig_raw_file = private_root / existing_receipt["original_raw_path"]
            _assert_capture_path(orig_raw_file, private_root)
            if (
                not orig_raw_file.exists()
                or sha256(_read_capture_bytes(orig_raw_file, root=private_root)).hexdigest()
                != existing_receipt["original_raw_sha256"]
            ):
                raise ValueError("Original raw capture file missing or corrupt")

            for var_sha, var_rel in existing_receipt.get("variants", {}).items():
                var_file = private_root / var_rel
                _assert_capture_path(var_file, private_root)
                if (
                    not var_file.exists()
                    or sha256(_read_capture_bytes(var_file, root=private_root)).hexdigest()
                    != var_sha
                ):
                    raise ValueError("Variant capture file missing or corrupt")

        raw_bytes_hash = sha256(raw_bytes).hexdigest()

        if receipt_path.exists():
            orig_raw_rel = existing_receipt["original_raw_path"]
            orig_raw_sha = existing_receipt["original_raw_sha256"]
            variants = dict(existing_receipt.get("variants", {}))
            orig_raw_file = private_root / orig_raw_rel

            if raw_bytes_hash == orig_raw_sha or raw_bytes_hash in variants:
                pass
            else:
                variant_filename = f"{raw_bytes_hash[:16]}.json"
                var_dir = private_root / "_distill" / "idea-capture" / "variants" / convo.uuid
                _assert_capture_path(var_dir, private_root)
                var_dir.mkdir(parents=True, exist_ok=True)
                variant_path = var_dir / variant_filename
                _assert_capture_path(variant_path, private_root)
                _atomic_write_bytes(variant_path, raw_bytes, root=private_root)
                variants[raw_bytes_hash] = variant_path.relative_to(private_root).as_posix()
        else:
            date = _date_from(convo.created_at)
            raw_dir = private_root / "chat-history" / "idea-capture"
            _assert_capture_path(raw_dir, private_root)
            raw_dir.mkdir(parents=True, exist_ok=True)
            orig_raw_file = raw_dir / f"{date}-{convo.uuid}.json"
            _assert_capture_path(orig_raw_file, private_root)
            _atomic_write_bytes(orig_raw_file, raw_bytes, root=private_root)
            orig_raw_rel = orig_raw_file.relative_to(private_root).as_posix()
            orig_raw_sha = raw_bytes_hash
            variants = {}

        indexes = brain_indexes if brain_indexes is not None else {}
        if "idea-capture" not in indexes:
            indexes["idea-capture"] = _capture_brain_paths(brain_root)
        existing_brain_paths = indexes["idea-capture"]

        brain_dir = brain_root / "_inbox" / "idea-capture"
        _assert_capture_path(brain_dir, brain_root)
        brain_dir.mkdir(parents=True, exist_ok=True)
        date = _date_from(convo.created_at)
        canonical_brain_path = brain_dir / f"{date}-{convo.uuid}.md"
        brain_path = existing_brain_paths.get(convo.uuid, canonical_brain_path)
        _assert_capture_path(brain_path, brain_root)

        if brain_path.exists():
            existing_post = frontmatter.load(brain_path)
            if (
                existing_post.get("conversation_id")
                and existing_post.get("conversation_id") != convo.uuid
            ):
                raise FileExistsError(f"Brain path collision for conversation {convo.uuid}")
            brain_preserved = True
        else:
            brain_preserved = False
            stub_summary = _agent_stub_summary(convo)
            brain_body = _render_brain_body(stub_summary)
            brain_post = frontmatter.Post(
                content=brain_body,
                source="idea-capture",
                conversation_id=convo.uuid,
                imported=_now_iso(),
                private_file=orig_raw_rel,
                status="needs-summary",
                trust="untrusted-data",
                tags=["draft", "needs-summary"],
            )
            _atomic_write_text(brain_path, frontmatter.dumps(brain_post), root=brain_root)
            existing_brain_paths[convo.uuid] = brain_path

        receipt_data = {
            "semantic_id": semantic_id,
            "conversation_id": convo.uuid,
            "original_raw_path": orig_raw_rel,
            "original_raw_sha256": orig_raw_sha,
            "variants": variants,
            "brain_path": brain_path.relative_to(brain_root).as_posix(),
            "brain_preserved": brain_preserved,
        }
        _atomic_write_text(receipt_path, json.dumps(receipt_data, indent=2), root=private_root)

        audit.record_ingest(
            private_root,
            conversation_id=convo.uuid,
            mode=effective_mode,
            fmt="idea-capture",
            raw_path=orig_raw_file,
            brain_path=brain_path,
            source="idea-capture",
            brain_preserved=brain_preserved,
            private_root_for_rel=private_root,
            brain_root_for_rel=brain_root,
        )
        audit.record_import_receipt(
            private_root,
            source_name="idea-capture",
            source_size=len(raw_bytes),
            fmt="idea-capture",
            selected_members=("idea-capture",),
            conversation_count=1,
            brain_created=int(not brain_preserved),
            brain_preserved=int(brain_preserved),
        )
        index_lock = receipt_dir / "index.lock"
        _assert_capture_path(index_lock, private_root)
        with audit.exclusive_lock(index_lock):
            # A selected import is only part of the corpus. Rebuild under one
            # lock so another capture cannot publish a stale partial index.
            corpus = _capture_brain_paths(brain_root)
            index_convos = []
            for conversation_id, note in corpus.items():
                if re.fullmatch(r"idea-[0-9a-f]{16}", conversation_id) is None:
                    raise ValueError("Invalid idea capture note identity")
                _assert_capture_path(note, brain_root)
                imported = frontmatter.loads(
                    _read_capture_bytes(note, root=brain_root).decode("utf-8")
                ).get("imported", "")
                date = (
                    imported
                    if isinstance(imported, str) and re.match(r"\d{4}-\d{2}-\d{2}T", imported)
                    else ""
                )
                index_convos.append(
                    replace(
                        convo,
                        uuid=conversation_id,
                        title=f"Captured Idea {conversation_id}",
                        created_at=date,
                        updated_at=date,
                        messages=(),
                        summary="",
                    )
                )
            _assert_capture_path(brain_dir / "_INDEX.md", brain_root)
            write_index(index_convos, brain_root=brain_root, platform="idea-capture")

        return [
            DualWriteResult(
                private_path=orig_raw_file,
                brain_path=brain_path,
                brain_preserved=brain_preserved,
            )
        ]


def _ingest_kura_capture(
    export_path: Path,
    *,
    brain_root: Path,
    private_root: Path,
    api_key: str,
    effective_mode: Mode,
    brain_indexes: dict[str, dict[str, Path]] | None = None,
) -> list[DualWriteResult]:
    """Hash-based incremental capture intake with private revision receipts."""
    convo = next(kura_handler.parse_export(export_path))
    token = sha256(f"{convo.platform}:{convo.uuid}".encode()).hexdigest()
    state_path = private_root / "_distill" / "kura" / f"{token}.json"
    if not state_path.resolve().is_relative_to(private_root.resolve()):
        raise ValueError("Kura receipt escapes private root")
    payload = json.dumps(
        {"title": convo.title, "messages": [(m.sender, m.text) for m in convo.messages]},
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = sha256(payload.encode()).hexdigest()
    with audit.exclusive_lock(state_path.with_suffix(".lock")):
        try:
            state = (
                json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                "Invalid private Kura receipt; restore it from a private backup before retrying"
            ) from error
        if not isinstance(state, dict) or (
            state
            and (
                not isinstance(state.get("raw_path"), str)
                or not isinstance(state.get("content_sha256"), str)
                or type(state.get("refresh_pending")) is not bool
            )
        ):
            raise ValueError(
                "Invalid private Kura receipt fields; restore the receipt before retrying"
            )
        indexes = brain_indexes if brain_indexes is not None else {}
        if convo.platform not in indexes:
            indexes[convo.platform] = index_existing_brain_paths(
                brain_root=brain_root, platform=convo.platform
            )
        existing = indexes[convo.platform]
        raw = private_root / state.get("raw_path", "_missing")
        if not raw.resolve().is_relative_to(private_root.resolve()):
            raise ValueError("Kura receipt escapes private root")
        raw_digest = sha256(raw.read_bytes()).hexdigest() if raw.is_file() else ""
        if (
            state.get("content_sha256") == digest
            and convo.uuid in existing
            and raw_digest
            and state.get("raw_sha256") == raw_digest
        ):
            return []
        summary = (
            summarize(convo, api_key=api_key)
            if effective_mode == "api" and convo.uuid not in existing
            else _dry_run_summary(convo)
            if effective_mode == "dry-run"
            else _agent_stub_summary(convo)
        )
        result = write_pair(
            convo,
            summary,
            brain_root=brain_root,
            private_root=private_root,
            existing_brain_paths=existing,
        )
        if effective_mode == "agent" and not result.brain_preserved:
            _mark_needs_summary(result.brain_path, brain_root=brain_root)
        audit.record_ingest(
            private_root,
            conversation_id=convo.uuid,
            mode=effective_mode,
            fmt="kura",
            raw_path=result.private_path,
            brain_path=result.brain_path,
            source=export_path.name,
            brain_preserved=result.brain_preserved,
            private_root_for_rel=private_root,
            brain_root_for_rel=brain_root,
        )
        audit.record_import_receipt(
            private_root,
            source_name=export_path.name,
            source_size=export_path.stat().st_size,
            fmt="kura",
            selected_members=(export_path.name,),
            conversation_count=1,
            brain_created=int(not result.brain_preserved),
            brain_preserved=int(result.brain_preserved),
        )
        _atomic_write_text(
            state_path,
            json.dumps(
                {
                    "content_sha256": digest,
                    "raw_sha256": sha256(result.private_path.read_bytes()).hexdigest(),
                    "raw_path": result.private_path.relative_to(private_root).as_posix(),
                    "refresh_pending": result.brain_preserved,
                },
                indent=2,
            ),
            root=private_root,
        )
        return [result]



def _mark_needs_summary(brain_path: Path, *, brain_root: Path) -> None:
    """Update brain file frontmatter to set status=needs-summary.

    Called only for agent-mode ingests. The /distill-inbox agent looks for this
    marker to know which inbox items are waiting for distillation.
    """
    import frontmatter  # local import keeps import-time light

    post = frontmatter.load(brain_path)
    post["status"] = "needs-summary"
    # Tag for inbox filtering in Obsidian
    raw_tags = post.get("tags", []) or []
    tags: list[str] = list(cast(Iterable[str], raw_tags))
    if "needs-summary" not in tags:
        tags.append("needs-summary")
    if "needs-triage" in tags:
        tags.remove("needs-triage")
    post["tags"] = tags
    _atomic_write_text(brain_path, frontmatter.dumps(post), root=brain_root)


@click.command()
@click.argument("export_paths", nargs=-1, type=click.Path(path_type=Path)) # type: ignore[type-var]
@click.option(
    "--brain-root",
    type=click.Path(path_type=Path), # type: ignore[type-var]
    envvar="SBO_BRAIN_VAULT_ROOT",
    required=True,
    help="Path to your brain/ vault. Default: $SBO_BRAIN_VAULT_ROOT env var.",
)
@click.option(
    "--private-root",
    type=click.Path(path_type=Path), # type: ignore[type-var]
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
    "--format",
    "format_option",
    type=click.Choice(
        ["claude.ai", "chatgpt", "kura", "idea-capture", "idea_capture"],
        case_sensitive=False,
    ),
    default=None,
    help="Explicit export format (e.g. idea-capture).",
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
    type=click.Path(exists=True, path_type=Path), # type: ignore[type-var]
    default=None,
    help="Path to the export's memories.json (the AI's cross-conversation memory). "
    "If omitted, a memories.json sibling next to EXPORT_PATH is auto-detected.",
)
def cli(
    export_paths: tuple[Path, ...],
    brain_root: Path,
    private_root: Path,
    mode_flag: str | None,
    format_option: str | None,
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

    mode_parsed: Mode | None = None
    if mode_flag in ("agent", "api", "dry-run"):
        mode_parsed = mode_flag # type: ignore[assignment]
    effective_mode = _resolve_mode(
        mode_parsed,
        dry_run=dry_run,
    )

    if effective_mode == "api" and not api_key:
        click.echo(
            "[error] mode=api requires --api-key (or $ANTHROPIC_API_KEY)",
            err=True,
        )
        sys.exit(1)

    normalized_fmt = format_option.lower().replace("_", "-") if format_option else None

    if normalized_fmt == "idea-capture":
        if effective_mode != "agent":
            click.echo("[error] idea-capture format requires agent mode", err=True)
            sys.exit(1)

        idea_results: list[DualWriteResult] = []
        for path in export_paths:
            try:
                idea_results.extend(
                    ingest(
                        path,
                        brain_root=brain_root,
                        private_root=private_root,
                        api_key=api_key,
                        mode=effective_mode,
                        memories_path=memories_path,
                        format="idea-capture",
                    )
                )
            except (ValueError, OSError) as e:
                click.echo(f"[error] {e}", err=True)
                sys.exit(1)
        click.echo(f"[sbo] wrote {len(idea_results)} conversation pairs")
        for r in idea_results:
            click.echo(f"  raw:     {r.private_path}")
            click.echo(f"  summary: {r.brain_path}")
        click.echo(f"[sbo] audit:   {private_root}/_distill/audit.jsonl")
        return

    try:
        files = [f for p in export_paths for f in _resolve_export_paths(p, [])]
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
    failures: list[str] = []
    try:
        for path in export_paths:
            try:
                results.extend(
                    ingest(
                        path,
                        brain_root=brain_root,
                        private_root=private_root,
                        api_key=api_key,
                        mode=effective_mode,
                        memories_path=memories_path,
                        format=format_option,
                    )
                )
            except CaptureBatchError as error:
                results.extend(error.results)
                failures.extend(error.failures)
    except (ValueError, OSError, YAMLError) as e:
        click.echo(f"[error] {e}", err=True)
        sys.exit(1)
    except AnthropicError as e:
        click.echo(f"[error] Anthropic API call failed: {e}", err=True)
        sys.exit(1)
    click.echo(f"[sbo] wrote {len(results)} conversation pairs")
    for r in results:
        click.echo(f"  raw:     {r.private_path}")
        click.echo(f"  summary: {r.brain_path}")
    click.echo(f"[sbo] audit:   {private_root}/_distill/audit.jsonl")
    if failures:
        click.echo(
            f"[error] {len(failures)} capture(s) failed; "
            "healthy results and receipts are preserved",
            err=True,
        )
        for failure in failures:
            click.echo(f"[error] {failure}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
