"""Read a bounded Kura v0.2.0 conversation capture, without fetching its links.

The Markdown file remains the authority. Ambiguous or incomplete role boundaries
fail closed; captures cover the visible thread, not the provider's entire account.
"""
from __future__ import annotations

import re
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import frontmatter

from sbo_ingestion.handlers.claude_ai import Conversation, Message

PLATFORMS = {
    "chatgpt": ("ChatGPT", "chatgpt", {"chatgpt.com", "chat.openai.com"}, r"/c/([^/]+)"),
    "claude": ("Claude", "claude.ai", {"claude.ai"}, r"/chat/([^/]+)"),
    "gemini": ("Gemini", "gemini", {"gemini.google.com"}, r"/app/([^/]+)"),
    "grok": ("Grok", "grok", {"grok.com", "x.com"}, r"/(?:c|chat)/([^/]+)"),
    "deepseek": ("DeepSeek", "deepseek", {"chat.deepseek.com"}, r"/a/chat/s/([^/]+)"),
    "perplexity": ("Perplexity", "perplexity", {"perplexity.ai", "www.perplexity.ai"}, r"/search/([^/]+)"),
}
MAX_CAPTURE_BYTES = 64 * 1024 * 1024
MAX_CAPTURES = 10_000
JS_WHITESPACE = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"


def discover(root: Path) -> list[Path]:
    """Scan only the specified capture root's platform/folder/conversation.md."""
    resolved = root.resolve()
    paths = []
    for platform in PLATFORMS:
        for path in (root / platform).glob("*/conversation.md"):
            if not path.is_file():
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(resolved):
                raise ValueError("Kura capture escapes its selected root")
            paths.append(path)
            if len(paths) > MAX_CAPTURES:
                raise ValueError("Kura input exceeds 10000 captures; select a smaller batch")
    return sorted(paths)


