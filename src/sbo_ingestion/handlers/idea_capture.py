"""Idea capture export parser and validator for Second Brain OS."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from sbo_ingestion.handlers.claude_ai import Conversation, Message

MAX_IDEA_CAPTURE_SIZE = 8 * 1024 * 1024
ALLOWED_KEYS = frozenset({"version", "rawText", "tags", "source", "sourceRef"})


def read_and_validate_packet(path: Path) -> tuple[dict[str, Any], bytes]:
    """Read and validate an idea capture JSON packet from path."""
    if not path.exists():
        raise ValueError("Idea capture file does not exist")
    if path.is_symlink():
        raise ValueError("Idea capture path cannot be a symlink")
    if not path.is_file():
        raise ValueError("Idea capture path must be a regular file")
    if path.stat().st_size > MAX_IDEA_CAPTURE_SIZE:
        raise ValueError("Idea capture file exceeds 8MiB size limit")

    with path.open("rb") as f:
        data = f.read(MAX_IDEA_CAPTURE_SIZE + 1)

    if len(data) > MAX_IDEA_CAPTURE_SIZE or not data:
        raise ValueError("Idea capture file exceeds limit or is empty")

    json_bytes = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    try:
        decoded_text = json_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError("Invalid UTF-8 encoding in idea capture packet") from e

    if any(0xD800 <= ord(c) <= 0xDFFF for c in decoded_text):
        raise ValueError("Surrogate characters not permitted in idea capture packet")

    def object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        if len(pairs) != len(set(k for k, _ in pairs)):
            raise ValueError("Duplicate keys detected in JSON packet")
        return dict(pairs)

    try:
        obj = json.loads(decoded_text, object_pairs_hook=object_pairs_hook)
    except ValueError as e:
        if "Duplicate keys" in str(e):
            raise
        raise ValueError("Invalid JSON in idea capture packet") from e

    if not isinstance(obj, dict) or set(obj.keys()) != ALLOWED_KEYS:
        raise ValueError("Idea capture packet must contain exact five expected fields")

    ver, raw, tags, src, ref = (
        obj["version"],
        obj["rawText"],
        obj["tags"],
        obj["source"],
        obj["sourceRef"],
    )
    if type(ver) is not int or isinstance(ver, bool) or ver != 1:
        raise ValueError("Invalid version in idea capture packet; must be integer 1")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Invalid rawText in idea capture packet")
    if not isinstance(tags, str):
        raise ValueError("Invalid tags in idea capture packet")
    if not isinstance(src, str) or not src.strip():
        raise ValueError("Invalid source in idea capture packet")
    if ref is not None and (not isinstance(ref, str) or not ref.strip()):
        raise ValueError("Invalid sourceRef in idea capture packet")

    for val in (raw, tags, src, ref):
        if isinstance(val, str) and any(0xD800 <= ord(c) <= 0xDFFF for c in val):
            raise ValueError("Surrogate characters not permitted in idea capture fields")

    return obj, data


def compute_semantic_identity(obj: dict[str, Any]) -> str:
    """Compute normalized semantic identity hash for an idea capture packet."""
    canonical = json.dumps(
        {k: obj[k] for k in sorted(ALLOWED_KEYS)}, sort_keys=True, ensure_ascii=False
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def create_idea_conversation(
    obj: dict[str, Any], semantic_id: str, created_at: str | None = None
) -> Conversation:
    """Construct a Conversation object representing the captured idea."""
    now_iso = created_at or datetime.now(tz=UTC).isoformat()
    convo_uuid = f"idea-{semantic_id[:16]}"
    msg = Message(
        uuid=f"msg-{semantic_id[:16]}",
        sender="captured-unverified",
        text=obj["rawText"],
        created_at=now_iso,
    )
    return Conversation(
        uuid=convo_uuid,
        title="Captured Idea",
        created_at=now_iso,
        updated_at=now_iso,
        messages=(msg,),
        platform="idea-capture",
        summary="",
    )
