import json

import frontmatter
import pytest
from click.testing import CliRunner

from sbo_ingestion.distill import cli, complete_stub, find_stubs


def _stub(brain_root, name, *, status="needs-summary", convo_id="c-1"):
    path = brain_root / "_inbox" / "chatgpt" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(
        content="**TL;DR:** (agent-mode: summary pending.)",
        status=status,
        conversation_id=convo_id,
        private_file=f"chat-history/chatgpt/{name}.md",
        tags=["draft", "needs-summary"],
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


def test_find_stubs_returns_only_pending(tmp_path):
    brain = tmp_path / "brain"
    _stub(brain, "pending-one")
    _stub(brain, "already-done", status="triage", convo_id="c-2")

    pending = find_stubs(brain)

    assert [p["conversation_id"] for p in pending] == ["c-1"]
    assert pending[0]["private_file"] == "chat-history/chatgpt/pending-one.md"


def test_find_stubs_on_missing_inbox_is_empty(tmp_path):
    assert find_stubs(tmp_path / "nope") == []


def test_complete_flips_status_and_writes_audit(tmp_path):
    brain, private = tmp_path / "brain", tmp_path / "private"
    stub = _stub(brain, "one")

    complete_stub(stub, private, agent="claude-code")

    post = frontmatter.load(stub)
    assert post["status"] == "triage"
    assert "needs-summary" not in post["tags"]

    entries = [
        json.loads(line)
        for line in (private / "_distill" / "audit.jsonl").read_text().splitlines()
    ]
    assert [e["action"] for e in entries] == ["distill"]
    assert entries[0]["conversation_id"] == "c-1"
    assert entries[0]["agent"] == "claude-code"


def test_complete_refuses_an_already_distilled_stub(tmp_path):
    brain, private = tmp_path / "brain", tmp_path / "private"
    stub = _stub(brain, "done", status="triage")

    with pytest.raises(Exception, match="not awaiting a summary"):
        complete_stub(stub, private, agent="claude-code")

    assert not (private / "_distill" / "audit.jsonl").exists()


def test_status_flip_and_audit_do_not_drift(tmp_path):
    """The audit log is the user's record that a model read their private vault."""
    brain, private = tmp_path / "brain", tmp_path / "private"
    stub = _stub(brain, "one")

    complete_stub(stub, private, agent="claude-code")
    audit_lines = (private / "_distill" / "audit.jsonl").read_text().splitlines()

    with pytest.raises(Exception):
        complete_stub(stub, private, agent="claude-code")

    assert (private / "_distill" / "audit.jsonl").read_text().splitlines() == audit_lines


def test_list_command_emits_json(tmp_path):
    brain = tmp_path / "brain"
    _stub(brain, "one")

    result = CliRunner().invoke(cli, ["list", "--brain-root", str(brain)])

    assert result.exit_code == 0
    assert json.loads(result.output)[0]["conversation_id"] == "c-1"


def test_redacted_title_policy_keeps_titles_out_of_brain(tmp_path, monkeypatch):
    """The LLM-readable vault must not become a titled index of the private one."""
    from sbo_ingestion.dual_write import write_pair
    from sbo_ingestion.handlers.claude_ai import Conversation
    from sbo_ingestion.summarize import Summary

    monkeypatch.setenv("SBO_TITLE_POLICY", "redacted")
    convo = Conversation(
        uuid="ff63a356-ebf9-4d79-b486-a672bb09519b",
        title="Painful Spot: Medical Evaluation",
        platform="chatgpt",
        created_at="2026-05-19T10:00:00+00:00",
        updated_at="2026-05-19T10:00:00+00:00",
        messages=[],
    )
    result = write_pair(
        convo,
        Summary(title=convo.title, tldr="", insights=[], decisions=[], open_questions=[]),
        brain_root=tmp_path / "brain",
        private_root=tmp_path / "private",
    )

    assert "medical" not in result.brain_path.name.lower()
    assert "medical" not in result.brain_path.read_text(encoding="utf-8").lower()
    # the real title is still available where the distilling agent reads it
    assert "Medical Evaluation" in result.private_path.read_text(encoding="utf-8")
