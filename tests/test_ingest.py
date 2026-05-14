"""End-to-end ingestion test with mocked summarizer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from sbo_ingestion.ingest import ingest
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
    # Both brain files exist in _inbox/
    brain_files = list((brain / "_inbox" / "claude-ai").glob("*.md"))
    assert len(brain_files) == 2


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
