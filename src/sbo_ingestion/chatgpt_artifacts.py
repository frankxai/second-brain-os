"""Private index of the binary artifacts a ChatGPT export references.

The index reads the preserved export in place. It extracts, renders and copies
nothing, and it writes only inside the private vault. A manifest states which
referenced files the export actually shipped, with a hash for each, and names
the ones it did not ship. Reuse approval is a later human decision: every
artifact is recorded as captured and not approved.
"""

from __future__ import annotations

import json
import re
import zlib
from hashlib import sha256
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

import click

from sbo_ingestion.chatgpt_archive import checked, immutable_text
from sbo_ingestion.handlers.chatgpt_source import ChatGPTSource, canonical_json

SCHEMA = "sbo.chatgpt-artifacts.v1"
RECEIPT_SCHEMA = "sbo.chatgpt-artifact-receipt.v1"
# Raise when detection changes, so an older receipt for the same export stays distinguishable.
DETECTOR = 1
# A member above this declared size is listed without a hash, never read.
MAX_HASH_BYTES = 4 * 1024**3
_ASSET_NAMES = "conversation_asset_file_names.json"
_MAX_NAMES_BYTES = 32 * 1024**2
# A whole string that is a pointer; prose that merely mentions one is not a reference.
_POINTER = re.compile(r"^(?:sediment|file-service)://(?=\S+$)")
_MARKERS = ("sediment://", "file-service://", '"attachments"')
_ASSET_ID = re.compile(r"file[-_][A-Za-z0-9]+")
_STATUSES = (
    "in-export",
    "missing-from-export",
    "ambiguous",
    "unreadable",
    "not-hashed-oversize",
    "export-has-no-binaries",
    "unrecognized-pointer",
)
_NOT_CAPTURED = (
    "rendered screenshots",
    "interactive states",
    "canvas documents and tool output the provider left out of the export",
    "files referenced only outside conversation messages",
)


def pointer_asset_id(pointer: str) -> str | None:
    """Return the provider file ID an asset pointer or bare attachment ID names."""
    rest = _POINTER.sub("", pointer)
    for part in rest.split("#"):
        match = _ASSET_ID.match(part)
        if match:
            return match.group(0)
    return None


