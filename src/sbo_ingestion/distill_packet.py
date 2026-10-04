"""Local coding-agent source packets. Never expose these functions through MCP."""
from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

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
        raise ValueError("Invalid or changed source-coverage receipt; restore it before retrying")
    if value.get("version") == 2:
        pending, acknowledged = value.get("pending"), value.get("acknowledged_tokens", [])
        if (not isinstance(pending, list) or len(pending) > 16
                or any(not isinstance(item, dict) or set(item) != {"token", "start", "end"}
                       or not isinstance(item["token"], str) or not re.fullmatch(r"[a-f0-9]{32}", item["token"])
                       or type(item["start"]) is not int or type(item["end"]) is not int
                       or not 0 <= item["start"] <= item["end"] <= size for item in pending)
                or not isinstance(acknowledged, list) or len(acknowledged) > 16
                or any(not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{32}", token) for token in acknowledged)):
            raise ValueError("Invalid packet-delivery receipt; reset coverage before retrying")
    return value


def _fingerprint(source: Path) -> list[int]:
    info = source.stat()
    return [info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_dev, info.st_ino]


def _roots(stub: Path, brain_root: Path, private_root: Path) -> tuple[Path, Path]:
    brain, private = brain_root.resolve(), private_root.resolve()
    if (not stub.resolve().is_relative_to(brain)
            or brain.is_relative_to(private) or private.is_relative_to(brain)):
        raise ValueError("Stub and private source require separate selected vault roots")
    return brain, private


def require_packet_hash(stub: Path, private_root: Path, digest: str) -> None:
    directory = _receipt_path(stub, private_root, "placeholder").parent
    if not directory.resolve().is_relative_to(private_root.resolve()):
        raise ValueError("Source-coverage directory escapes private vault")
    if not digest and directory.exists() and any(directory.glob("*.json")):
        raise ValueError("A packet sequence exists; completion requires its source hash")


def packet(stub: Path, *, brain_root: Path, private_root: Path,
           offset: int = 0, max_bytes: int = 6000, expected_sha256: str = "") -> dict:
    _, private = _roots(stub, brain_root, private_root)
    if not 256 <= max_bytes <= 32_000 or offset < 0:
        raise ValueError("Packet budget must be 256..32000 bytes and offset non-negative")
    source = source_for_stub(stub, private)
    fingerprint = _fingerprint(source)
    cached = None
    if expected_sha256:
        if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
            raise ValueError("Invalid source hash")
        candidate = _receipt_path(stub, private, expected_sha256)
        if not candidate.resolve().is_relative_to(private):
            raise ValueError("Source-coverage receipt escapes private vault")
        if candidate.exists():
            cached = _load_receipt(candidate, expected_sha256, fingerprint[0])
    # Cache only local I/O, never model output. Completion rehashes the source.
    cache_valid = cached is not None and cached.get("fingerprint") == fingerprint
    digest = expected_sha256 if cache_valid else source_digest(source)
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
    if _fingerprint(source) != fingerprint or (not cache_valid and source_digest(source) != digest):
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
        if state.get("version") != 2:
            state["legacy_issued_intervals"] = state["intervals"]
            state.update(version=2, intervals=[], pending=[])
        pending = state.get("pending")
        if (not isinstance(pending, list) or len(pending) > 16
                or any(not isinstance(item, dict) or set(item) != {"token", "start", "end"}
                       or not isinstance(item["token"], str) or not re.fullmatch(r"[a-f0-9]{32}", item["token"])
                       or type(item["start"]) is not int or type(item["end"]) is not int
                       or not 0 <= item["start"] <= item["end"] <= size for item in pending)):
            raise ValueError("Invalid packet-delivery receipt; reset coverage before retrying")
        issued = next((item for item in pending if item["start"] == offset and item["end"] == end), None)
        if issued is None:
            if len(pending) >= 16:
                raise ValueError("Acknowledge received packets before requesting more")
            issued = {"token": uuid4().hex, "start": offset, "end": end}
            pending.append(issued)
        state["fingerprint"] = fingerprint
        audit.atomic_write_text(receipt, json.dumps(state, separators=(",", ":")) + "\n")
    return {"trust": "untrusted-data", "source": source.relative_to(private).as_posix(),
            "source_sha256": digest, "source_bytes": size, "start": offset, "end": end,
            "next_offset": end if end < size else None, "source_chunk_bytes": len(selected),
            "approx_source_tokens": (len(selected) + 3) // 4,
            "coverage_complete": state["intervals"] == [[0, size]],
            "ack_token": issued["token"], "content": text}


def acknowledge_packet(stub: Path, *, brain_root: Path, private_root: Path,
                       digest: str, token: str) -> dict:
    _, private = _roots(stub, brain_root, private_root)
    source = source_for_stub(stub, private)
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or not re.fullmatch(r"[a-f0-9]{32}", token):
        raise ValueError("Invalid source hash or packet token")
    receipt = _receipt_path(stub, private, digest)
    if not receipt.resolve().is_relative_to(private) or not receipt.with_suffix(".lock").resolve().is_relative_to(private):
        raise ValueError("Source-coverage receipt escapes private vault")
    with audit.exclusive_lock(receipt.with_suffix(".lock")):
        state = _load_receipt(receipt, digest, source.stat().st_size)
        if state.get("version") != 2 or state.get("fingerprint") != _fingerprint(source):
            raise ValueError("Source changed; reread before acknowledging")
        issued = next((item for item in state.get("pending", []) if item.get("token") == token), None)
        if not issued:
            if token in state.get("acknowledged_tokens", []):
                return {"source_sha256": digest, "coverage_complete": state["intervals"] == [[0, state["source_bytes"]]]}
            raise ValueError("Packet token was not issued for this source")
        state["intervals"] = _merge_intervals(state["intervals"] + [[issued["start"], issued["end"]]])
        state["pending"] = [item for item in state["pending"] if item["token"] != token]
        state["acknowledged_tokens"] = (state.get("acknowledged_tokens", []) + [token])[-16:]
        audit.atomic_write_text(receipt, json.dumps(state, separators=(",", ":")) + "\n")
    return {"source_sha256": digest, "coverage_complete": state["intervals"] == [[0, state["source_bytes"]]]}


def reset_coverage(stub: Path, private_root: Path, digest: str) -> None:
    source = source_for_stub(stub, private_root)
    if source_digest(source) != digest:
        raise ValueError("Reset requires the current source hash")
    receipt = _receipt_path(stub, private_root, digest)
    target = receipt.with_name(f"{digest}.recovery-{uuid4().hex}.json")
    if any(not path.resolve().is_relative_to(private_root.resolve()) for path in (receipt, target, receipt.with_suffix(".lock"))):
        raise ValueError("Source-coverage receipt escapes private vault")
    with audit.exclusive_lock(receipt.with_suffix(".lock")):
        if receipt.exists():
            receipt.replace(target)


def require_complete_coverage(stub: Path, private_root: Path, digest: str) -> None:
    source = source_for_stub(stub, private_root)
    if source_digest(source) != digest:
        raise ValueError("Source changed since distillation; reread before completion")
    receipt = _receipt_path(stub, private_root, digest)
    if not receipt.resolve().is_relative_to(private_root.resolve()):
        raise ValueError("Source-coverage receipt escapes private vault")
    state = _load_receipt(receipt, digest, source.stat().st_size)
    if state.get("version") != 2 or _merge_intervals(state["intervals"]) != [[0, source.stat().st_size]]:
        raise ValueError("Source coverage is incomplete; read its remaining packets")


def plan_batch(stubs: list[dict], private_root: Path, *, max_notes: int = 3,
               source_budget: int = 18_000) -> dict:
    if not 1 <= max_notes <= 10 or not 256 <= source_budget <= 128_000:
        raise ValueError("Invalid metadata planning budget")
    selected, deferred, invalid, next_large = [], 0, [], None
    for item in stubs:
        try:
            source = source_for_stub(Path(item["stub"]), private_root)
            size = source.stat().st_size
        except (ValueError, OSError):
            deferred += 1
            invalid.append({"stub": item["stub"], "reason": "invalid_private_reference"})
            continue
        if len(selected) >= max_notes or size > source_budget:
            deferred += 1
            if next_large is None and size > source_budget:
                next_large = {**item, "source_bytes": size}
            continue
        try:
            source.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            deferred += 1
            invalid.append({"stub": item["stub"], "reason": "invalid_utf8"})
            continue
        selected.append({**item, "source_bytes": size, "approx_source_tokens": (size + 3) // 4})
        source_budget -= size
    return {"notes": selected, "deferred": deferred, "raw_bodies_returned": 0,
            "pending_stubs_inspected": len(stubs),
            "next_large_source": next_large, "invalid_sources": invalid[:10],
            "source_bytes_selected": sum(item["source_bytes"] for item in selected),
            "paid_api_calls": 0, "token_estimate_is_exact": False}
