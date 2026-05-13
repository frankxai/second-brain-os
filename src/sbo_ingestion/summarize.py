"""Summarizer — calls Anthropic API with prompt caching to produce a structured summary.

Output is a Summary dataclass that downstream dual_write.py renders to YAML frontmatter
plus markdown body in the brain/_inbox/ file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from anthropic import Anthropic

from sbo_ingestion.handlers.claude_ai import Conversation


SYSTEM_PROMPT = """\
You summarize a single AI chat conversation into a structured JSON object for inclusion
in a personal-knowledge Obsidian vault. The vault has a strict folder structure; you must
propose destinations that map to it.

OUTPUT FORMAT — return ONLY a JSON object with these keys:
- title (string): short noun-phrase title for the conversation (5-10 words). Improve on
  the original if needed.
- tldr (string): one to two sentences summarizing the conversation's takeaway.
- insights (array of strings): atomic insights worth capturing as evergreen notes. Each
  string is a complete sentence.
- decisions (array of strings): any explicit decisions the human made or committed to.
- open_questions (array of strings): unresolved questions raised that did not get answered.
- people_mentioned (array of objects): each {name, context} for any person mentioned
  by name in the conversation. Skip the AI assistant itself.
- suggested_destinations (array of strings): relative paths inside the brain/ vault
  where this conversation's content could fit, e.g. "notes/learnings/{slug}.md" or
  "projects/{project}/log.md". Maximum 3.

VOICE: direct, technical, warm. No "delve into", "dive into", "it's worth noting",
"certainly", "absolutely". No hyperbole. Pattern recognition as poetry.

Output VALID JSON. No prose outside the JSON object."""


@dataclass(frozen=True)
class PersonMention:
    name: str
    context: str


@dataclass(frozen=True)
class Summary:
    title: str
    tldr: str
    insights: tuple[str, ...] = field(default_factory=tuple)
    decisions: tuple[str, ...] = field(default_factory=tuple)
    open_questions: tuple[str, ...] = field(default_factory=tuple)
    people_mentioned: tuple[PersonMention, ...] = field(default_factory=tuple)
    suggested_destinations: tuple[str, ...] = field(default_factory=tuple)


def _conversation_to_user_message(convo: Conversation) -> str:
    parts = [f"# {convo.title}", f"Platform: {convo.platform}", f"Created: {convo.created_at}", ""]
    for m in convo.messages:
        parts.append(f"## {m.sender}")
        parts.append(m.text)
        parts.append("")
    return "\n".join(parts)


def summarize(
    convo: Conversation,
    *,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 2000,
) -> Summary:
    """Summarize a conversation. Returns Summary; never raises on bad JSON."""
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": _conversation_to_user_message(convo)}],
    )
    text = response.content[0].text if response.content else ""
    return _parse_summary_or_fallback(text, fallback_title=convo.title)


def _parse_summary_or_fallback(text: str, *, fallback_title: str) -> Summary:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # Try to recover by finding a JSON block within the text
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return Summary(
                title=fallback_title,
                tldr="(Could not be parsed from LLM response.)",
            )
        try:
            obj = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return Summary(
                title=fallback_title,
                tldr="(Could not be parsed from LLM response.)",
            )
    people = tuple(
        PersonMention(name=p.get("name", ""), context=p.get("context", ""))
        for p in obj.get("people_mentioned", [])
        if isinstance(p, dict) and p.get("name")
    )
    return Summary(
        title=obj.get("title") or fallback_title,
        tldr=obj.get("tldr") or "",
        insights=tuple(obj.get("insights") or []),
        decisions=tuple(obj.get("decisions") or []),
        open_questions=tuple(obj.get("open_questions") or []),
        people_mentioned=people,
        suggested_destinations=tuple(obj.get("suggested_destinations") or []),
    )