def sniff_media_type(head: bytes) -> str | None:
    """Name a media type from leading bytes; unknown signatures stay unknown."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"PK\x03\x04"):
        return "application/zip"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    if head.startswith(b"ID3"):
        return "audio/mpeg"
    if head.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand == b"avif":
            return "image/avif"
        if brand in (b"heic", b"heix"):
            return "image/heic"
        if brand == b"M4A ":
            return "audio/mp4"
        return "video/mp4"
    return None


class ExportAssets:
    """Asset members of one export, hashed in place and never extracted."""

    def __init__(self, export: Path):
        self.export = export
        self.is_zip = export.suffix.lower() == ".zip"
        self.referenced: set[str] = set()
        self._members: dict[str, list[str]] = {}
        self._names: dict[str, str] = {}
        self._hashed: dict[str, dict] = {}
        if not self.is_zip:
            return
        with ZipFile(export) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                base = PurePosixPath(info.filename).name
                match = _ASSET_ID.match(base)
                if match:
                    self._members.setdefault(match.group(0), []).append(info.filename)
                elif base == _ASSET_NAMES and info.file_size <= _MAX_NAMES_BYTES:
                    self._load_names(archive, info.filename)

    def _load_names(self, archive: ZipFile, member: str) -> None:
        try:
            found = json.loads(archive.read(member))
        except (ValueError, OSError, RuntimeError, NotImplementedError, BadZipFile, zlib.error):
            return
        if isinstance(found, dict):
            self._names.update(
                (key, value)
                for key, value in found.items()
                if isinstance(key, str) and isinstance(value, str)
            )

    @property
    def asset_ids(self) -> frozenset[str]:
        return frozenset(self._members)

    def _hash(self, members: list[str]) -> None:
        pending = [name for name in members if name not in self._hashed]
        if not pending:
            return
        with ZipFile(self.export) as archive:
            for name in pending:
                info = archive.getinfo(name)
                if info.file_size > MAX_HASH_BYTES:
                    self._hashed[name] = {"status": "not-hashed-oversize"}
                    continue
                digest = sha256()
                head = b""
                size = 0
                try:
                    with archive.open(info) as handle:
                        while chunk := handle.read(1024 * 1024):
                            if not head:
                                head = chunk[:16]
                            digest.update(chunk)
                            size += len(chunk)
                except (OSError, RuntimeError, NotImplementedError, BadZipFile, zlib.error):
                    self._hashed[name] = {"status": "unreadable"}
                    continue
                self._hashed[name] = {
                    "status": "in-export",
                    "sha256": digest.hexdigest(),
                    "size_bytes": size,
                    "sniffed_media_type": sniff_media_type(head),
                }

    def _original_name(self, asset_id: str, member: str) -> str | None:
        base = PurePosixPath(member).name
        name = self._names.get(base) or self._names.get(asset_id + ".dat")
        return PurePosixPath(name.replace("\\", "/")).name if name else None

    def resolve(self, asset_id: str | None) -> dict:
        """State what the export holds for one referenced file ID. Never guess."""
        if asset_id is None:
            return {"status": "unrecognized-pointer"}
        self.referenced.add(asset_id)
        if not self.is_zip:
            return {"status": "export-has-no-binaries"}
        members = sorted(set(self._members.get(asset_id, ())))
        if not members:
            return {"status": "missing-from-export"}
        self._hash(members)
        found = [{"member": name, **self._hashed[name]} for name in members]
        for wanted in ("unreadable", "not-hashed-oversize"):
            if any(item["status"] == wanted for item in found):
                return {"status": wanted, "members": members}
        if len({item["sha256"] for item in found}) > 1:
            # Two different files claim one ID. Selecting either would be a guess.
            return {
                "status": "ambiguous",
                "candidates": [
                    {key: item[key] for key in ("member", "sha256", "size_bytes")}
                    for item in found
                ],
            }
        first = found[0]
        original = {
            "status": "in-export",
            "member": first["member"],
            "sha256": first["sha256"],
            "size_bytes": first["size_bytes"],
            "sniffed_media_type": first["sniffed_media_type"],
            "original_name": self._original_name(asset_id, first["member"]),
        }
        if len(members) > 1:
            original["duplicate_members"] = members[1:]
        return original


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _strings(value: object):
    """Yield (path, string, holder, key) in document order without recursion."""
    stack: list[tuple[object, tuple[str, ...], object, str]] = [(value, (), None, "")]
    while stack:
        item, path, holder, key = stack.pop()
        if isinstance(item, str):
            yield path, item, holder, key
        elif isinstance(item, dict):
            for name in sorted(item, reverse=True):
                stack.append((item[name], (*path, str(name)), item, str(name)))
        elif isinstance(item, list):
            for index in range(len(item) - 1, -1, -1):
                stack.append((item[index], (*path, str(index)), item, str(index)))


def _kind(holder: object, key: str, path: tuple[str, ...]) -> str:
    content_type = holder.get("content_type") if isinstance(holder, dict) else None
    if key == "image_url":
        return "tool-output"
    if len(path) > 1 and path[-2] == "screenshot":
        return "screenshot"
    if content_type == "image_asset_pointer":
        return "image"
    if isinstance(content_type, str) and "video" in content_type:
        return "video"
    if isinstance(content_type, str) and "audio" in content_type:
        return "audio"
    return "unknown"


def _declared(holder: object) -> dict:
    """Copy only the provider's own descriptive fields; content stays in the source."""
    if not isinstance(holder, dict):
        return {}
    declared: dict[str, object] = {}
    for name in ("name", "mime_type"):
        if isinstance(holder.get(name), str):
            declared[name] = holder[name]
    for name in ("size_bytes", "size", "width", "height"):
        value = holder.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            declared[name] = value
    metadata = holder.get("metadata")
    if isinstance(metadata, dict) and any(metadata.get(k) for k in ("dalle", "generation")):
        declared["has_generation_metadata"] = True
    return declared


