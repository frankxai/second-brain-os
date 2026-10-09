"""Bounded text intake for inspected local Codex rollout JSONL files.

This is a local cache reader, not a supported cloud export API. Only stored
message records and compaction summaries are captured. Tool traces, reasoning,
event duplicates and binary attachments remain in the untouched original file.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from sbo_ingestion.handlers.claude_ai import Conversation, Message

MAX_SOURCE_BYTES = 512 * 1024 * 1024
MAX_RECORD_BYTES = 8 * 1024 * 1024
MAX_TEXT_BYTES = 32 * 1024 * 1024
MAX_MESSAGES = 100_000
ROLES = {"user": "human", "assistant": "assistant", "developer": "developer", "system": "system"}


@dataclass(frozen=True)
class CodexConversation(Conversation):
    source_path: str = ""
    source_sha256: str = ""
    source_lines: tuple[int, ...] = ()

    def to_raw_markdown(self) -> str:
        lines = [
            f"# {self.title}", "", "Capture scope: stored local Codex message text",
            f"Source file: {self.source_path}", f"Source SHA-256: {self.source_sha256}",
            "User-role records may include setup, delegated work or runtime replays; "
            "they do not establish founder authorship.",
            "Tool traces, reasoning, event duplicates and non-text attachments remain "
            "in the original source. A compaction summary is derived context, "
            "not an original prompt.", "",
        ]
        for message, number in zip(self.messages, self.source_lines, strict=True):
            lines.extend([f"**{message.sender}** · {message.created_at} · source line {number}",
                          "", message.text, ""])
        return "\n".join(lines) + "\n"


def _first_record(path: Path) -> dict:
    with path.open("rb") as handle:
        # Bound leading whitespace as well as individual records.
        for _ in range(100):
            line = handle.readline(MAX_RECORD_BYTES + 1)
            if not line:
                return {}
            if len(line) > MAX_RECORD_BYTES:
                raise ValueError("Codex source record exceeds the size bound")
            if line.strip():
                record = json.loads(line.decode("utf-8-sig"))
                return record if isinstance(record, dict) else {}
    raise ValueError("Too many blank records before export identity")


def is_rollout(path: Path) -> bool:
    """Recognize identity before routing JSONL to the older Claude reader."""
    try:
        return _first_record(path).get("type") == "session_meta"
    except (json.JSONDecodeError, UnicodeError):
        return False


def _timestamp(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Codex {label} must be an ISO timestamp")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Codex {label} must be an ISO timestamp") from error
    if timestamp.tzinfo is None:
        raise ValueError(f"Codex {label} must include a timezone")
    return value


def parse_export(path: Path) -> Iterator[CodexConversation]:
    """Parse a whole bounded snapshot before yielding anything writable."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("Codex source must be a regular local file")
    start = path.stat()
    if start.st_size > MAX_SOURCE_BYTES:
        raise ValueError("Codex source exceeds the size bound")
    digest = sha256()
    identity = None
    created_at = ""
    messages: list[Message] = []
    source_lines: list[int] = []
    retained_bytes = 0
    bytes_read = 0
    with path.open("rb") as handle:
        number = 0
        while line := handle.readline(MAX_RECORD_BYTES + 1):
            number += 1
            bytes_read += len(line)
            if len(line) > MAX_RECORD_BYTES or bytes_read > MAX_SOURCE_BYTES:
                raise ValueError("Codex source or record exceeds the size bound")
            digest.update(line)
            if not line.strip():
                continue
            try:
                record = json.loads(line.decode("utf-8-sig"))
            except (json.JSONDecodeError, UnicodeError) as error:
                raise ValueError(f"Invalid Codex JSON on line {number}") from error
            if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
                raise ValueError(f"Invalid Codex record on line {number}")
            payload = record["payload"]
            kind = record.get("type")
            if kind == "session_meta":
                try:
                    session_id = str(UUID(payload["id"]))
                except (KeyError, ValueError, TypeError, AttributeError) as error:
                    raise ValueError("Invalid Codex session identity") from error
                timestamp = _timestamp(payload.get("timestamp", record.get("timestamp")),
                                       label="session timestamp")
                if identity is not None and (identity != session_id or created_at != timestamp):
                    raise ValueError("Conflicting Codex session metadata")
                identity, created_at = session_id, timestamp
                continue
            if identity is None:
                raise ValueError("Codex session metadata must precede its records")
            sender, text = "", ""
            if kind == "response_item" and payload.get("type") == "message":
                role = payload.get("role")
                if role not in ROLES or not isinstance(payload.get("content"), list):
                    raise ValueError(f"Invalid Codex message on line {number}")
                if role == "assistant" and payload.get("channel") == "analysis":
                    continue
                pieces = []
                for part in payload["content"]:
                    if not isinstance(part, dict) or not isinstance(part.get("type"), str):
                        raise ValueError(f"Invalid Codex content on line {number}")
                    if part["type"] in {"input_text", "output_text"}:
                        if not isinstance(part.get("text"), str):
                            raise ValueError(f"Invalid Codex text on line {number}")
                        pieces.append(part["text"])
                    elif part["type"] in {"input_image", "input_audio", "output_audio"}:
                        pieces.append(
                            f"[Non-text {part['type']} remains in original source line {number}]"
                        )
                    else:
                        raise ValueError(f"Unsupported Codex content type on line {number}")
                sender, text = ROLES[role], "\n".join(pieces)
            elif kind == "compacted":
                if not isinstance(payload.get("message"), str):
                    raise ValueError(f"Invalid Codex compaction summary on line {number}")
                sender, text = "system", "[Derived compaction summary]\n" + payload["message"]
            if sender:
                timestamp = _timestamp(record.get("timestamp"), label="message timestamp")
                retained_bytes += len(text.encode("utf-8"))
                if retained_bytes > MAX_TEXT_BYTES or len(messages) >= MAX_MESSAGES:
                    raise ValueError("Codex retained text or message count exceeds the size bound")
                messages.append(Message(f"{identity}:line:{number}", sender, text, timestamp))
                source_lines.append(number)
    finish = path.stat()
    if (start.st_size, start.st_mtime_ns, start.st_ctime_ns, start.st_ino) != (
            finish.st_size, finish.st_mtime_ns, finish.st_ctime_ns, finish.st_ino):
        raise ValueError("Codex source changed during intake; retry a settled snapshot")
    if identity is None or not messages:
        raise ValueError("Codex source has no session identity or stored messages")
    yield CodexConversation(
        uuid=identity, title=f"Codex session {identity}", created_at=created_at,
        updated_at=messages[-1].created_at, messages=tuple(messages), platform="codex",
        source_path=str(path.resolve()), source_sha256=digest.hexdigest(),
        source_lines=tuple(source_lines),
    )
