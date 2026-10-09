"""Native rollout preservation, routing and two-vault failure behavior."""

import json
from hashlib import sha256

import frontmatter
import pytest

from sbo_ingestion.handlers import codex
from sbo_ingestion.ingest import _detect_format, ingest

SESSION = "01a10c15-e8d5-73f0-ab17-f23c4031d2db"
STAMP = "2026-10-05T12:42:04.889Z"


def record(kind, payload):
    return {"timestamp": STAMP, "type": kind, "payload": payload}


def message(role, text):
    return record("response_item", {"type": "message", "role": role,
                                    "content": [{"type": "input_text", "text": text}]})


def write_source(tmp_path, extra=()):
    rows = [record("session_meta", {"id": SESSION, "timestamp": STAMP}),
            message("developer", "Setup instructions are not a founder request."),
            message("user", "Preserve the exact prompt.\n\n  Whitespace and \u2603 matter.  "),
            record("event_msg", {"type": "user_message", "message": "Duplicate event"}),
            record("response_item", {"type": "function_call_output",
                                     "output": "SECRET TOOL TRACE"}),
            message("assistant", "Keep remaining work open."), *extra]
    path = tmp_path / "rollout.jsonl"
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n",
                    encoding="utf-8")
    return path


def test_native_identity_routes_and_preserves_exact_text_and_lineage(tmp_path):
    path = write_source(tmp_path)
    assert _detect_format(path) == "codex"
    convo = next(codex.parse_export(path))
    assert convo.uuid == SESSION
    assert [m.sender for m in convo.messages] == ["developer", "human", "assistant"]
    assert convo.messages[1].text == (
        "Preserve the exact prompt.\n\n  Whitespace and \u2603 matter.  "
    )
    assert convo.source_sha256 == sha256(path.read_bytes()).hexdigest()
    assert convo.source_lines == (2, 3, 6)
    raw = convo.to_raw_markdown()
    assert "source line 3" in raw and "founder authorship" in raw
    assert "SECRET TOOL TRACE" not in raw and "Duplicate event" not in raw


def test_compaction_context_is_explicitly_derived_and_attachments_stay_in_source(tmp_path):
    path = write_source(tmp_path, [record("compacted", {"message": "Earlier decisions"}),
        record("response_item", {"type": "message", "role": "user", "content": [
            {"type": "input_image", "image_url": "data:image/png;base64,PRIVATE"}]})])
    convo = next(codex.parse_export(path))
    assert convo.messages[-2].text == "[Derived compaction summary]\nEarlier decisions"
    assert "Non-text input_image remains in original source line 8" in convo.messages[-1].text
    assert "base64,PRIVATE" not in convo.to_raw_markdown()


def test_final_prompt_whitespace_is_not_trimmed_by_markdown_rendering(tmp_path):
    text = "Final request.  \n\n  "
    convo = next(codex.parse_export(write_source(tmp_path, [message("user", text)])))
    assert convo.messages[-1].text == text
    assert text + "\n\n" in convo.to_raw_markdown()


def test_agent_intake_writes_private_text_and_preserves_curated_note(tmp_path, monkeypatch):
    import sbo_ingestion.ingest as module
    monkeypatch.setattr(module, "summarize", lambda *a, **k: pytest.fail("No API call allowed"))
    source = write_source(tmp_path)
    brain, private = tmp_path / "brain", tmp_path / "private"
    result, = ingest(source, brain_root=brain, private_root=private, mode="agent")
    raw = frontmatter.load(result.private_path)
    stub = frontmatter.load(result.brain_path)
    assert raw["source"] == "codex" and raw["message_count"] == 3
    assert "Whitespace and \u2603 matter." in raw.content
    assert "Whitespace" not in stub.content and "Setup instructions" not in stub.content
    assert stub["status"] == "needs-summary"
    stub.content = "Reviewed decision with source citation."
    stub["status"] = "reviewed"
    result.brain_path.write_text(frontmatter.dumps(stub), encoding="utf-8")
    before = result.brain_path.read_bytes()
    repeated = ingest(source, brain_root=brain, private_root=private, mode="agent")
    assert repeated == [] and result.brain_path.read_bytes() == before
    assert len(list((brain / "_inbox" / "codex").glob("*.md"))) == 2  # note and index


