"""End-to-end ingestion test with mocked summarizer."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import frontmatter

import pytest
from click.testing import CliRunner

from sbo_ingestion.ingest import _detect_format, cli, ingest
from sbo_ingestion.summarize import Summary


@patch("sbo_ingestion.ingest.summarize")
def test_ingest_claude_ai_writes_two_pairs(
    mock_summarize: MagicMock,
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    brain, private = tmp_vault_pair
    mock_summarize.return_value = Summary(title="Test", tldr="t", insights=("i",))
    result = ingest(claude_ai_export_path, brain_root=brain, private_root=private, api_key="test")
    # Fixture has 2 conversations
    assert len(result) == 2
    # Both raw files exist in private/
    raw_files = list((private / "chat-history" / "claude-ai").glob("*.md"))
    assert len(raw_files) == 2
    # Both brain files exist in _inbox/ (excluding the derived _INDEX.md corpus map)
    brain_files = [
        p for p in (brain / "_inbox" / "claude-ai").glob("*.md") if p.name != "_INDEX.md"
    ]
    assert len(brain_files) == 2
    # _INDEX.md corpus map is also written, newest-first
    assert (brain / "_inbox" / "claude-ai" / "_INDEX.md").exists()


@patch("sbo_ingestion.ingest.summarize")
def test_ingest_chatgpt_routes_correctly(
    mock_summarize: MagicMock,
    chatgpt_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    brain, private = tmp_vault_pair
    mock_summarize.return_value = Summary(title="Test", tldr="t")
    result = ingest(chatgpt_export_path, brain_root=brain, private_root=private, api_key="test")
    assert len(result) == 1
    assert (private / "chat-history" / "chatgpt").exists()
    assert (brain / "_inbox" / "chatgpt").exists()


def test_ingest_chatgpt_sharded_zip_without_extraction(
    chatgpt_export_path: Path,
    tmp_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    source = json.loads(chatgpt_export_path.read_text(encoding="utf-8"))
    second = dict(source[0])
    second["id"] = "conv-bbbb-2222"
    second["title"] = source[0]["title"]  # exercise collision-safe brain filenames
    export_zip = tmp_path / "chatgpt-export.zip"
    with ZipFile(export_zip, "w") as archive:
        archive.writestr("conversations-001.json", json.dumps([second]))
        archive.writestr("conversations-000.json", json.dumps(source))

    brain, private = tmp_vault_pair
    result = ingest(export_zip, brain_root=brain, private_root=private, mode="agent")

    assert len(result) == 2
    assert len({item.brain_path for item in result}) == 2
    assert all(item.private_path.exists() for item in result)
    assert (brain / "_inbox" / "chatgpt" / "_INDEX.md").exists()
    receipts = list((private / "_distill" / "imports").glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["selected_members"] == [
        "conversations-000.json",
        "conversations-001.json",
    ]
    assert receipt["conversation_count"] == 2
    assert "source_path" not in receipt
    assert all("C:\\" not in member for member in receipt["selected_members"])


def test_reingest_preserves_existing_brain_content(
    chatgpt_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    brain, private = tmp_vault_pair
    first = ingest(chatgpt_export_path, brain_root=brain, private_root=private, mode="agent")
    note = frontmatter.load(first[0].brain_path)
    note["status"] = "distilled"
    note.content = "# Durable synthesis\n\nKeep this curated analysis.\n"
    first[0].brain_path.write_text(frontmatter.dumps(note), encoding="utf-8")

    second = ingest(chatgpt_export_path, brain_root=brain, private_root=private, mode="agent")
    preserved = frontmatter.load(second[0].brain_path)

    assert second[0].brain_preserved is True
    assert preserved["status"] == "distilled"
    assert "Keep this curated analysis." in preserved.content


def test_reingest_finds_promoted_note_outside_inbox(
    chatgpt_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    brain, private = tmp_vault_pair
    first = ingest(chatgpt_export_path, brain_root=brain, private_root=private, mode="agent")
    promoted_dir = brain / "notes" / "learnings"
    promoted_dir.mkdir(parents=True)
    promoted_path = promoted_dir / "durable-chatgpt-learning.md"
    first[0].brain_path.replace(promoted_path)
    promoted = frontmatter.load(promoted_path)
    promoted["status"] = "distilled"
    promoted.content = "# Promoted insight\n\nThis note has left the inbox.\n"
    promoted_path.write_text(frontmatter.dumps(promoted), encoding="utf-8")

    second = ingest(chatgpt_export_path, brain_root=brain, private_root=private, mode="agent")

    assert second[0].brain_path == promoted_path
    assert second[0].brain_preserved is True
    assert "This note has left the inbox." in promoted_path.read_text(encoding="utf-8")
    inbox_notes = [
        path
        for path in (brain / "_inbox" / "chatgpt").glob("*.md")
        if not path.name.startswith("_")
    ]
    assert inbox_notes == []


def test_ingest_unknown_format_raises(
    tmp_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    brain, private = tmp_vault_pair
    bogus = tmp_path / "bogus.txt"
    bogus.write_text("not an export")
    try:
        ingest(bogus, brain_root=brain, private_root=private, api_key="test")
    except ValueError as e:
        assert "format" in str(e).lower() or "unknown" in str(e).lower()
    else:
        raise AssertionError("Should have raised ValueError for unknown format")


def test_ingest_dry_run_skips_api(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Dry-run must not call the Anthropic API and must still produce both files."""
    brain, private = tmp_vault_pair
    # No api_key, no mock — proves no network call happens.
    result = ingest(
        claude_ai_export_path,
        brain_root=brain,
        private_root=private,
        dry_run=True,
    )
    assert len(result) == 2
    assert all(r.private_path.exists() for r in result)
    assert all(r.brain_path.exists() for r in result)
    # Stub-summary marker visible in brain output
    sample = result[0].brain_path.read_text(encoding="utf-8")
    assert "dry-run" in sample.lower()


