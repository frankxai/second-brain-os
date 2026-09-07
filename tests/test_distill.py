import json
import os
import stat

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


def test_failed_note_replace_preserves_note_and_has_no_receipt(tmp_path, monkeypatch):
    from sbo_ingestion import audit

    stub = _stub(tmp_path / "brain", "one")
    before = stub.read_bytes()
    private = tmp_path / "private"
    with monkeypatch.context() as patch:
        patch.setattr(audit.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
        with pytest.raises(OSError, match="disk full"):
            complete_stub(stub, private, agent="claude-code")
    assert stub.read_bytes() == before
    assert not (private / "_distill" / "audit.jsonl").exists()
    assert not list(stub.parent.glob("*.tmp"))
    complete_stub(stub, private, agent="claude-code")
    assert frontmatter.load(stub)["status"] == "triage"


def test_failed_audit_is_discoverable_and_retry_keeps_original_attribution(tmp_path, monkeypatch):
    from sbo_ingestion import audit
    from sbo_ingestion.distill import PENDING_RECEIPT

    brain, private = tmp_path / "brain", tmp_path / "private"
    stub = _stub(brain, "one")
    real_replace = audit.os.replace

    def fail_audit(source, target):
        if target.name == "audit.jsonl":
            raise OSError("audit unavailable")
        return real_replace(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(audit.os, "replace", fail_audit)
        with pytest.raises(OSError, match="audit unavailable"):
            complete_stub(stub, private, agent="original-agent", model="original-model")
    assert frontmatter.load(stub)["status"] == "triage"
    assert find_stubs(brain)[0]["receipt_pending"] is True
    assert not (private / "_distill" / "audit.jsonl").exists()
    receipt = complete_stub(stub, private, agent="retry-agent")
    entries = [json.loads(line) for line in receipt.read_text().splitlines()]
    assert len(entries) == 1
    assert entries[0]["agent"] == "original-agent"
    assert entries[0]["model"] == "original-model"
    assert PENDING_RECEIPT not in frontmatter.load(stub)
    assert find_stubs(brain) == []


def test_retry_after_receipt_before_marker_cleanup_does_not_duplicate(tmp_path, monkeypatch):
    from sbo_ingestion import audit
    from sbo_ingestion.distill import PENDING_RECEIPT

    brain, private = tmp_path / "brain", tmp_path / "private"
    stub = _stub(brain, "one")
    real_write = audit.atomic_write_text

    def fail_cleanup(path, text):
        if path == stub.resolve() and PENDING_RECEIPT not in text:
            raise OSError("cleanup interrupted")
        return real_write(path, text)

    with monkeypatch.context() as patch:
        patch.setattr(audit, "atomic_write_text", fail_cleanup)
        with pytest.raises(OSError, match="cleanup interrupted"):
            complete_stub(stub, private, agent="original")
    audit_path = private / "_distill" / "audit.jsonl"
    before = audit_path.read_bytes()
    complete_stub(stub, private, agent="retry")
    assert audit_path.read_bytes() == before
    assert len(before.splitlines()) == 1


def test_changed_summary_cannot_reuse_pending_receipt(tmp_path, monkeypatch):
    from sbo_ingestion import audit

    stub = _stub(tmp_path / "brain", "one")
    private = tmp_path / "private"
    with monkeypatch.context() as patch:
        patch.setattr(audit, "record_distill", lambda *a, **kw: (_ for _ in ()).throw(OSError("offline")))
        with pytest.raises(OSError):
            complete_stub(stub, private, agent="original")
    post = frontmatter.load(stub)
    post.content = "A later, different summary"
    stub.write_text(frontmatter.dumps(post), encoding="utf-8")
    with pytest.raises(Exception, match="Pending completion changed"):
        complete_stub(stub, private, agent="retry")
    assert not (private / "_distill" / "audit.jsonl").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_atomic_replacement_preserves_private_permissions(tmp_path):
    from sbo_ingestion.audit import atomic_write_text

    path = tmp_path / "private.jsonl"
    path.write_text("old")
    path.chmod(0o600)
    atomic_write_text(path, "new")
    assert path.read_text() == "new"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    created = tmp_path / "created.jsonl"
    atomic_write_text(created, "private")
    assert stat.S_IMODE(created.stat().st_mode) == 0o600


@pytest.mark.parametrize("marker", ["invalid", {"completion_id": 42}, ["not", "a", "mapping"]])
def test_malformed_pending_marker_is_a_controlled_error(tmp_path, marker):
    from sbo_ingestion.distill import PENDING_RECEIPT

    stub = _stub(tmp_path / "brain", "one")
    post = frontmatter.load(stub)
    post[PENDING_RECEIPT] = marker
    stub.write_text(frontmatter.dumps(post), encoding="utf-8")
    result = CliRunner().invoke(cli, ["complete", str(stub), "--private-root",
                                     str(tmp_path / "private"), "--agent", "review"])
    assert result.exit_code == 1
    assert "Invalid pending completion marker" in result.output
