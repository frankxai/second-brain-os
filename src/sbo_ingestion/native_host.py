"""Origin-bound local Chrome host. Imports verified captures; never serves raw data."""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO

MAX_FRAME = 32_768
PLATFORMS = {"chatgpt", "claude", "gemini", "grok", "deepseek", "perplexity"}


def load_config(path: Path, origin: str) -> dict:
    if path.is_symlink() or path.stat().st_size > MAX_FRAME:
        raise ValueError("Invalid host configuration")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if (not isinstance(value, dict)
            or set(value) != {"version", "extension_id", "capture_root", "brain_root", "private_root"}
            or type(value["version"]) is not int or value["version"] != 1
            or not re.fullmatch(r"[a-p]{32}", str(value["extension_id"]))
            or origin != f"chrome-extension://{value['extension_id']}/"):
        raise ValueError("Origin or host configuration rejected")
    roots = []
    for key in ("capture_root", "brain_root", "private_root"):
        root = Path(value[key])
        if not root.is_absolute() or root.is_symlink() or not root.is_dir():
            raise ValueError("Host requires existing absolute vault roots")
        value[key] = root.resolve()
        roots.append(value[key])
    if any(a.is_relative_to(b) or b.is_relative_to(a)
           for i, a in enumerate(roots) for b in roots[i + 1:]):
        raise ValueError("Host roots must not overlap")
    return value


def read_frame(stream: BinaryIO) -> dict | None:
    def read_exact(size: int) -> bytes:
        parts = bytearray()
        while len(parts) < size:
            part = stream.read(size - len(parts))
            if not part:
                raise ValueError("Incomplete native frame")
            parts.extend(part)
        return bytes(parts)
    first = stream.read(1)
    if not first:
        return None
    size = struct.unpack("=I", first + read_exact(3))[0]
    if not 0 < size <= MAX_FRAME:
        raise ValueError("Native frame exceeds its bound")
    value = json.loads(read_exact(size).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Native request must be an object")
    return value


def write_frame(stream: BinaryIO, value: dict) -> None:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > 4096:
        raise ValueError("Native response exceeds metadata budget")
    stream.write(struct.pack("=I", len(body)) + body)
    stream.flush()


def capture_path(config: dict, relative: str) -> Path:
    if not isinstance(relative, str):
        raise ValueError("Invalid capture pointer")
    parts = relative.split("/")
    if (len(parts) != 3 or parts[0] not in PLATFORMS or parts[2] != "conversation.md"
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}_[a-z0-9-]{1,180}", parts[1])):
        raise ValueError("Invalid capture pointer")
    root = config["capture_root"]
    path = root.joinpath(*parts)
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("Capture pointer escapes configured root")
    return path


def process_request(request: dict, config: dict) -> dict:
    request_id = request.get("id")
    if (type(request.get("v")) is not int or request.get("v") != 1 or not isinstance(request_id, str)
            or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", request_id)):
        return {"v": 1, "ok": False, "code": "invalid_request"}
    base = {"v": 1, "id": request_id}
    if request.get("op") == "hello" and set(request) == {"v", "id", "op"}:
        return {**base, "ok": True, "mode": "agent", "paidApiCalls": 0,
                "vault": config["brain_root"].parent.name,
                "captureFolder": config["capture_root"].name}
    if request.get("op") == "search" and set(request) <= {"v", "id", "op", "query", "cursor", "platform"}:
        if not isinstance(request.get("query"), str):
            return {**base, "ok": False, "code": "invalid_request"}
        from sbo_ingestion.archive_search import search
        try:
            result = search(config["brain_root"], request["query"],
                            cursor=request.get("cursor"), platform=request.get("platform"))
        except ValueError:
            return {**base, "ok": False, "code": "invalid_request"}
        reply = {**base, **result}
        if len(json.dumps(reply, ensure_ascii=False, separators=(",", ":")).encode()) > 4096:
            return {**base, "ok": False, "code": "response_bound"}
        return reply
    if (request.get("op") != "process"
            or set(request) != {"v", "id", "op", "path", "sha256"}
            or not isinstance(request.get("sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", request["sha256"])):
        return {**base, "ok": False, "code": "invalid_request"}
    try:
        path = capture_path(config, request["path"])
        companion = path.with_name("capture.json")
        if (companion.is_symlink() or not companion.resolve().is_relative_to(config["capture_root"])
                or companion.stat().st_size > 64 * 1024 * 1024):
            raise ValueError("Invalid capture packet")
        packet_bytes = companion.read_bytes()
        if sha256(packet_bytes).hexdigest() != request["sha256"]:
            return {**base, "ok": False, "code": "capture_changed"}
        before = sha256(path.read_bytes()).hexdigest() if path.stat().st_size <= 64 * 1024 * 1024 else ""
        if not before:
            raise ValueError("Capture exceeds its bound")
        # Import lazily: hello and protocol failures do not load model SDKs.
        from sbo_ingestion.ingest import ingest
        results = ingest(path, brain_root=config["brain_root"], private_root=config["private_root"], mode="agent")
        if (sha256(companion.read_bytes()).hexdigest() != request["sha256"]
                or sha256(path.read_bytes()).hexdigest() != before):
            return {**base, "ok": False, "code": "capture_changed"}
        return {**base, "ok": True, "processed": len(results),
                "notesCreated": sum(not item.brain_preserved for item in results),
                "refreshPending": sum(item.brain_preserved for item in results),
                "unchanged": not results, "paidApiCalls": 0, "receipt": request["sha256"]}
    except Exception:
        # Raw paths, titles, private text and exception details must not cross this boundary.
        return {**base, "ok": False, "code": "capture_rejected"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("origin")
    parser.add_argument("--parent-window")
    args = parser.parse_args()
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    try:
        config = load_config(args.config, args.origin)
        while (request := read_frame(sys.stdin.buffer)) is not None:
            write_frame(sys.stdout.buffer, process_request(request, config))
        return 0
    except Exception:
        # Failure without a well-formed request ID produces no unframed stdout.
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