def references(graph: ChatGPTSource) -> list[dict]:
    """List every asset reference in every branch, addressed into the source envelope."""
    # Most conversations are text only; skip them without reparsing the source.
    if not any(marker in graph.original_json for marker in _MARKERS):
        return []
    mapping = graph.mapping
    selected = set(graph.path_to())
    found = []
    for node_id in sorted(mapping):
        message = mapping[node_id].get("message")
        if not isinstance(message, dict):
            continue
        base = "#/original/mapping/" + _escape(node_id) + "/message"
        origin = {
            "node_id": node_id,
            "message_id": message.get("id"),
            "role": (message.get("author") or {}).get("role"),
            # Unknown branch selection is recorded as unknown, not as "not selected".
            "on_selected_branch": (node_id in selected) if selected else None,
        }
        for path, text, holder, key in _strings(message):
            if not _POINTER.match(text):
                continue
            found.append(
                {
                    **origin,
                    "reference": base + "".join("/" + _escape(p) for p in path),
                    "pointer": text,
                    "asset_id": pointer_asset_id(text),
                    "kind": _kind(holder, key, path),
                    "provider_content_type": holder.get("content_type")
                    if isinstance(holder, dict)
                    else None,
                    "declared": _declared(holder),
                }
            )
        metadata = message.get("metadata")
        attachments = metadata.get("attachments") if isinstance(metadata, dict) else None
        for index, item in enumerate(attachments if isinstance(attachments, list) else ()):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            match = _ASSET_ID.fullmatch(item["id"])
            found.append(
                {
                    **origin,
                    "reference": f"{base}/metadata/attachments/{index}",
                    "pointer": item["id"],
                    "asset_id": match.group(0) if match else None,
                    "kind": "attachment",
                    "provider_content_type": None,
                    "declared": _declared(item),
                }
            )
    return found


def _counts(assets: list[dict], reference_count: int) -> dict:
    counts = {"assets": len(assets), "references": reference_count}
    counts.update(
        {status: sum(a["original"]["status"] == status for a in assets) for status in _STATUSES}
    )
    return counts


def build_manifest(graph: ChatGPTSource, export: ExportAssets, root: Path) -> dict | None:
    """Return the artifact manifest for one source revision, or None when it has none."""
    found = references(graph)
    if not found:
        return None
    grouped: dict[str, list[dict]] = {}
    for item in found:
        grouped.setdefault(item["asset_id"] or item["pointer"], []).append(item)
    assets = []
    for key in sorted(grouped):
        group = grouped[key]
        assets.append(
            {
                "asset_id": group[0]["asset_id"],
                "pointers": sorted({item["pointer"] for item in group}),
                "kinds": sorted({item["kind"] for item in group}),
                "original": export.resolve(group[0]["asset_id"]),
                "references": [
                    {k: v for k, v in item.items() if k not in ("asset_id", "pointer")}
                    for item in group
                ],
                # Capture is not approval. A person promotes an artifact, never the importer.
                "governance": {"status": "captured", "approved_for_reuse": False},
            }
        )
    try:
        snapshot = export.export.absolute().relative_to(root.absolute()).as_posix()
    except ValueError:
        snapshot = None
    return {
        "schema_version": SCHEMA,
        "detector": DETECTOR,
        "provider": graph.provider,
        "account_scope": graph.account_scope,
        "conversation_id": graph.conversation_id,
        "stable_id": graph.stable_id,
        "source_content_sha256": graph.content_sha256,
        "export_sha256": graph.source_sha256,
        "export_snapshot": snapshot,
        "capture_method": "official-export",
        "not_captured": list(_NOT_CAPTURED),
        "assets": assets,
        "counts": _counts(assets, len(found)),
    }