def test_native_source_never_discovers_or_copies_sibling_memories(tmp_path, monkeypatch):
    import sbo_ingestion.ingest as module
    source = write_source(tmp_path)
    (tmp_path / "memories.json").write_text('{"sensitive": "PRIVATE MEMORY"}', encoding="utf-8")
    monkeypatch.setattr(module.memories_handler, "write_memory_export",
                        lambda *a, **k: pytest.fail("Native intake must not export memories"))
    brain, private = tmp_path / "brain", tmp_path / "private"
    ingest(source, brain_root=brain, private_root=private)
    assert not list(brain.rglob("_memory-export.md"))
    assert all("PRIVATE MEMORY" not in x.read_text(encoding="utf-8") for x in brain.rglob("*.md"))
    with pytest.raises(ValueError, match="only its selected session"):
        ingest(source, brain_root=brain, private_root=private,
               memories_path=tmp_path / "memories.json")


def test_changed_and_shorter_sources_archive_revisions_and_keep_curated_note(tmp_path):
    source = write_source(tmp_path)
    brain, private = tmp_path / "brain", tmp_path / "private"
    initial, = ingest(source, brain_root=brain, private_root=private)
    old_raw = initial.private_path.read_text(encoding="utf-8")
    post = frontmatter.load(initial.brain_path)
    post.content, post["status"] = "Human-curated decision.", "reviewed"
    initial.brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    curated = initial.brain_path.read_bytes()
    with source.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(message("user", "New unfinished demand.")) + "\n")
    changed, = ingest(source, brain_root=brain, private_root=private)
    assert changed.brain_preserved and changed.brain_path.read_bytes() == curated
    assert "New unfinished demand." in changed.private_path.read_text(encoding="utf-8")
    history = list((private / "_distill" / "codex" / "history").rglob("*.md"))
    assert len(history) == 1 and history[0].read_text(encoding="utf-8") == old_raw
    receipts = list((private / "_distill" / "codex").glob("*.json"))
    assert len(receipts) == 1 and json.loads(receipts[0].read_text())["refresh_pending"] is True
    extended = changed.private_path.read_text(encoding="utf-8")
    write_source(tmp_path)
    shortened, = ingest(source, brain_root=brain, private_root=private)
    assert shortened.brain_path.read_bytes() == curated
    history = list((private / "_distill" / "codex" / "history").rglob("*.md"))
    assert len(history) == 2 and extended in [x.read_text(encoding="utf-8") for x in history]


def test_multiple_sessions_and_index_loss_keep_full_corpus(tmp_path):
    source = write_source(tmp_path)
    brain, private = tmp_path / "brain", tmp_path / "private"
    ingest(source, brain_root=brain, private_root=private)
    second = tmp_path / "second"
    second.mkdir()
    second_source = write_source(second)
    other = "01a10c15-e8d5-73f0-ab17-f23c4031d2dc"
    second_source.write_text(second_source.read_text(encoding="utf-8").replace(SESSION, other),
                             encoding="utf-8")
    ingest(second_source, brain_root=brain, private_root=private)
    index = brain / "_inbox" / "codex" / "_INDEX.md"
    assert frontmatter.load(index)["conversation_count"] == 2
    assert SESSION in index.read_text() and other in index.read_text()
    index.unlink()
    assert ingest(source, brain_root=brain, private_root=private) == []
    assert frontmatter.load(index)["conversation_count"] == 2


