"""Idea capture export parser and validator for Second Brain OS.

Handles single JSON packets with exact schema:
  - version: 1 (integer, not bool)
  - rawText: nonblank string
  - tags: string always (whitespace and duplicates preserved; lists rejected before writes)
  - source: nonblank string
  - sourceRef: null or nonblank string

Strictly bounded file size (<= 8MiB), non-symlink regular file, UTF-8 (with optional BOM,
no surrogates), and no duplicate/unknown JSON keys.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from sbo_ingestion.handlers.claude_ai import Conversation, Message

MAX_IDEA_CAPTURE_SIZE = 8 * 1024 * 1024  # 8 MiB
ALLOWED_KEYS = frozenset({"version", "rawText", "tags", "source", "sourceRef"})


def read_and_validate_packet(path: Path) -> tuple[dict[str, Any], bytes]:
    """Read and validate an idea capture JSON packet from path.

    Returns (parsed_dict, raw_bytes).
    Enforces <=8MiB size bound on stat and read, non-symlink regular file,
    exact 5 fields, no duplicate keys, string tags, UTF-8 (plain or BOM),
    no surrogates, and generic error messages omitting private data.
    """
    if not path.exists():
        raise ValueError("Idea capture file does not exist")
    if path.is_symlink():
        raise ValueError("Idea capture path cannot be a symlink")
    if not path.is_file():
        raise ValueError("Idea capture path must be a regular file")

    st_size = path.stat().st_size
    if st_size > MAX_IDEA_CAPTURE_SIZE:
        raise ValueError("Idea capture file exceeds 8MiB size limit")

    with path.open("rb") as f:
        data = f.read(MAX_IDEA_CAPTURE_SIZE + 1)

    if len(data) > MAX_IDEA_CAPTURE_SIZE:
        raise ValueError("Idea capture file exceeds 8MiB size limit")

    if not data:
        raise ValueError("Idea capture file is empty")

    if data.startswith(b"\xef\xbb\xbf"):
        json_bytes = data[3:]
    else:
        json_bytes = data

    try:
        decoded_text = json_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError("Invalid UTF-8 encoding in idea capture packet") from e

    if any(0xD800 <= ord(c) <= 0xDFFF for c in decoded_text):
        raise ValueError("Surrogate characters not permitted in idea capture packet")

    def object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate keys detected in JSON packet")
        return dict(pairs)

    try:
        obj = json.loads(decoded_text, object_pairs_hook=object_pairs_hook)
    except ValueError as e:
        if "Duplicate keys" in str(e):
            raise
        raise ValueError("Invalid JSON in idea capture packet") from e
    except Exception as e:
        raise ValueError("Invalid JSON in idea capture packet") from e

    if not isinstance(obj, dict):
        raise ValueError("Idea capture packet must be a JSON object")

    if set(obj.keys()) != ALLOWED_KEYS:
        raise ValueError("Idea capture packet must contain exact five expected fields")

    version = obj["version"]
    if type(version) is not int or isinstance(version, bool) or version != 1:
        raise ValueError("Invalid version in idea capture packet; must be integer 1")

    raw_text = obj["rawText"]
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("Invalid rawText in idea capture packet; must be nonblank string")

    tags = obj["tags"]
    if not isinstance(tags, str):
        raise ValueError("Invalid tags in idea capture packet; must be string")

    source = obj["source"]
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Invalid source in idea capture packet; must be nonblank string")

    source_ref = obj["sourceRef"]
    if source_ref is not None:
        if not isinstance(source_ref, str) or not source_ref.strip():
            raise ValueError(
                "Invalid sourceRef in idea capture packet; must be null or nonblank string"
            )

    # Escaped JSON values become Unicode code points only after json.loads.
    for value in (raw_text, tags, source, source_ref):
        if isinstance(value, str) and any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("Surrogate characters not permitted in idea capture fields")
    return obj, data


def compute_semantic_identity(obj: dict[str, Any]) -> str:
    """Compute normalized semantic identity hash for an idea capture packet."""
    canonical = json.dumps(
        {
            "version": obj["version"],
            "rawText": obj["rawText"],
            "tags": obj["tags"],
            "source": obj["source"],
            "sourceRef": obj["sourceRef"],
        },
        sort_keys=True,
        ensure_ascii=False,
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