def test_mode_api_requires_api_key(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Explicit mode=api without an api_key must raise — never silently fall through to default."""
    brain, private = tmp_vault_pair
    try:
        ingest(
            claude_ai_export_path,
            brain_root=brain,
            private_root=private,
            mode="api",
        )
    except ValueError as e:
        assert "api_key" in str(e).lower()
    else:
        raise AssertionError("Should have raised ValueError when mode=api and api_key missing")


# ---------------------------------------------------------------------------
# v0.2.0 — agent-mode contracts
# ---------------------------------------------------------------------------


def test_default_mode_is_agent(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """No flags = agent mode. Default must not be 'api' (would surprise-bill users)."""
    brain, private = tmp_vault_pair
    # No api_key, no mode, no dry_run — must NOT raise, must NOT call Anthropic.
    result = ingest(claude_ai_export_path, brain_root=brain, private_root=private)
    assert len(result) == 2


def test_agent_mode_writes_needs_summary_status(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Agent-mode brain stubs carry status=needs-summary so /distill-inbox can find them."""
    import frontmatter

    brain, private = tmp_vault_pair
    result = ingest(
        claude_ai_export_path,
        brain_root=brain,
        private_root=private,
        mode="agent",
    )
    for r in result:
        post = frontmatter.load(r.brain_path)
        assert post.get("status") == "needs-summary"
        assert "needs-summary" in (post.get("tags") or [])


def test_agent_mode_skips_anthropic_call(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Agent-mode must not construct an Anthropic client or hit the network."""
    brain, private = tmp_vault_pair
    # No api_key, no mock — proves no network call. Would error if summarize() was reached.
    result = ingest(
        claude_ai_export_path,
        brain_root=brain,
        private_root=private,
        mode="agent",
    )
    assert len(result) == 2
    # Sentinel string in the agent-mode stub body
    sample = result[0].brain_path.read_text(encoding="utf-8")
    assert "/distill-inbox" in sample


def test_agent_mode_writes_audit_log_in_private(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Audit log lives at private/_distill/audit.jsonl — inside private/, never brain/."""
    import json

    brain, private = tmp_vault_pair
    ingest(
        claude_ai_export_path,
        brain_root=brain,
        private_root=private,
        mode="agent",
    )
    audit_path = private / "_distill" / "audit.jsonl"
    assert audit_path.exists(), "audit log must be written inside private/_distill/"
    lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2  # fixture has 2 conversations
    for line in lines:
        entry = json.loads(line)
        assert entry["action"] == "ingest"
        assert entry["mode"] == "agent"
        assert entry["format"] == "claude.ai"
        assert "ts" in entry
        assert "conversation_id" in entry


def test_audit_log_never_lands_in_brain(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Privacy contract: the audit log must never be reachable via the brain vault."""
    brain, private = tmp_vault_pair
    ingest(
        claude_ai_export_path,
        brain_root=brain,
        private_root=private,
        mode="agent",
    )
    # Walk the brain tree — no audit.jsonl anywhere
    brain_audits = list(brain.rglob("audit.jsonl"))
    assert brain_audits == [], f"audit log must NOT appear in brain vault: {brain_audits}"


def test_legacy_dry_run_flag_still_implies_dry_run(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Back-compat: --dry-run continues to work as a legacy alias for --mode dry-run."""
    brain, private = tmp_vault_pair
    result = ingest(
        claude_ai_export_path,
        brain_root=brain,
        private_root=private,
        dry_run=True,
    )
    sample = result[0].brain_path.read_text(encoding="utf-8")
    assert "dry-run" in sample.lower()


def test_explicit_mode_overrides_legacy_flags(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """If --mode is set, --dry-run and --api-key precedence are ignored for mode resolution."""
    brain, private = tmp_vault_pair
    # dry_run=True but mode='agent' — agent wins, no dry-run sentinel
    result = ingest(
        claude_ai_export_path,
        brain_root=brain,
        private_root=private,
        mode="agent",
        dry_run=True,
    )
    sample = result[0].brain_path.read_text(encoding="utf-8")
    assert "/distill-inbox" in sample  # agent-mode sentinel


# ---------------------------------------------------------------------------
# Sharded exports and format detection
# ---------------------------------------------------------------------------


def test_ingest_directory_of_shards(
    chatgpt_sharded_dir: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """A directory of shards ingests as one run: 1 convo in shard 000, 2 in shard 001."""
    brain, private = tmp_vault_pair
    result = ingest(chatgpt_sharded_dir, brain_root=brain, private_root=private)
    assert len(result) == 3
    assert len(list((brain / "_inbox" / "chatgpt").glob("*.md"))) == 3


def test_ingest_glob_of_shards(
    chatgpt_sharded_dir: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """A glob selects and orders shards the same way a directory does."""
    brain, private = tmp_vault_pair
    result = ingest(
        chatgpt_sharded_dir / "conversations-*.json",
        brain_root=brain,
        private_root=private,
    )
    assert len(result) == 3


def test_shards_processed_in_sorted_order(
    chatgpt_sharded_dir: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Shard 000 must be ingested before shard 001, whatever order the FS lists them."""
    brain, private = tmp_vault_pair
    ingest(chatgpt_sharded_dir, brain_root=brain, private_root=private)
    sources = [
        json.loads(line)["source"]
        for line in (private / "_distill" / "audit.jsonl")
        .read_text(encoding="utf-8")
        .strip()
        .split("\n")
    ]
    assert sources == [
        "conversations-000.json",
        "conversations-001.json",
        "conversations-001.json",
    ]


def test_sharded_audit_log_is_one_coherent_run(
    chatgpt_sharded_dir: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """One audit line per conversation across all shards, each naming its shard."""
    brain, private = tmp_vault_pair
    ingest(chatgpt_sharded_dir, brain_root=brain, private_root=private)
    lines = (private / "_distill" / "audit.jsonl").read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    entries = [json.loads(line) for line in lines]
    assert {e["action"] for e in entries} == {"ingest"}
    assert {e["format"] for e in entries} == {"chatgpt"}
    assert len({e["conversation_id"] for e in entries}) == 3


def test_empty_directory_raises(
    tmp_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    brain, private = tmp_vault_pair
    empty = tmp_path / "no-exports"
    empty.mkdir()
    with pytest.raises(ValueError, match="No .json or .jsonl export files"):
        ingest(empty, brain_root=brain, private_root=private)


def test_array_shaped_claude_export_routes_to_claude(
    claude_ai_json_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """A JSON array whose objects carry chat_messages is Claude.ai, not ChatGPT."""
    assert _detect_format(claude_ai_json_export_path) == "claude.ai"
    brain, private = tmp_vault_pair
    result = ingest(claude_ai_json_export_path, brain_root=brain, private_root=private)
    assert len(result) == 2
    assert len(list((brain / "_inbox" / "claude-ai").glob("*.md"))) == 2
    assert list((brain / "_inbox" / "chatgpt").glob("*.md")) == []


def test_array_shaped_chatgpt_export_still_routes_to_chatgpt(
    chatgpt_export_path: Path,
) -> None:
    """The mapping key keeps ChatGPT arrays on the ChatGPT handler."""
    assert _detect_format(chatgpt_export_path) == "chatgpt"


def test_jsonl_export_routes_to_claude(claude_ai_export_path: Path) -> None:
    assert _detect_format(claude_ai_export_path) == "claude.ai"


# ---------------------------------------------------------------------------
# api mode is opt-in only — a bare ANTHROPIC_API_KEY must never bill the user
# ---------------------------------------------------------------------------


def test_ambient_api_key_does_not_select_api_mode(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exported ANTHROPIC_API_KEY must leave the default at agent mode."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-be-used")
    brain, private = tmp_vault_pair
    result = CliRunner().invoke(
        cli,
        [
            str(claude_ai_export_path),
            "--brain-root",
            str(brain),
            "--private-root",
            str(private),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "mode:    agent" in result.output
    for r in (brain / "_inbox" / "claude-ai").glob("*.md"):
        assert "needs-summary" in r.read_text(encoding="utf-8")


def test_mode_api_without_key_prints_one_line_error(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--mode api with no key exits cleanly — a message, not a traceback."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    brain, private = tmp_vault_pair
    result = CliRunner().invoke(
        cli,
        [
            str(claude_ai_export_path),
            "--brain-root",
            str(brain),
            "--private-root",
            str(private),
            "--mode",
            "api",
        ],
    )
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output
    assert "[error] mode=api requires --api-key" in result.output

# v0.3.0 — corpus index + memory export wiring
# ---------------------------------------------------------------------------


def test_ingest_emits_index(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Every ingest drops a newest-first _INDEX.md mapping the whole corpus."""
    brain, private = tmp_vault_pair
    ingest(claude_ai_export_path, brain_root=brain, private_root=private, mode="agent")
    index_path = brain / "_inbox" / "claude-ai" / "_INDEX.md"
    assert index_path.exists()
    post = frontmatter.load(index_path)
    assert post.metadata["conversation_count"] == 2
    # The first fixture conversation carries an export summary — it must show in the map.
    assert "Two-vault architecture" in post.content


def test_ingest_autodetects_sibling_memories(
    claude_ai_export_path: Path,
    memories_list_path: Path,
    tmp_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """A memories.json sitting next to the export is picked up with no flag."""
    brain, private = tmp_vault_pair
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    export_copy = export_dir / "conversations.jsonl"
    shutil.copy(claude_ai_export_path, export_copy)
    shutil.copy(memories_list_path, export_dir / "memories.json")

    ingest(export_copy, brain_root=brain, private_root=private, mode="agent")
    mem_path = brain / "_inbox" / "claude-ai" / "_memory-export.md"
    assert mem_path.exists()
    assert frontmatter.load(mem_path).metadata["memory_count"] == 3


def test_ingest_explicit_memories_path(
    claude_ai_export_path: Path,
    memories_dict_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """An explicit memories_path is honored even with no sibling file."""
    brain, private = tmp_vault_pair
    ingest(
        claude_ai_export_path,
        brain_root=brain,
        private_root=private,
        mode="agent",
        memories_path=memories_dict_path,
    )
    mem_path = brain / "_inbox" / "claude-ai" / "_memory-export.md"
    assert mem_path.exists()


def test_ingest_no_memories_is_fine(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """No memories.json anywhere -> no _memory-export.md, no error."""
    brain, private = tmp_vault_pair
    ingest(claude_ai_export_path, brain_root=brain, private_root=private, mode="agent")
    assert not (brain / "_inbox" / "claude-ai" / "_memory-export.md").exists()
