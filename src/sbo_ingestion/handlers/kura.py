"""Read a bounded Kura v0.2.0 conversation capture, without fetching its links.

The Markdown file remains the authority. Ambiguous or incomplete role boundaries
fail closed; captures cover the visible thread, not the provider's entire account.
"""
from __future__ import annotations

import re
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
    if source.scheme != "https" or source.hostname not in hosts or source.username or source.password:
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
