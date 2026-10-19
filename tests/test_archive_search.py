from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sbo_ingestion import archive_search as archive
from sbo_ingestion import archive_search as excerpt_archive
from sbo_ingestion.archive_search import search
from sbo_ingestion.native_host import process_request


def note(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_reviewed_note_is_cited_and_pending_note_hides_its_body(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    note(
        brain / "notes" / "decisions" / "kura.md",
        """---
title: Kura archive decision
status: reviewed
source: chatgpt
source_url: https://chatgpt.com/c/decision
imported: 2026-10-04T10:00:00Z
summary: Keep the filesystem canonical and cite the reviewed note.
---
Keep the filesystem canonical and cite the reviewed note.
""",
    )
    note(
        brain / "notes" / "ideas" / "pending.md",
        """---
title: Pending archive decision
status: needs-summary
source: claude
summary: This private-looking pending body must not be returned.
---
This private-looking pending body must not be returned.
""",
    )
    note(
        tmp_path / "private" / "chat-history" / "secret.md",
        """---
title: Secret original
status: reviewed
summary: private original about the archive decision
---
private original about the archive decision
""",
    )
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
        note(
            brain / "notes" / f"item-{index}.md",
            f"""---
title: Item {index}
status: reviewed
source: grok
summary: bounded retrieval item {index} for cursor stability
---
bounded retrieval item {index}
""",
        )
    first = search(brain, "bounded retrieval")
    second = search(brain, "bounded retrieval", cursor=first["cursor"])
    assert first["cursor"]
    assert {item["citation"] for item in first["items"]}.isdisjoint(
        item["citation"] for item in second["items"]
    )
    note(
        brain / "notes" / "new.md",
        """---
title: New bounded retrieval
status: reviewed
source: grok
summary: bounded retrieval added after the cursor
---
bounded retrieval added after the cursor
""",
    )
    changed = search(brain, "bounded retrieval", cursor=first["cursor"])
    assert changed["ok"] is False and changed["code"] == "index_changed"


def test_incremental_index_reuses_unchanged_notes(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    for index in range(30):
        note(
            brain / "notes" / f"{index}.md",
            f"""---
title: Note {index}
status: reviewed
summary: lexical cache note {index}
---
lexical cache note {index}
""",
        )
    first = search(brain, "lexical cache")
    second = search(brain, "lexical cache")
    assert first["searched"]["changed"] == 30
    assert second["searched"]["reused"] == 30
    assert second["searched"]["changed"] == 0
    assert second["searched"]["milliseconds"] <= first["searched"]["milliseconds"] + 50


@pytest.mark.parametrize(
    "cache",
    [
        [],
        {"files": None},
        {"files": []},
        {"files": {"note.md": ["broken"]}},
        {"files": {"note.md": "broken"}},
    ],
)
def test_malformed_cache_rebuilds_from_saved_notes(tmp_path: Path, cache: object) -> None:
    brain = tmp_path / "brain"
    note(
        brain / "note.md",
        """---
title: Saved continuity
status: reviewed
source: grok
source_url: https://grok.com/c/continuity
---
Useful recovered continuity artifact.
""",
    )
    cache_path = brain / "_meta" / "kura-archive-index.json"
    cache_path.parent.mkdir()
    cache_path.write_text(json.dumps(cache), encoding="utf-8")

    result = search(brain, "continuity")
    assert result["ok"] is True
    assert [item["citation"] for item in result["items"]] == ["note.md"]
    assert result["items"][0]["sourceUrl"] == "https://grok.com/c/continuity"
    assert result["searched"]["changed"] == 1
    rebuilt = search(brain, "continuity")
    assert rebuilt["searched"]["reused"] == 1
    assert rebuilt["searched"]["changed"] == 0
    assert rebuilt["items"] == result["items"]


def test_hostile_source_does_not_escape(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    note(
        brain / "notes" / "bad-link.md",
        """---
title: Bad link
status: reviewed
source: https://evil.test/?chatgpt.com
summary: archive decision with a rejected link
---
archive decision with a rejected link
""",
    )
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
    note(
        brain / "notes" / "cited.md",
        """---
title: Cited native result
status: reviewed
source: chatgpt
source_url: https://chatgpt.com/c/native
summary: native cited archive search result
---
native cited archive search result
""",
    )
    config = {
        "version": 1,
        "extension_id": "a" * 32,
        "capture_root": capture,
        "brain_root": brain,
        "private_root": private,
    }
    reply = process_request(
        {"v": 1, "id": "search-1", "op": "search", "query": "cited archive"}, config
    )
    assert reply["ok"] is True
    assert reply["items"][0]["citation"] == "notes/cited.md"
    assert len(json.dumps(reply, separators=(",", ":")).encode()) <= 4096


def test_native_search_rejects_private_scope(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "extension_id": "a" * 32,
        "capture_root": tmp_path / "c",
        "brain_root": tmp_path / "b",
        "private_root": tmp_path / "p",
    }
    for root in config.values():
        if isinstance(root, Path):
            root.mkdir()
    reply = process_request(
        {"v": 1, "id": "search-2", "op": "search", "query": "x", "scope": "private"}, config
    )
    assert reply["ok"] is False and reply["code"] == "invalid_request"


def test_native_search_filters_recovered_codex_notes(tmp_path: Path) -> None:
    brain, private, capture = tmp_path / "brain", tmp_path / "private", tmp_path / "capture"
    for root in (brain, private, capture):
        root.mkdir()
    for platform in ("codex", "chatgpt", "grok"):
        note(
            brain / f"{platform}.md",
            f"""---
title: Recovered intent from {platform}
status: reviewed
source: {platform}
---
Recovered intent for the existing owner.
""",
        )
    config = {
        "version": 1,
        "extension_id": "a" * 32,
        "capture_root": capture,
        "brain_root": brain,
        "private_root": private,
    }
    reply = process_request(
        {
            "v": 1,
            "id": "codex-filter",
            "op": "search",
            "query": "recovered intent",
            "platform": "codex",
        },
        config,
    )
    assert reply["ok"] is True
    assert [item["citation"] for item in reply["items"]] == ["codex.md"]
    assert reply["items"][0]["platform"] == "codex"
    assert reply["items"][0]["excerpt"] == "Recovered intent for the existing owner."


def test_cursor_refuses_changed_content_with_unchanged_paths_and_scores(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    for label in ("a", "b", "c", "d"):
        note(
            brain / f"{label}.md",
            f"""---
title: Shared {label}
status: reviewed
source: codex
---
Shared stable firstword.
""",
        )
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


@pytest.mark.parametrize(
    "invalid_url",
    [
        "https://chatgpt.com:broken/c/one",
        "https://chatgpt.com:70000/c/one",
        "https://[bad-host/c/one",
        "https://chatgpt.com:0/c/one",
        "https://@chatgpt.com/c/one",
        "https://:fixture@chatgpt.com/c/one",
    ],
)
def test_invalid_source_link_does_not_block_valid_note_retrieval(
    tmp_path: Path,
    invalid_url: str,
) -> None:
    brain = tmp_path / "brain"
    note(
        brain / "notes" / "invalid.md",
        f"""---
title: Invalid linked archive
status: reviewed
source: chatgpt
source_url: {json.dumps(invalid_url)}
---
Recover archive with rejected source link.
""",
    )
    note(
        brain / "notes" / "valid.md",
        """---
title: Valid linked archive
status: reviewed
source: chatgpt
source_url: https://chatgpt.com/c/valid
---
Recover archive with valid source link.
""",
    )
    result = search(brain, "recover archive")
    assert result["ok"]
    hits = {item["citation"]: item for item in result["items"]}
    assert hits["notes/invalid.md"]["sourceUrl"] is None
    assert hits["notes/valid.md"]["sourceUrl"] == "https://chatgpt.com/c/valid"


def _warm_repair_fixture(tmp_path: Path) -> tuple[Path, dict]:
    brain = tmp_path / "brain"
    note(
        brain / "saved.md",
        """---
title: Saved archive
status: reviewed
source: codex
source_url: https://chatgpt.com/c/canonical
---
"""
        + "Introductory context. " * 30
        + "Kura archive decision retained in the canonical note.",
    )
    request = {
        "v": 1,
        "id": "cache-repair",
        "op": "search",
        "query": "Kura archive",
        "platform": "codex",
    }
    assert process_request(request, {"brain_root": brain})["ok"]
    return brain, request


@pytest.mark.parametrize(
    "changes",
    [
        {"terms": 42},
        {"terms": [{}]},
        {"terms": None},
        {"terms": ["../private/secret"]},
        {"sourceUrl": "https://example.invalid/untrusted-cache"},
        {"sourceUrl": {}},
        {"citation": "../private/forged.md"},
        {"citation": "C:/private/forged.md"},
        {"citation": None},
        {"title": []},
        {"status": []},
        {"platform": None},
        {"date": {}},
        {"excerpt": []},
        {"excerpt": "x" * 161},
        {"review": []},
        {"review": "arbitrary"},
        {"status": "pending", "review": "excerpt"},
        {"mtime_ns": True},
        {"size": True},
    ],
)
def test_warm_cache_record_validation_rebuilds_from_canonical_note(
    tmp_path: Path,
    changes: dict,
) -> None:
    brain, request = _warm_repair_fixture(tmp_path)
    cache = brain / "_meta" / "kura-archive-index.json"
    payload = json.loads(cache.read_text(encoding="utf-8"))
    payload["files"]["saved.md"].update(changes)
    cache.write_text(json.dumps(payload), encoding="utf-8")
    reply = process_request(request, {"brain_root": brain})
    assert reply["ok"] and reply["searched"]["changed"] == 1
    assert reply["items"][0]["citation"] == "saved.md"
    assert reply["items"][0]["sourceUrl"] == "https://chatgpt.com/c/canonical"
    assert "Kura" in reply["items"][0]["excerpt"]
    assert len(json.dumps(reply, ensure_ascii=False, separators=(",", ":")).encode()) <= 4096


def test_warm_search_excerpt_uses_query_instead_of_title_context(tmp_path: Path) -> None:
    brain, request = _warm_repair_fixture(tmp_path)
    reply = process_request(request, {"brain_root": brain})
    assert reply["searched"]["reused"] == 1
    assert "Kura" in reply["items"][0]["excerpt"]


def test_shape_valid_cached_output_is_replaced_by_canonical_metadata(tmp_path: Path) -> None:
    brain, request = _warm_repair_fixture(tmp_path)
    cache = brain / "_meta" / "kura-archive-index.json"
    payload = json.loads(cache.read_text(encoding="utf-8"))
    payload["files"]["saved.md"].update(
        title="Forged title", excerpt="Forged body", sourceUrl="https://chatgpt.com/c/forged"
    )
    cache.write_text(json.dumps(payload), encoding="utf-8")
    item = process_request(request, {"brain_root": brain})["items"][0]
    assert item["title"] == "Saved archive"
    assert item["sourceUrl"] == "https://chatgpt.com/c/canonical"
    assert "Kura" in item["excerpt"] and "Forged body" not in item["excerpt"]


def test_hidden_warm_record_is_excluded_before_reuse(tmp_path: Path) -> None:
    brain, request = _warm_repair_fixture(tmp_path)
    hidden = brain / ".hidden" / "forged.md"
    note(hidden, "Hidden Kura archive secret")
    cache = brain / "_meta" / "kura-archive-index.json"
    payload = json.loads(cache.read_text(encoding="utf-8"))
    record = dict(payload["files"]["saved.md"])
    record.update(
        citation=".hidden/forged.md", size=hidden.stat().st_size, mtime_ns=hidden.stat().st_mtime_ns
    )
    payload["files"][".hidden/forged.md"] = record
    cache.write_text(json.dumps(payload), encoding="utf-8")
    reply = process_request(request, {"brain_root": brain})
    assert [item["citation"] for item in reply["items"]] == ["saved.md"]


def test_canonical_pending_state_overrides_shape_valid_cached_excerpt(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    note(
        brain / "pending.md",
        """---
title: Kura pending
status: pending
source: codex
---
Private pending body.
""",
    )
    request = {
        "v": 1,
        "id": "pending-repair",
        "op": "search",
        "query": "pending",
        "platform": "codex",
    }
    process_request(request, {"brain_root": brain})
    cache = brain / "_meta" / "kura-archive-index.json"
    payload = json.loads(cache.read_text(encoding="utf-8"))
    payload["files"]["pending.md"].update(
        status="reviewed", review="excerpt", excerpt="Private pending body."
    )
    cache.write_text(json.dumps(payload), encoding="utf-8")
    reply = process_request(request, {"brain_root": brain})
    assert reply["items"][0]["review"] == "metadata-only"
    assert reply["items"][0]["excerpt"] is None
    assert "Private pending body" not in json.dumps(reply)


def test_substring_does_not_select_unrelated_replacement_passage():
    text = "Checkpoint replacement completed successfully. " + "Routine checks. " * 25
    text += "Frank asks why Monograph became the flagship instead of existing GenCreator products."
    excerpt = excerpt_archive._excerpt(text, ["replace", "monograph", "gencreator", "products"])
    assert "Monograph" in excerpt
    assert "GenCreator" in excerpt


def test_full_query_cluster_wins_over_generic_opening_heading():
    text = "AI creation: complete editions and preserved ambition. " + "Earlier work remains. " * 25
    text += (
        "The paid outcome is a complete source backed release edition "
        "with reusable creator decisions."
    )
    excerpt = excerpt_archive._excerpt(
        text,
        ["complete", "source", "backed", "release", "edition", "reusable", "creator", "decisions"],
    )
    assert "reusable creator decisions" in excerpt
    assert "release edition" in excerpt


def test_named_subject_remains_visible_when_prefix_is_not_a_query_token():
    text = "Cartridge replacement notes. " + "Unrelated material. " * 25
    text += "A cart for art materials can help the artist move between rooms."
    excerpt = excerpt_archive._excerpt(text, ["cart", "art", "artist"])
    assert "cart for art materials" in excerpt
    assert "artist" in excerpt


def test_unicode_before_named_subject_does_not_shift_source_offsets():
    text = chr(304) * 200 + " Monograph GenCreator products are the relevant subjects."
    excerpt = excerpt_archive._excerpt(text, ["monograph", "gencreator", "products"])
    assert "Monograph GenCreator products" in excerpt
    assert len(excerpt) <= excerpt_archive.MAX_EXCERPT


def saved(path: Path, word: str = "alpha", status: str = "reviewed") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (
            f"---\ntitle: Saved decision\nstatus: {status}\nsource: codex\n---\n"
            f"{word} retained decision.\n"
        ).encode()
    )


def same_stat_replace(path: Path, old: bytes, new: bytes) -> None:
    before = path.stat()
    data = path.read_bytes()
    assert old in data and len(old) == len(new)
    path.write_bytes(data.replace(old, new))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    assert path.stat().st_mtime_ns == before.st_mtime_ns


@pytest.mark.parametrize("query,expected", [("bravo", ["note.md"]), ("alpha", [])])
def test_same_stat_edit_uses_current_content(tmp_path: Path, query: str, expected: list[str]):
    brain = tmp_path / "brain"
    path = brain / "note.md"
    saved(path)
    archive.search(brain, "alpha")
    same_stat_replace(path, b"alpha", b"bravo")
    result = archive.search(brain, query)
    assert result["ok"] is True
    assert [item["citation"] for item in result["items"]] == expected
    assert result["searched"]["changed"] == 1
    if expected:
        assert "bravo" in result["items"][0]["excerpt"]


def test_same_stat_edit_invalidates_cursor(tmp_path: Path):
    brain = tmp_path / "brain"
    for label in "abcd":
        saved(brain / f"{label}.md")
    first = archive.search(brain, "decision")
    assert first["cursor"]
    same_stat_replace(brain / "d.md", b"alpha", b"bravo")
    result = archive.search(brain, "decision", cursor=first["cursor"])
    assert result["ok"] is False and result["code"] == "index_changed"


@pytest.mark.parametrize("mutation", ["replace", "pending", "delete", "invalid_utf8"])
def test_result_mutation_refuses_stale_ranked_page(tmp_path: Path, monkeypatch, mutation: str):
    brain = tmp_path / "brain"
    path = brain / "note.md"
    saved(path)
    real_load = archive.load_index

    def changed_after_index(root):
        records, measurement = real_load(root)
        if mutation == "replace":
            same_stat_replace(path, b"alpha", b"bravo")
        elif mutation == "pending":
            saved(path, "private_pending_body", "pending")
        elif mutation == "delete":
            path.unlink()
        else:
            path.write_bytes(b"\xff\xfe\x00")
        return records, measurement

    monkeypatch.setattr(archive, "load_index", changed_after_index)
    result = archive.search(brain, "alpha")
    assert result["ok"] is False and result["code"] == "index_changed"
    assert not result.get("items") and not result.get("cursor")
    assert "private_pending_body" not in json.dumps(result)


def test_legacy_stat_only_cache_rebuilds(tmp_path: Path):
    brain = tmp_path / "brain"
    saved(brain / "note.md")
    archive.search(brain, "alpha")
    path = brain / archive.INDEX_RELATIVE
    cache = json.loads(path.read_bytes())
    cache["files"]["note.md"].pop("sha256", None)
    cache["version"] = 1
    path.write_bytes(json.dumps(cache).encode("utf-8"))
    result = archive.search(brain, "alpha")
    assert result["ok"] and result["searched"]["changed"] == 1
    rebuilt = json.loads(path.read_bytes())
    assert rebuilt["version"] == 2
    assert len(rebuilt["files"]["note.md"]["sha256"]) == 64


@pytest.mark.parametrize("status", ["needs-summary", "triage"])
def test_native_capture_filter_keeps_source_identity_and_pending_privacy(tmp_path, status):
    brain = tmp_path / "brain"
    note(
        brain / "capture.md",
        f"""---
title: Habitat capture decision
status: {status}
source: idea-capture
---
CAPTURE_BODY_SENTINEL habitat learning.
""",
    )
    note(
        brain / "provider.md",
        """---
title: Habitat provider decision
status: reviewed
source: codex
---
PROVIDER_BODY_SENTINEL habitat learning.
""",
    )
    response = process_request(
        {
            "v": 1,
            "id": "capture-search",
            "op": "search",
            "query": "habitat",
            "platform": "idea-capture",
        },
        {"brain_root": brain},
    )
    assert response["ok"] is True
    assert [item["citation"] for item in response["items"]] == ["capture.md"]
    assert response["items"][0]["platform"] == "idea-capture"
    assert "PROVIDER_BODY_SENTINEL" not in json.dumps(response)
    if status == "needs-summary":
        assert response["items"][0]["excerpt"] is None
        assert "CAPTURE_BODY_SENTINEL" not in json.dumps(response)
    else:
        assert "CAPTURE_BODY_SENTINEL" in response["items"][0]["excerpt"]
