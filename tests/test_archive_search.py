from __future__ import annotations

import json
from pathlib import Path

import pytest

from sbo_ingestion.archive_search import search
from sbo_ingestion.native_host import process_request


def note(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_reviewed_note_is_cited_and_pending_note_hides_its_body(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    note(brain / "notes" / "decisions" / "kura.md", """---
title: Kura archive decision
status: reviewed
source: chatgpt
source_url: https://chatgpt.com/c/decision
imported: 2026-10-04T10:00:00Z
summary: Keep the filesystem canonical and cite the reviewed note.
---
Keep the filesystem canonical and cite the reviewed note.
""")
    note(brain / "notes" / "ideas" / "pending.md", """---
title: Pending archive decision
status: needs-summary
source: claude
summary: This private-looking pending body must not be returned.
---
This private-looking pending body must not be returned.
""")
    note(tmp_path / "private" / "chat-history" / "secret.md", """---
title: Secret original
status: reviewed
summary: private original about the archive decision
---
private original about the archive decision
""")
    result = search(brain, "archive decision")
    assert result["ok"] is True
    assert result["scope"] == "brain" and result["searched"]["root"] == "brain"
    citations = {item["citation"]: item for item in result["items"]}
    assert citations["notes/decisions/kura.md"]["excerpt"]
    assert citations["notes/decisions/kura.md"]["sourceUrl"] == "https://chatgpt.com/c/decision"
    assert citations["notes/ideas/pending.md"]["review"] == "metadata-only"
    assert citations["notes/ideas/pending.md"]["excerpt"] is None
    assert "private original" not in json.dumps(result)
    assert "chat-history" not in json.dumps(result)


def test_cursor_is_stable_until_the_index_changes(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    for index in range(5):
        note(brain / "notes" / f"item-{index}.md", f"""---
title: Item {index}
status: reviewed
source: grok
summary: bounded retrieval item {index} for cursor stability
---
bounded retrieval item {index}
""")
    first = search(brain, "bounded retrieval")
    second = search(brain, "bounded retrieval", cursor=first["cursor"])
    assert first["cursor"]
    assert {item["citation"] for item in first["items"]}.isdisjoint(item["citation"] for item in second["items"])
    note(brain / "notes" / "new.md", """---
title: New bounded retrieval
status: reviewed
source: grok
summary: bounded retrieval added after the cursor
---
bounded retrieval added after the cursor
""")
    changed = search(brain, "bounded retrieval", cursor=first["cursor"])
    assert changed["ok"] is False and changed["code"] == "index_changed"


def test_incremental_index_reuses_unchanged_notes(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    for index in range(30):
        note(brain / "notes" / f"{index}.md", f"""---
title: Note {index}
status: reviewed
summary: lexical cache note {index}
---
lexical cache note {index}
""")
    first = search(brain, "lexical cache")
    second = search(brain, "lexical cache")
    assert first["searched"]["changed"] == 30
    assert second["searched"]["reused"] == 30
    assert second["searched"]["changed"] == 0
    assert second["searched"]["milliseconds"] <= first["searched"]["milliseconds"] + 50


def test_hostile_source_does_not_escape(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    note(brain / "notes" / "bad-link.md", """---
title: Bad link
status: reviewed
source: https://evil.test/?chatgpt.com
summary: archive decision with a rejected link
---
archive decision with a rejected link
""")
    result = search(brain, "archive decision")
    assert [item["citation"] for item in result["items"]] == ["notes/bad-link.md"]
    assert result["items"][0]["sourceUrl"] is None


def test_symlink_does_not_escape(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    outside = tmp_path / "outside.md"
    outside.write_text("outside archive decision", encoding="utf-8")
    (brain / "notes").mkdir(parents=True)
    try:
        (brain / "notes" / "escape.md").symlink_to(outside)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows host lacks symlink creation privilege")
        raise
    result = search(brain, "archive decision")
    assert result["items"] == []


def test_native_search_stays_inside_the_metadata_budget(tmp_path: Path) -> None:
    brain, private, capture = tmp_path / "brain", tmp_path / "private", tmp_path / "captures"
    for root in (brain, private, capture):
        root.mkdir()
    note(brain / "notes" / "cited.md", """---
title: Cited native result
status: reviewed
source: chatgpt
source_url: https://chatgpt.com/c/native
summary: native cited archive search result
---
native cited archive search result
""")
    config = {"version": 1, "extension_id": "a" * 32, "capture_root": capture,
              "brain_root": brain, "private_root": private}
    reply = process_request({"v": 1, "id": "search-1", "op": "search", "query": "cited archive"}, config)
    assert reply["ok"] is True
    assert reply["items"][0]["citation"] == "notes/cited.md"
    assert len(json.dumps(reply, separators=(",", ":")).encode()) <= 4096


def test_native_search_rejects_private_scope(tmp_path: Path) -> None:
    config = {"version": 1, "extension_id": "a" * 32, "capture_root": tmp_path / "c",
              "brain_root": tmp_path / "b", "private_root": tmp_path / "p"}
    for root in config.values():
        if isinstance(root, Path):
            root.mkdir()
    reply = process_request({"v": 1, "id": "search-2", "op": "search", "query": "x", "scope": "private"}, config)
    assert reply["ok"] is False and reply["code"] == "invalid_request"


def test_cursor_refuses_changed_content_with_unchanged_paths_and_scores(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    for label in ("a", "b", "c", "d"):
        note(brain / f"{label}.md", f"""---
title: Shared {label}
status: reviewed
source: codex
---
Shared stable firstword.
""")
    first = search(brain, "shared")
    assert first["cursor"]
    unchanged = search(brain, "shared", cursor=first["cursor"])
    assert unchanged["ok"] and len(unchanged["items"]) == 1

    target = brain / "d.md"
    original = target.read_text(encoding="utf-8")
    note(target, original.replace("firstword", "otherword"))
    changed = search(brain, "shared", cursor=first["cursor"])
    assert changed["ok"] is False and changed["code"] == "index_changed"

    fresh = search(brain, "shared")
    assert fresh["searched"]["generation"] != first["searched"]["generation"]
    resumed = search(brain, "shared", cursor=fresh["cursor"])
    assert resumed["ok"] and len(resumed["items"]) == 1
