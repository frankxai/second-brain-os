"""Private immutable source copies using SBO's existing filesystem/audit boundary."""

from __future__ import annotations

import json
import os
from hashlib import file_digest, sha256
from pathlib import Path
from uuid import uuid4

import frontmatter

from sbo_ingestion import audit
from sbo_ingestion.handlers.chatgpt_source import ChatGPTSource, canonical_json


def checked(path: Path, root: Path) -> Path:
    """Reject redirected paths, including links that remain within the vault."""
    try:
        relative = path.absolute().relative_to(root.absolute())
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError("ChatGPT archive path escapes private root") from None
    cursor = root.absolute()
    for part in (None, *relative.parts):
        if part is not None:
            cursor /= part
        if cursor.is_symlink():
            raise ValueError("ChatGPT archive paths cannot contain symlinks")
    return path


def immutable_text(path: Path, text: str, root: Path) -> Path:
    checked(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError("Immutable ChatGPT source conflict; restore before retry")
        return path
    audit.atomic_write_text(path, text)
    return path


def preserve_export(source: Path, root: Path) -> tuple[Path, str]:
    """Stream a byte-exact private snapshot before parsing it; never extract ZIPs."""
    with source.open("rb") as handle:
        digest = file_digest(handle, "sha256").hexdigest()
    suffix = ".zip" if source.suffix.lower() == ".zip" else ".json"
    target = checked(root / "_distill/chatgpt/exports" / digest / ("original" + suffix), root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        with target.open("rb") as handle:
            if file_digest(handle, "sha256").hexdigest() != digest:
                raise ValueError("Private original hash mismatch; restore before retry")
        return target, digest
    temporary = target.with_name(".copy-" + uuid4().hex)
    try:
        with source.open("rb") as src, temporary.open("xb") as dst:
            os.chmod(temporary, 0o600)
            checksum = sha256()
            while chunk := src.read(1024 * 1024):
                checksum.update(chunk)
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        if checksum.hexdigest() != digest:
            raise ValueError("Export changed during copy; retry stable source")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target, digest


def preserve_graph(graph: ChatGPTSource, root: Path) -> Path:
    envelope = canonical_json(graph.envelope()) + "\n"
    token = sha256(graph.stable_id.encode()).hexdigest()
    digest = sha256(envelope.encode()).hexdigest()
    return immutable_text(
        root / "_distill/chatgpt/sources" / token / f"{digest}.json", envelope, root
    )


def assert_revision_forward(graph: ChatGPTSource, active: str | None, root: Path) -> None:
    """An old export must not silently reactivate a superseded source revision."""
    if not active or active == graph.content_sha256:
        return
    token = sha256(graph.stable_id.encode()).hexdigest()
    directory = checked(root / "_distill/chatgpt/history" / token, root)
    if directory.exists():
        for path in directory.glob("*.md"):
            checked(path, root)
            text = path.read_text(encoding="utf-8")
            if sha256(text.encode()).hexdigest() != path.stem:
                raise ValueError("Private source history hash mismatch")
            previous = frontmatter.loads(text)
            if (
                previous.get("conversation_id") == graph.stable_id
                and previous.get("account_scope") == graph.account_scope
                and previous.get("source_content_sha256") == graph.content_sha256
            ):
                raise ValueError(
                    "Previously imported ChatGPT revision requires review before reactivation"
                )


def preserve_previous(path: Path, root: Path) -> str | None:
    checked(path, root)
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    digest = sha256(text.encode()).hexdigest()
    identity = frontmatter.loads(text).get("conversation_id", "")
    token = sha256(str(identity).encode()).hexdigest()
    immutable_text(root / "_distill/chatgpt/history" / token / f"{digest}.md", text, root)
    return digest


def write_manifest(
    root: Path,
    *,
    batch: str,
    account_scope: str | None,
    source_name: str,
    members: tuple[str, ...],
    records: list[dict],
) -> Path:
    scope = sha256(canonical_json(["chatgpt", account_scope]).encode()).hexdigest()
    path = checked(root / "_distill/chatgpt/imports" / scope / f"{batch}.json", root)
    payload = {
        "schema_version": "sbo.chatgpt-import.v1",
        "provider": "chatgpt",
        "account_scope": account_scope,
        "batch_id": batch,
        "source_sha256": batch,
        "source_name": source_name,
        "selected_members": list(members),
        "member_namespace": "private-snapshot",
        "coverage": "supplied-export-only",
        "exporter_window": None,
        "account_denominator": None,
        "unknown": [
            "other accounts",
            "unexported conversations",
            "provider retention",
            "export completeness",
            "hidden or deleted messages",
        ],
        "watermark": {"kind": "completed-file-hash", "value": batch},
        "status": "completed",
        "records": records,
        "counts": {
            key: sum(r["status"] == key for r in records)
            for key in ("captured", "unchanged", "revised")
        },
        "source_times": {
            "earliest": min((r["created_at"] for r in records if r["created_at"]), default=None),
            "latest": max((r["updated_at"] for r in records if r["updated_at"]), default=None),
        },
        "parse_exceptions": [list(r["diagnostics"]) for r in records if r["diagnostics"]],
        "duplicate_candidates": None,
    }
    # A completed batch receipt is immutable: replay returns its original accounting.
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        fixed = (
            "schema_version",
            "provider",
            "account_scope",
            "batch_id",
            "source_sha256",
            "member_namespace",
            "coverage",
            "exporter_window",
            "account_denominator",
            "unknown",
            "watermark",
            "status",
            "source_times",
            "parse_exceptions",
            "duplicate_candidates",
        )
        if any(previous.get(key) != payload[key] for key in fixed):
            raise ValueError("Invalid ChatGPT import receipt invariants")
        old_records = previous.get("records")
        if not isinstance(old_records, list) or len(old_records) != len(records):
            raise ValueError("Invalid ChatGPT import receipt records")
        if not isinstance(previous.get("source_name"), str) or (
            previous.get("selected_members") != list(members)
        ):
            raise ValueError("Invalid ChatGPT import receipt members")
        for old, current in zip(old_records, records, strict=True):
            if (
                not isinstance(old, dict)
                or old.get("status") not in {"captured", "unchanged", "revised"}
                or type(old.get("refresh_pending")) is not bool
            ):
                raise ValueError("Invalid ChatGPT import receipt record status")
            if any(
                old.get(key) != value
                for key, value in current.items()
                if key not in {"status", "refresh_pending", "diagnostics"}
            ):
                raise ValueError("Invalid ChatGPT import receipt source identity")
            if old.get("diagnostics") != list(current["diagnostics"]):
                raise ValueError("Invalid ChatGPT import receipt diagnostics")
        counts = {
            key: sum(r["status"] == key for r in old_records)
            for key in ("captured", "unchanged", "revised")
        }
        if previous.get("counts") != counts:
            raise ValueError("Invalid ChatGPT import receipt counts")
        return path
    return immutable_text(path, canonical_json(payload) + "\n", root)
