"""Image ingestion handler — vision-based classification and extraction.

Accepts JPEG, PNG, GIF, and WEBP images from any source: notebook photos,
Notion screenshots, Obsidian exports, scanned documents.

Pipeline per image:
  1. Encode image as base64
  2. Single Claude vision API call: classify content type + extract structure
  3. Return ImageCapture dataclass

Content types: handwritten_note, typed_text, sketch, table, todo_list,
               journal_entry, meeting_notes, diagram, mixed, illegible
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import anthropic

SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp"})

_EXTRACT_PROMPT = """\
You are processing an image from a personal knowledge system. Analyze and extract its content.

Return a JSON object with exactly these fields:
- "content_type": one of: handwritten_note, typed_text, sketch, table, todo_list, journal_entry, meeting_notes, diagram, mixed, illegible
- "title": short descriptive title (max 60 chars) — infer from content, not filename
- "body_md": full transcribed or described content in clean Markdown — preserve structure (headings, bullets, tables, checkboxes [ ]/[x]) — for diagrams/sketches describe elements and relationships
- "tags": array of 2-6 lowercase topic tags (not content-type tags)
- "people": array of people's names mentioned or visible (empty array if none)
- "projects": array of project/product/system names referenced (empty array if none)
- "date_visible": date string if visibly written in image (ISO-8601 preferred, else raw text, empty string if none)
- "confidence": float 0.0–1.0 — your confidence in transcription/extraction quality

Rules:
- For handwritten content: transcribe exactly as written. Do not correct or paraphrase.
- For typed text / screenshots: extract full visible text content.
- For diagrams or sketches: describe elements, relationships, and any visible labels.
- If content is illegible: set content_type to "illegible", body_md to a brief description of what you can see.
- Return ONLY valid JSON. No prose before or after the JSON object.\
"""


@dataclass(frozen=True)
class ImageCapture:
    """Structured output from vision-based image analysis."""

    source_path: Path
    content_type: str
    title: str
    body_md: str
    tags: tuple[str, ...]
    people: tuple[str, ...]
    projects: tuple[str, ...]
    date_visible: str
    confidence: float
    platform: str = "image"


def _encode_image(path: Path) -> tuple[str, str]:
    """Return (base64_data, media_type) for a local image file."""
    suffix = path.suffix.lower()
    media_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_map.get(suffix) or (
        mimetypes.guess_type(str(path))[0] or "image/jpeg"
    )
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return data, media_type


def _parse_response(raw: str, source_path: Path) -> ImageCapture:
    """Parse Claude's JSON response into an ImageCapture. Fails gracefully."""
    obj: dict = {}
    try:
        obj = json.loads(raw.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    return ImageCapture(
        source_path=source_path,
        content_type=str(obj.get("content_type") or "mixed"),
        title=str(obj.get("title") or source_path.stem)[:60],
        body_md=str(obj.get("body_md") or ""),
        tags=tuple(str(t).lower() for t in (obj.get("tags") or [])),
        people=tuple(str(p) for p in (obj.get("people") or [])),
        projects=tuple(str(p) for p in (obj.get("projects") or [])),
        date_visible=str(obj.get("date_visible") or ""),
        confidence=float(obj.get("confidence") or 0.5),
    )


def analyze_image(
    path: Path,
    *,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
) -> ImageCapture:
    """Run a single image through the vision pipeline. Returns ImageCapture."""
    client = anthropic.Anthropic(api_key=api_key)
    b64_data, media_type = _encode_image(path)

    message = client.messages.create(
        model=model,
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": _EXTRACT_PROMPT,
                    },
                ],
            }
        ],
    )

    raw_text = message.content[0].text if message.content else "{}"
    return _parse_response(raw_text, path)


def parse_image_folder(
    folder: Path,
    *,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
    recursive: bool = False,
) -> Iterator[ImageCapture]:
    """Yield ImageCapture objects for all supported images in a folder.

    Processes in alphabetical order. Skips unsupported extensions silently.
    Set recursive=True to walk all subdirectories.
    """
    pattern = "**/*" if recursive else "*"
    paths = sorted(
        p
        for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    for path in paths:
        yield analyze_image(path, api_key=api_key, model=model)