def preserve_manifest(graph: ChatGPTSource, export: ExportAssets, root: Path) -> dict | None:
    """Write the manifest content-addressed in the private vault; return its receipt row."""
    manifest = build_manifest(graph, export, root)
    if manifest is None:
        return None
    text = canonical_json(manifest) + "\n"
    digest = sha256(text.encode()).hexdigest()
    token = sha256(graph.stable_id.encode()).hexdigest()
    path = immutable_text(
        root / "_distill/chatgpt/artifacts" / token / f"{digest}.json", text, root
    )
    return {
        "stable_id": graph.stable_id,
        "conversation_id": graph.conversation_id,
        "source_content_sha256": graph.content_sha256,
        "manifest": path.relative_to(root).as_posix(),
        "manifest_sha256": digest,
        "counts": manifest["counts"],
    }


def write_receipt(
    root: Path,
    *,
    batch: str,
    account_scope: str | None,
    export: ExportAssets,
    scanned: int,
    records: list[dict],
) -> Path:
    """Record what one import batch referenced and what the export shipped."""
    counts = {
        key: sum(record["counts"][key] for record in records)
        for key in ("assets", "references", *_STATUSES)
    }
    payload = {
        "schema_version": RECEIPT_SCHEMA,
        "detector": DETECTOR,
        "provider": "chatgpt",
        "account_scope": account_scope,
        "batch_id": batch,
        "export_kind": "zip" if export.is_zip else "json",
        "conversations_scanned": scanned,
        "conversations_with_artifacts": len(records),
        "counts": counts,
        "asset_ids_in_export": len(export.asset_ids),
        "asset_ids_never_referenced": len(export.asset_ids - export.referenced),
        "unknown": [
            "files the provider omitted from this export",
            "artifacts in conversations outside this export",
            "rendered and interactive states",
        ],
        "records": records,
    }
    text = canonical_json(payload) + "\n"
    scope = sha256(canonical_json(["chatgpt", account_scope]).encode()).hexdigest()
    digest = sha256(text.encode()).hexdigest()
    return immutable_text(
        root / "_distill/chatgpt/artifact-receipts" / scope / batch / f"{digest}.json", text, root
    )


def load_receipts(root: Path) -> list[dict]:
    """Return the newest-detector artifact receipt for each import batch."""
    base = checked(root / "_distill/chatgpt/artifact-receipts", root)
    receipts = []
    for batch in sorted(p for p in base.glob("*/*") if p.is_dir()):
        candidates = []
        for path in sorted(batch.glob("*.json")):
            data = checked(path, root).read_bytes()
            if sha256(data).hexdigest() != path.stem:
                raise ValueError("Artifact receipt hash mismatch; restore before use")
            candidates.append(json.loads(data))
        if candidates:
            receipts.append(max(candidates, key=lambda item: item.get("detector", 0)))
    return receipts


@click.command()
@click.option(
    "--private-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Private vault that holds the import receipts.",
)
def cli(private_root: Path) -> None:
    """Report which referenced ChatGPT files each imported export contained."""
    try:
        receipts = load_receipts(private_root)
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    if not receipts:
        click.echo("[sbo] no ChatGPT artifact receipts in this private vault")
        return
    for receipt in receipts:
        counts = receipt["counts"]
        click.echo(
            f"[sbo] export {receipt['batch_id'][:12]} ({receipt['export_kind']}): "
            f"{receipt['conversations_scanned']} conversations scanned, "
            f"{receipt['conversations_with_artifacts']} with file references"
        )
        click.echo(
            f"  files referenced: {counts['assets']}; in export with hash: {counts['in-export']}"
        )
        for status in _STATUSES[1:]:
            if counts[status]:
                click.echo(f"  {status}: {counts[status]}")
        click.echo(f"  files in export never referenced: {receipt['asset_ids_never_referenced']}")
        gaps = sorted(
            (
                (r["counts"]["assets"] - r["counts"]["in-export"], r["stable_id"])
                for r in receipt["records"]
            ),
            reverse=True,
        )
        for gap, stable_id in gaps[:10]:
            if gap:
                click.echo(f"  {gap} without a verified file: {stable_id}")
