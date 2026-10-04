import json
import os
import subprocess
import sys
from pathlib import Path

import frontmatter
import pytest
from click.testing import CliRunner

from sbo_ingestion.distill import cli, complete_stub, find_stubs
from sbo_ingestion.distill_packet import packet, plan_batch, _receipt_path


@pytest.fixture
def source(tmp_path):
    brain, private = tmp_path / "brain", tmp_path / "private"
    stub = brain / "_inbox" / "chatgpt" / "one.md"
    raw = private / "chat-history" / "chatgpt" / "one.md"
    stub.parent.mkdir(parents=True)
    raw.parent.mkdir(parents=True)
    text = "A useful workflow decision. 日本語 🙂\n" * 100
    raw.write_text(text, encoding="utf-8", newline="")
    stub.write_text(frontmatter.dumps(frontmatter.Post("Summary pending.", status="needs-summary",
                   conversation_id="one", private_file="chat-history/chatgpt/one.md")), encoding="utf-8")
    return brain, private, stub, raw, text


def test_packets_preserve_all_unicode_and_require_complete_coverage(source):
    brain, private, stub, _, text = source
    first = packet(stub, brain_root=brain, private_root=private, max_bytes=257)
    assert first["source_chunk_bytes"] <= 257 and not first["coverage_complete"]
    with pytest.raises(ValueError, match="incomplete"):
        complete_stub(stub, private, agent="test", source_sha256=first["source_sha256"])
    chunks, current = [first["content"]], first
    while current["next_offset"] is not None:
        current = packet(stub, brain_root=brain, private_root=private, max_bytes=257,
                         offset=current["next_offset"], expected_sha256=first["source_sha256"])
        chunks.append(current["content"])
    assert "".join(chunks) == text and current["coverage_complete"]
    complete_stub(stub, private, agent="test", source_sha256=first["source_sha256"])
    assert frontmatter.load(stub)["distill_source_coverage"] == "complete"


def test_changed_source_cannot_resume_or_complete(source):
    brain, private, stub, raw, _ = source
    result = packet(stub, brain_root=brain, private_root=private)
    raw.write_text("Changed source", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        packet(stub, brain_root=brain, private_root=private, offset=10,
               expected_sha256=result["source_sha256"])
    with pytest.raises(ValueError, match="changed"):
        complete_stub(stub, private, agent="test", source_sha256=result["source_sha256"])


def test_packet_rejects_escape_and_utf8_middle_offset(source, tmp_path):
    brain, private, stub, raw, _ = source
    raw.write_text("🙂" * 100, encoding="utf-8", newline="")
    first = packet(stub, brain_root=brain, private_root=private, max_bytes=256)
    with pytest.raises(ValueError, match="UTF-8"):
        packet(stub, brain_root=brain, private_root=private, offset=1,
               expected_sha256=first["source_sha256"])
    post = frontmatter.load(stub)
    post["private_file"] = "chat-history/chatgpt/../../outside.md"
    stub.write_text(frontmatter.dumps(post))
    with pytest.raises(ValueError, match="reference"):
        packet(stub, brain_root=brain, private_root=private)
    with pytest.raises(ValueError, match="separate"):
        packet(stub, brain_root=tmp_path / "other", private_root=private)


def test_plan_is_metadata_only_and_budgeted(source):
    brain, private, _, raw, _ = source
    plan = plan_batch(find_stubs(brain), private, source_budget=raw.stat().st_size)
    assert len(plan["notes"]) == 1 and plan["raw_bodies_returned"] == 0
    assert "content" not in json.dumps(plan) and plan["paid_api_calls"] == 0
    assert plan_batch(find_stubs(brain), private, source_budget=256)["deferred"] == 1


def test_packet_cli_returns_parseable_bounded_source_with_provenance(source):
    brain, private, stub, _, _ = source
    result = CliRunner().invoke(cli, ["packet", str(stub), "--brain-root", str(brain),
                                     "--private-root", str(private), "--max-bytes", "256"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["trust"] == "untrusted-data" and payload["source_chunk_bytes"] <= 256
    assert payload["next_offset"] is not None


def test_oversized_coverage_journal_is_rejected_without_completion(source):
    brain, private, stub, _, _ = source
    first = packet(stub, brain_root=brain, private_root=private)
    receipt = _receipt_path(stub, private, first["source_sha256"])
    receipt.write_text(" " * (128 * 1024 + 1), encoding="utf-8")
    with pytest.raises(ValueError, match="bounded"):
        complete_stub(stub, private, agent="test", source_sha256=first["source_sha256"])
    assert frontmatter.load(stub)["status"] == "needs-summary"


def test_packet_cli_emits_utf8_even_with_windows_legacy_stdout_encoding(source):
    brain, private, stub, _, _ = source
    result = subprocess.run([sys.executable, "-m", "sbo_ingestion.distill", "packet", str(stub),
                             "--brain-root", str(brain), "--private-root", str(private),
                             "--max-bytes", "256"], capture_output=True,
                            env={**os.environ, "PYTHONIOENCODING": "cp1252"}, timeout=15)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    payload = json.loads(result.stdout.decode("utf-8"))
    assert "日本語" in payload["content"] and "🙂" in payload["content"]