def test_assistant_analysis_channel_is_excluded_and_final_channel_retained(tmp_path):
    analysis = message("assistant", "PRIVATE ANALYSIS")
    analysis["payload"]["channel"] = "analysis"
    final = message("assistant", "Visible final result.")
    final["payload"]["channel"] = "final"
    convo = next(codex.parse_export(write_source(tmp_path, [analysis, final])))
    assert "PRIVATE ANALYSIS" not in convo.to_raw_markdown()
    assert convo.messages[-1].text == "Visible final result."


def test_promoted_note_keeps_source_date_and_curated_bytes_in_rebuilt_index(tmp_path):
    source = write_source(tmp_path)
    brain, private = tmp_path / "brain", tmp_path / "private"
    result, = ingest(source, brain_root=brain, private_root=private)
    destination = brain / "notes" / "reviewed-work.md"
    destination.parent.mkdir()
    result.brain_path.rename(destination)
    before = destination.read_bytes()
    assert ingest(source, brain_root=brain, private_root=private) == []
    index = (brain / "_inbox" / "codex" / "_INDEX.md").read_text(encoding="utf-8")
    assert "2026-10-05" in index and "undated" not in index
    assert destination.read_bytes() == before


@pytest.mark.parametrize("extra,match", [
    ([record("session_meta", {"id": "../../private", "timestamp": STAMP})], "identity"),
    ([record("session_meta", {"id": "01a10c15-e8d5-73f0-ab17-f23c4031d2dc",
                              "timestamp": STAMP})], "Conflicting"),
    ([message("unknown", "unattributed")], "Invalid Codex message"),
    ([record("response_item", {"type": "message", "role": "user", "content": [
        {"type": "output_text", "text": {"unsafe": "shape"}}]})], "Invalid Codex text"),
    ([record("response_item", {"type": "message", "role": "user", "content": [
        {"type": "future_content", "payload": "unknown"}]})], "Unsupported"),
    ([{"timestamp": "yesterday", "type": "compacted", "payload": {"message": "summary"}}],
     "timestamp"),
])
def test_bad_source_fails_before_any_vault_write(tmp_path, extra, match):
    source = write_source(tmp_path, extra)
    brain, private = tmp_path / "brain", tmp_path / "private"
    with pytest.raises(ValueError, match=match):
        ingest(source, brain_root=brain, private_root=private, mode="agent")
    assert not brain.exists() and not private.exists()


def test_truncated_json_and_bounded_source_are_not_partial_success(tmp_path, monkeypatch):
    source = write_source(tmp_path)
    with source.open("a", encoding="utf-8") as handle:
        handle.write('{"type":')
    with pytest.raises(ValueError, match="Invalid Codex JSON"):
        next(codex.parse_export(source))
    source = write_source(tmp_path)
    monkeypatch.setattr(codex, "MAX_TEXT_BYTES", 4)
    with pytest.raises(ValueError, match="retained text"):
        next(codex.parse_export(source))


def test_disjoint_vault_boundary_and_older_claude_jsonl_routing(tmp_path):
    source = write_source(tmp_path)
    with pytest.raises(ValueError, match="non-overlapping"):
        ingest(source, brain_root=tmp_path / "private" / "brain", private_root=tmp_path / "private")
    source.write_text(json.dumps({"uuid": "claude", "chat_messages": []}) + "\n",
                      encoding="utf-8")
    assert _detect_format(source) == "claude.ai"


def test_message_before_identity_and_source_change_are_refused(tmp_path, monkeypatch):
    source = write_source(tmp_path)
    source.write_text(json.dumps(message("user", "No identity")) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="metadata must precede"):
        next(codex.parse_export(source))
    source = write_source(tmp_path)
    original = json.loads
    changed = False

    def append_while_reading(value, *args, **kwargs):
        nonlocal changed
        parsed = original(value, *args, **kwargs)
        if not changed:
            changed = True
            with source.open("a", encoding="utf-8") as handle:
                handle.write("\n")
        return parsed

    monkeypatch.setattr(codex.json, "loads", append_while_reading)
    with pytest.raises(ValueError, match="changed during intake"):
        next(codex.parse_export(source))
