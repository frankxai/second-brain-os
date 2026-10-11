from __future__ import annotations

import json
from pathlib import Path

from sbo_ingestion.archive_search import search
from sbo_ingestion.native_host import process_request


def note(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_reviewed_note_is_cited_and_pending_note_hides_its_body(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    note(
        brain / "notes" / "decisions" / "kura.md",
        "---\ntitle: Kura archive decision\nstatus: reviewed\nsource: chatgpt\n"
        "source_url: https://chatgpt.com/c/decision\nimported: 2026-10-04T10:00:00Z\n"
        "summary: Keep filesystem canonical and cite reviewed note.\n---\n"
        "Keep filesystem canonical and cite reviewed note.\n",
    )
    note(
        brain / "notes" / "ideas" / "pending.md",
        "---\ntitle: Pending archive decision\nstatus: needs-summary\nsource: claude\n"
        "summary: Private pending body.\n---\nPrivate pending body.\n",
    )
    note(
        tmp_path / "private" / "chat-history" / "secret.md",
        "---\ntitle: Secret\nstatus: reviewed\nsummary: private secret\n---\nprivate secret\n",
    )
    result = search(brain, "archive decision")
    assert result["ok"] is True and result["scope"] == "brain"
    citations = {item["citation"]: item for item in result["items"]}
    assert citations["notes/decisions/kura.md"]["excerpt"]
    assert citations["notes/decisions/kura.md"]["sourceUrl"] == "https://chatgpt.com/c/decision"
    assert citations["notes/ideas/pending.md"]["review"] == "metadata-only"
    assert citations["notes/ideas/pending.md"]["excerpt"] is None
    assert "secret" not in json.dumps(result)


def test_cursor_is_stable_until_the_index_changes(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    for i in range(5):
        note(
            brain / "notes" / f"item-{i}.md",
            f"---\ntitle: Item {i}\nstatus: reviewed\nsource: grok\n"
            f"summary: retrieval item {i}\n---\nretrieval item {i}\n",
        )
    first = search(brain, "retrieval item")
    second = search(brain, "retrieval item", cursor=first["cursor"])
    assert first["cursor"]
    assert {i["citation"] for i in first["items"]}.isdisjoint(
        i["citation"] for i in second["items"]
    )
    note(
        brain / "notes" / "new.md",
        "---\ntitle: New\nstatus: reviewed\nsource: grok\n"
        "summary: retrieval item\n---\nretrieval item\n",
    )
    changed = search(brain, "retrieval item", cursor=first["cursor"])
    assert changed["ok"] is False and changed["code"] == "index_changed"


def test_incremental_index_reuses_unchanged_notes(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    for i in range(10):
        note(
            brain / "notes" / f"{i}.md",
            f"---\ntitle: Note {i}\nstatus: reviewed\n"
            f"summary: cache test {i}\n---\ncache test {i}\n",
        )
    first = search(brain, "cache test")
    second = search(brain, "cache test")
    assert first["searched"]["changed"] == 10
    assert second["searched"]["reused"] == 10
    assert second["searched"]["changed"] == 0


def test_hostile_source_and_symlink_do_not_escape(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    outside = tmp_path / "outside.md"
    outside.write_text("outside decision", encoding="utf-8")
    (brain / "notes").mkdir(parents=True)
    (brain / "notes" / "escape.md").symlink_to(outside)
    note(
        brain / "notes" / "bad.md",
        "---\ntitle: Bad link\nstatus: reviewed\nsource: https://evil.test/?chatgpt.com\n"
        "summary: decision bad link\n---\ndecision bad link\n",
    )
    result = search(brain, "decision")
    assert [i["citation"] for i in result["items"]] == ["notes/bad.md"]
    assert result["items"][0]["sourceUrl"] is None


def test_native_search_and_private_scope_check(tmp_path: Path) -> None:
    brain, private, capture = tmp_path / "b", tmp_path / "p", tmp_path / "c"
    for root in (brain, private, capture):
        root.mkdir()
    note(
        brain / "notes" / "cited.md",
        "---\ntitle: Cited\nstatus: reviewed\nsource: chatgpt\n"
        "summary: native cited search\n---\nnative search\n",
    )
    config = {
        "version": 1,
        "extension_id": "a" * 32,
        "capture_root": capture,
        "brain_root": brain,
        "private_root": private,
    }
    reply = process_request({"v": 1, "id": "s-1", "op": "search", "query": "native cited"}, config)
    assert reply["ok"] is True and reply["items"][0]["citation"] == "notes/cited.md"
    reply2 = process_request(
        {"v": 1, "id": "s-2", "op": "search", "query": "x", "scope": "private"}, config
    )
    assert reply2["ok"] is False and reply2["code"] == "invalid_request"
