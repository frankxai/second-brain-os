"""Cited lexical search over a selected brain root.

The filesystem remains canonical. The index under ``_meta`` is a derived cache:
deleting it only forces a rebuild. Private originals are never opened. Pending
notes return metadata only. A cursor is bound to an index generation, so a
changed archive cannot skip or repeat a page.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from os import stat_result
from pathlib import Path
from urllib.parse import urlparse

import frontmatter
from yaml import YAMLError

INDEX_RELATIVE = "_meta/kura-archive-index.json"
PENDING = {"needs-summary", "pending", "raw"}
REVIEWED = {"reviewed", "curated", "accepted"}
ALLOWED_HOSTS = {
    "chatgpt.com",
    "chat.openai.com",
    "claude.ai",
    "gemini.google.com",
    "grok.com",
    "x.com",
    "chat.deepseek.com",
    "perplexity.ai",
    "www.perplexity.ai",
}
TOKEN = re.compile(r"[a-z0-9]{2,}")
MAX_QUERY = 200
MAX_HITS = 3
MAX_EXCERPT = 160


def tokenize(value: str) -> list[str]:
    return TOKEN.findall(value.lower())


def source_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 300:
        return None
    try:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.port is not None
            or parsed.hostname not in ALLOWED_HOSTS
        ):
            return None
    except ValueError:
        return None
    return parsed.geturl()


def _excerpt(text: str, terms: list[str]) -> str:
    flat = " ".join(text.split())
    wanted = set(terms)
    # Match positions in the original string: Unicode lowercasing can expand
    # characters and invalidate offsets used to slice the original text.
    matches = [
        match
        for match in re.finditer(TOKEN.pattern, flat, re.IGNORECASE | re.ASCII)
        if match.group().lower() in wanted
    ]
    if matches:
        # A lone rare substring can point at an unrelated paragraph. Prefer
        # windows containing more distinct complete query tokens instead.
        priorities = {term: len(terms) - index for index, term in enumerate(terms)}
        candidates = {max(0, match.start() - 40) for match in matches}
        best = None
        for candidate in sorted(candidates):
            start = candidate
            if start and not flat[start - 1].isspace():
                boundary = flat.find(" ", start)
                if boundary != -1:
                    start = boundary + 1
            end = min(len(flat), start + MAX_EXCERPT)
            if end < len(flat) and not flat[end].isspace():
                boundary = flat.rfind(" ", start, end)
                if boundary > start:
                    end = boundary
            clip = flat[start:end]
            if "chat-history/" in clip or "/private/" in clip:
                continue
            found = set(tokenize(clip)) & wanted
            score = (len(found), sum(priorities[term] for term in found), -start)
            if best is None or score > best[0]:
                best = (score, clip)
        if best is not None:
            return best[1]
    clip = flat[:MAX_EXCERPT]
    if "chat-history/" in clip or "/private/" in clip:
        return ""
    return clip


def _source_snapshot(path: Path) -> tuple[bytes, stat_result] | None:
    """Read one source version; refuse observable mutation during the read."""
    try:
        before = path.stat()
        content = path.read_bytes()
        after = path.stat()
    except OSError:
        return None
    fields = ("st_size", "st_mtime_ns", "st_ctime_ns", "st_dev", "st_ino")
    if len(content) != after.st_size or any(
        getattr(before, key) != getattr(after, key) for key in fields
    ):
        return None
    return content, after


def _record(
    path: Path,
    brain: Path,
    query_terms: list[str] | None = None,
    *,
    snapshot: tuple[bytes, stat_result] | None = None,
) -> dict | None:
    if path.is_symlink() or not path.resolve().is_relative_to(brain):
        return None
    relative = path.relative_to(brain).as_posix()
    if relative == INDEX_RELATIVE or any(
        part.startswith(".") for part in path.relative_to(brain).parts
    ):
        return None
    snapshot = snapshot if snapshot is not None else _source_snapshot(path)
    if snapshot is None:
        return None
    content, stat = snapshot
    # The parsed body and its identity must come from the same bytes.
    if path.is_symlink() or not path.resolve().is_relative_to(brain):
        return None
    try:
        post = frontmatter.loads(content.decode("utf-8"))
    except (OSError, UnicodeError, YAMLError):
        return None
    status = str(post.get("status") or "unknown")[:40]
    pending = status in PENDING or bool(post.get("distill_pending"))
    title = str(post.get("title") or path.stem)[:180]
    platform = str(post.get("source") or post.get("platform") or "")[:40]
    imported = str(post.get("imported") or post.get("capturedAt") or "")[:24]
    body = "" if pending else str(post.get("summary") or post.content or "")
    terms = tokenize(f"{title} {'' if pending else body}")
    return {
        "citation": relative,
        "title": title,
        "status": status,
        "platform": platform,
        "date": imported[:10],
        "sourceUrl": source_url(post.get("source_url") or post.get("source")),
        "review": "metadata-only" if pending else "excerpt",
        "excerpt": ""
        if pending
        else _excerpt(body, query_terms if query_terms is not None else terms[:8]),
        "terms": terms,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _valid_cached_record(record: object, relative: str, stat: stat_result, digest: str) -> bool:
    """A stat match does not establish that a derived record is well formed."""
    if not isinstance(record, dict) or record.get("citation") != relative:
        return False
    bounds = {"title": 180, "status": 40, "platform": 40, "date": 10, "excerpt": MAX_EXCERPT}
    if any(
        not isinstance(record.get(key), str) or len(record[key]) > bound
        for key, bound in bounds.items()
    ):
        return False
    terms = record.get("terms")
    if not isinstance(terms, list) or any(
        not isinstance(term, str) or TOKEN.fullmatch(term) is None for term in terms
    ):
        return False
    review = record.get("review")
    if not isinstance(review, str) or review not in {"metadata-only", "excerpt"}:
        return False
    if review == "metadata-only" and record["excerpt"]:
        return False
    if record["status"] in PENDING and review != "metadata-only":
        return False
    url = record.get("sourceUrl")
    if url is not None and (not isinstance(url, str) or source_url(url) != url):
        return False
    return (
        isinstance(record.get("sha256"), str)
        and record["sha256"] == digest
        and type(record.get("size")) is int
        and record["size"] == stat.st_size
        and type(record.get("mtime_ns")) is int
        and record["mtime_ns"] == stat.st_mtime_ns
    )


def load_index(brain_root: Path) -> tuple[dict, dict]:
    """Return records and a measurement of changed versus reused files."""
    brain = brain_root.resolve()
    cache_path = brain / INDEX_RELATIVE
    cached: dict[str, dict] = {}
    if cache_path.is_file() and not cache_path.is_symlink():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            files = payload.get("files") if isinstance(payload, dict) else None
            if isinstance(files, dict):
                cached = files
        except (OSError, UnicodeError, json.JSONDecodeError):
            cached = {}
    records: dict[str, dict] = {}
    changed = reused = 0
    started = time.perf_counter()
    for path in brain.rglob("*.md"):
        relative = path.relative_to(brain).as_posix()
        if (
            relative == INDEX_RELATIVE
            or path.is_symlink()
            or not path.resolve().is_relative_to(brain)
            or any(part.startswith(".") for part in path.relative_to(brain).parts)
        ):
            continue
        snapshot = _source_snapshot(path)
        if snapshot is None:
            continue
        content, stat = snapshot
        digest = hashlib.sha256(content).hexdigest()
        previous = cached.get(relative)
        if _valid_cached_record(previous, relative, stat, digest):
            records[relative] = previous
            reused += 1
            continue
        record = _record(path, brain, snapshot=snapshot)
        if record:
            records[relative] = record
            changed += 1
    payload = {"version": 2, "files": records}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    temporary.replace(cache_path)
    generation = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return records, {
        "root": "brain",
        "changed": changed,
        "reused": reused,
        "notes": len(records),
        "generation": generation,
        "milliseconds": round((time.perf_counter() - started) * 1000, 3),
    }


def search(
    brain_root: Path,
    query: str,
    *,
    cursor: str | None = None,
    platform: str | None = None,
) -> dict:
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY:
        raise ValueError("Query must be 1 to 200 characters")
    if (
        platform is not None
        and platform not in ALLOWED_HOSTS
        and platform
        not in {
            "chatgpt",
            "claude",
            "gemini",
            "grok",
            "deepseek",
            "perplexity",
            "codex",
            "idea-capture",
        }
    ):
        raise ValueError("Unsupported platform filter")
    records, measurement = load_index(brain_root)
    terms = tokenize(query)
    if not terms:
        raise ValueError("Query has no searchable words")
    docs = [
        item
        for item in records.values()
        if not platform or item.get("platform") in {platform, platform.split(".")[0]}
    ]
    counts: dict[str, int] = {}
    for item in docs:
        for term in set(item.get("terms") or []):
            counts[term] = counts.get(term, 0) + 1
    average = max(1, sum(len(item.get("terms") or []) for item in docs) / max(1, len(docs)))
    ranked = []
    for item in docs:
        frequencies: dict[str, int] = {}
        for term in item.get("terms") or []:
            frequencies[term] = frequencies.get(term, 0) + 1
        score = 0.0
        for term in terms:
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            documents = max(1, len(docs))
            idf = math.log(
                1 + (documents - counts.get(term, 0) + 0.5) / (counts.get(term, 0) + 0.5)
            )
            length = len(item.get("terms") or [])
            score += idf * (frequency * 2.2) / (frequency + 1.2 * (0.25 + 0.75 * length / average))
        if score:
            ranked.append((round(score, 6), item["citation"], item))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    start = 0
    if cursor:
        try:
            marker = json.loads(cursor)
        except json.JSONDecodeError as error:
            raise ValueError("Invalid search cursor") from error
        if marker.get("generation") != measurement["generation"]:
            return {"ok": False, "code": "index_changed", "searched": measurement}
        start = next(
            (
                i + 1
                for i, row in enumerate(ranked)
                if row[1] == marker.get("citation") and row[0] == marker.get("score")
            ),
            None,
        )
        if start is None:
            return {"ok": False, "code": "index_changed", "searched": measurement}
    page = ranked[start : start + MAX_HITS]
    items = []
    # Re-read only the bounded result page: source metadata and the current query
    # determine what leaves the host, rather than a precomputed cache excerpt.
    excerpt_terms = sorted(terms, key=lambda term: counts.get(term, 0))
    brain = brain_root.resolve()
    for score, citation, indexed in page:
        item = _record(brain / citation, brain, excerpt_terms)
        if item is None or item["sha256"] != indexed["sha256"]:
            # A changed result cannot inherit its old ranking or cursor.
            return {"ok": False, "code": "index_changed", "searched": measurement}
        items.append(
            {
                "citation": item["citation"],
                "title": item["title"],
                "status": item["status"],
                "platform": item["platform"],
                "date": item["date"],
                "review": item["review"],
                "excerpt": item["excerpt"] if item["review"] == "excerpt" else None,
                "sourceUrl": item["sourceUrl"],
                "score": score,
            }
        )
    next_cursor = None
    if start + MAX_HITS < len(ranked) and page:
        next_cursor = json.dumps(
            {
                "generation": measurement["generation"],
                "score": page[-1][0],
                "citation": page[-1][1],
            },
            separators=(",", ":"),
        )
    return {
        "ok": True,
        "scope": "brain",
        "searched": measurement,
        "total": len(ranked),
        "cursor": next_cursor,
        "items": items,
    }
