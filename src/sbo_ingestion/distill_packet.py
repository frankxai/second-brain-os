"""Local coding-agent source packets. Never expose these functions through MCP."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import frontmatter

from sbo_ingestion import audit

MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_RECEIPT_BYTES = 128 * 1024


def source_for_stub(stub: Path, private_root: Path) -> Path:
    if stub.is_symlink() or stub.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Stub must be a bounded regular note")
    reference = frontmatter.load(stub).get("private_file")
    if not isinstance(reference, str):
        raise ValueError("Stub requires a private source reference")
    parts = reference.split("/")
    if (len(parts) < 3 or parts[0] != "chat-history" or not parts[-1].endswith(".md")
            or any(not part or part in {".", ".."} or "\\" in part or ":" in part
                   or any(ord(char) < 32 for char in part) for part in parts)):
        raise ValueError("Invalid private source reference")
    source = private_root.joinpath(*parts)
    if (source.is_symlink() or not source.resolve().is_relative_to(private_root.resolve())
            or not source.is_file() or source.stat().st_size > MAX_SOURCE_BYTES):
        raise ValueError("Private source must remain in its selected vault and fit 64 MiB")
    return source


def source_digest(source: Path) -> str:
    digest = sha256()
    with source.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _receipt_path(stub: Path, private_root: Path, digest: str) -> Path:
    key = sha256(str(stub.resolve()).encode()).hexdigest()
    return private_root / "_distill" / "packets" / key / f"{digest}.json"


def _merge_intervals(intervals: list[list[int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _load_receipt(path: Path, digest: str, size: int) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_RECEIPT_BYTES:
        raise ValueError("Source-coverage receipt exceeds its bounded size")
    value = json.loads(path.read_text(encoding="utf-8"))
    intervals = value.get("intervals") if isinstance(value, dict) else None
    if (not isinstance(value, dict) or value.get("source_sha256") != digest
            or value.get("source_bytes") != size or not isinstance(intervals, list)
            or len(intervals) > 4096
            or any(not isinstance(pair, list) or len(pair) != 2
                   or any(type(item) is not int for item in pair)
                   or not 0 <= pair[0] <= pair[1] <= size for pair in intervals)):
        raise ValueError("Invalid source-coverage receipt; restore it before retrying")
    return value


def packet(stub: Path, *, brain_root: Path, private_root: Path,
           offset: int = 0, max_bytes: int = 6000, expected_sha256: str = "") -> dict:
    brain, private = brain_root.resolve(), private_root.resolve()
    if (not stub.resolve().is_relative_to(brain)
            or brain.is_relative_to(private) or private.is_relative_to(brain)):
        raise ValueError("Stub and private source require separate selected vault roots")
    if not 256 <= max_bytes <= 32_000 or offset < 0:
        raise ValueError("Packet budget must be 256..32000 bytes and offset non-negative")
    source = source_for_stub(stub, private)
    digest = source_digest(source)
    size = source.stat().st_size
    if offset > size or (offset and not expected_sha256):
        raise ValueError("Continuation requires a source hash and an in-range byte offset")
    if expected_sha256 and expected_sha256 != digest:
        raise ValueError("Source changed; start a new packet sequence")
    with source.open("rb") as handle:
        handle.seek(offset)
        chunk = handle.read(max_bytes)
    # Preserve every byte while avoiding a UTF-8 code point split at the end.
    for trim in range(4):
        try:
            selected = chunk[:len(chunk) - trim] if trim else chunk
            text = selected.decode("utf-8")
            break
        except UnicodeDecodeError as error:
            if (error.reason != "unexpected end of data" or offset + len(chunk) >= size
                    or error.start < len(chunk) - 4):
                raise ValueError("Source offset is not a UTF-8 boundary or source is invalid") from error
    else:
        raise ValueError("Source offset is not a UTF-8 boundary or source is invalid")
    end = offset + len(selected)
    if source_digest(source) != digest:
        raise ValueError("Source changed while reading; repeat the packet")
    receipt = _receipt_path(stub, private, digest)
    if not receipt.resolve().is_relative_to(private):
        raise ValueError("Source-coverage receipt escapes private vault")
    lock = receipt.with_suffix(".lock")
    if not lock.resolve().is_relative_to(private):
        raise ValueError("Source-coverage lock escapes private vault")
    with audit.exclusive_lock(lock):
        state = (_load_receipt(receipt, digest, size) if receipt.exists()
                 else {"source_sha256": digest, "source_bytes": size, "intervals": []})
        state["intervals"] = _merge_intervals(state["intervals"] + [[offset, end]])
        audit.atomic_write_text(receipt, json.dumps(state, separators=(",", ":")) + "\n")
    return {"trust": "untrusted-data", "source": source.relative_to(private).as_posix(),
            "source_sha256": digest, "source_bytes": size, "start": offset, "end": end,
            "next_offset": end if end < size else None, "source_chunk_bytes": len(selected),
            "approx_source_tokens": (len(selected) + 3) // 4,
            "coverage_complete": state["intervals"] == [[0, size]], "content": text}


def require_complete_coverage(stub: Path, private_root: Path, digest: str) -> None:
    source = source_for_stub(stub, private_root)
    if source_digest(source) != digest:
        raise ValueError("Source changed since distillation; reread before completion")
    receipt = _receipt_path(stub, private_root, digest)
    if not receipt.resolve().is_relative_to(private_root.resolve()):
        raise ValueError("Source-coverage receipt escapes private vault")
    state = _load_receipt(receipt, digest, source.stat().st_size)
    if _merge_intervals(state["intervals"]) != [[0, source.stat().st_size]]:
        raise ValueError("Source coverage is incomplete; read its remaining packets")


def plan_batch(stubs: list[dict], private_root: Path, *, max_notes: int = 3,
               source_budget: int = 18_000) -> dict:
    selected, deferred = [], 0
    for item in stubs:
        try:
            source = source_for_stub(Path(item["stub"]), private_root)
            size = source.stat().st_size
        except (ValueError, OSError):
            deferred += 1
            continue
        if len(selected) >= max_notes or size > source_budget:
            deferred += 1
            continue
        selected.append({**item, "source_bytes": size, "approx_source_tokens": (size + 3) // 4})
        source_budget -= size
    return {"notes": selected, "deferred": deferred, "raw_bodies_returned": 0,
            "pending_stubs_inspected": len(stubs),
            "source_bytes_selected": sum(item["source_bytes"] for item in selected),
            "paid_api_calls": 0, "token_estimate_is_exact": False}