def parse_export(path: Path):
    if path.is_symlink() or path.stat().st_size > MAX_CAPTURE_BYTES:
        raise ValueError("Kura input must be a regular capture of at most 64 MiB")
    post = frontmatter.loads(path.read_text(encoding="utf-8-sig"))
    if str(post.get("schemaVersion")) != "0.2.0" or not str(post.get("capturedBy", "")).startswith("kura/"):
        raise ValueError("Unsupported Kura capture schema or provenance")
    platform = str(post.get("platform", ""))
    if platform not in PLATFORMS:
        raise ValueError("Unsupported Kura platform")
    label, normalized_platform, hosts, pattern = PLATFORMS[platform]
    source = urlparse(str(post.get("source", "")))
    if (source.scheme != "https" or source.hostname not in hosts or source.username or source.password
            or source.port not in (None, 443)):
        raise ValueError("Kura source URL does not match its platform")
    source_id = str(post.get("id", ""))
    if not source_id or len(source_id) > 512:
        raise ValueError("Kura capture requires a bounded source ID")
    native = re.fullmatch(pattern, source.path)
    if native and source_id == f"{platform}-{native[1]}":
        # Join official exports only on an exact, source-URL-verified ID.
        source_id = native[1]
    else:
        source_id = f"kura:{source_id}"
    captured = str(post.get("capturedAt", ""))
    try:
        datetime.fromisoformat(captured.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Kura capturedAt must be an ISO timestamp") from error
    roles = {"You": "human", label: "assistant", "System": "system"}
    packet_path = path.with_name("capture.json")
    if packet_path.exists():
        if (packet_path.is_symlink() or not packet_path.resolve().is_relative_to(path.parent.resolve())
                or packet_path.stat().st_size > MAX_CAPTURE_BYTES):
            raise ValueError("Kura packet must remain in its capture folder and fit the size bound")
        packet = json.loads(packet_path.read_text(encoding="utf-8-sig"))
        expected = {key: str(post.get(key, "")) for key in ("id", "platform", "title", "source", "capturedAt")}
        actual = packet.get("capture") if isinstance(packet, dict) else None
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError("Invalid capture identity in Kura packet")
        try:
            packet_time = datetime.fromisoformat(str(actual["capturedAt"]).replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("Invalid capture timestamp in Kura packet") from error
        same_identity = all(actual[key] == expected[key] for key in expected if key != "capturedAt")
        if (not isinstance(packet, dict) or packet.get("kind") != "kura-capture"
                or packet.get("packetVersion") != "1.0.0" or not same_identity
                or packet_time != datetime.fromisoformat(captured.replace("Z", "+00:00"))
                or packet.get("renderedBody") != post.content.strip()):
            raise ValueError("Kura packet and Markdown disagree; finish or repeat the browser capture")
        messages = packet.get("messages")
        spans = packet.get("messageSpans")
        if (type(post.get("messageCount")) is not int or not isinstance(messages, list)
                or not messages or len(messages) != post.get("messageCount")
                or not isinstance(spans, list) or len(spans) != len(messages)):
            raise ValueError("Kura packet message count disagrees with Markdown")
        normalized = []
        # Browser string offsets count UTF-16 units; Python counts code points.
        encoded_body = post.content.strip().encode("utf-16-le")
        previous_end = 0
        for index, message in enumerate(messages):
            if (not isinstance(message, dict) or message.get("role") not in ("user", "assistant", "system")
                    or not isinstance(message.get("content"), str)
                    or not isinstance(message.get("timestamp", ""), str)):
                raise ValueError("Invalid message in Kura packet")
            span = spans[index]
            if (not isinstance(span, dict) or type(span.get("start")) is not int
                    or type(span.get("length")) is not int or span["length"] < 0):
                raise ValueError("Invalid message span in Kura packet")
            role_label = "You" if message["role"] == "user" else label if message["role"] == "assistant" else "System"
            stamp = f" <sub>· {message['timestamp']}</sub>" if message.get("timestamp") and packet.get("includeTimestamps", True) else ""
            prefix = f"## {role_label}{stamp}\n\n".encode("utf-16-le")
            start, end = span["start"] * 2, (span["start"] + span["length"]) * 2
            expected_text = message["content"].strip(JS_WHITESPACE).replace("\r\n", "\n").encode("utf-16-le")
            if (start - len(prefix) < previous_end or end > len(encoded_body)
                    or encoded_body[start-len(prefix):start] != prefix
                    or encoded_body[start:end] != expected_text):
                raise ValueError("Kura message data and rendered Markdown disagree")
            previous_end = end
            normalized.append(Message(f"{source_id}:{index}",
                                      "human" if message["role"] == "user" else message["role"],
                                      message["content"], message.get("timestamp", "")))
        yield Conversation(uuid=source_id, title=expected["title"], created_at="", updated_at=captured,
                           messages=tuple(normalized), platform=normalized_platform, source_url=source.geturl())
        return
    heading = re.compile(r"^## (You|" + re.escape(label) + r"|System)(?: <sub>· (.*?)</sub>)?$")
    messages = []
    current = None
    body = []
    fence = None
    fence_size = 0

    def finish():
        if current is None:
            return
        text = "\n".join(body).strip()
        if text.endswith("\n\n---"):
            text = text[:-5].rstrip()
        messages.append(Message(f"{source_id}:{len(messages)}", roles[current[1]], text, current[2] or ""))

    content = re.sub(r"\n---\n\s*\n\*Captured by \[Kura\]\(https://github\.com/frankxai/(?:arcanea-vault|kura)\) · schema v0\.2\.0\*\s*$", "", post.content)
    for line in content.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            if fence is None:
                fence, fence_size = marker[1][0], len(marker[1])
            elif marker[1][0] == fence and len(marker[1]) >= fence_size and not marker[2].strip():
                fence = None
        match = heading.fullmatch(line) if fence is None and not marker else None
        if match:
            finish()
            current, body = match, []
        elif current is not None:
            body.append(line)
    if fence is not None:
        raise ValueError("Unclosed Markdown fence in Kura capture")
    finish()
    count = post.get("messageCount")
    if type(count) is not int or count != len(messages) or not messages:
        raise ValueError("Kura messageCount disagrees with parsed role sections")
    yield Conversation(
        uuid=source_id, title=str(post.get("title") or "Untitled"),
        # Capture time is not the provider's conversation creation time.
        created_at="", updated_at=captured, messages=tuple(messages), platform=normalized_platform,
        source_url=source.geturl(),
    )
