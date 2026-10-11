"""Tests for idea capture packet validation, ingestion, and packet distillation."""

import json
from hashlib import sha256

import frontmatter
import pytest

from sbo_ingestion.distill_packet import acknowledge_packet, packet, plan_batch
from sbo_ingestion.handlers.idea_capture import compute_semantic_identity, read_and_validate_packet
from sbo_ingestion.ingest import ingest


def make_packet(
    version=1,
    rawText="Autonomous test idea text.",
    tags="test,idea",
    source="mobile-app",
    sourceRef="ref-123",
):
    return {
        "version": version,
        "rawText": rawText,
        "tags": tags,
        "source": source,
        "sourceRef": sourceRef,
    }


def test_valid_packet_validation_and_identity(tmp_path):
    p = tmp_path / "valid.json"
    obj = make_packet()
    p.write_bytes(json.dumps(obj).encode("utf-8"))
    validated, _ = read_and_validate_packet(p)
    assert validated["version"] == 1 and validated["rawText"] == "Autonomous test idea text."
    assert len(compute_semantic_identity(validated)) == 64


def test_packet_validation_failures(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        read_and_validate_packet(tmp_path / "missing.json")

    real = tmp_path / "real.json"
    real.write_text(json.dumps(make_packet()))
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symlink"):
        read_and_validate_packet(link)

    for val_dict, match in [
        (make_packet(version=True), "version"),
        (make_packet(rawText="   "), "rawText"),
    ]:
        bad_p = tmp_path / "bad.json"
        bad_p.write_text(json.dumps(val_dict))
        with pytest.raises(ValueError, match=match):
            read_and_validate_packet(bad_p)

    dup_p = tmp_path / "dup.json"
    dup_p.write_bytes(
        b'{"version": 1, "rawText": "a", "rawText": "b", '
        b'"tags": "", "source": "s", "sourceRef": null}'
    )
    with pytest.raises(ValueError, match="Duplicate keys"):
        read_and_validate_packet(dup_p)


def test_idea_capture_ingest_and_distill(tmp_path):
    brain, private = tmp_path / "brain", tmp_path / "private"
    brain.mkdir()
    private.mkdir()

    p = tmp_path / "idea.json"
    raw_bytes = json.dumps(
        make_packet(rawText="Capture idea for testing distillation packets. " * 10)
    ).encode("utf-8")
    p.write_bytes(raw_bytes)

    results = ingest(p, brain_root=brain, private_root=private, format="idea-capture")
    res = results[0]
    assert res.brain_path.exists() and res.private_path.exists()

    plan = plan_batch([{"stub": str(res.brain_path)}], private)
    assert len(plan["notes"]) == 1

    digest = sha256(raw_bytes).hexdigest()
    pkt = packet(res.brain_path, brain_root=brain, private_root=private, expected_sha256=digest)
    assert pkt["trust"] == "untrusted-data" and pkt["source_sha256"] == digest

    ack = acknowledge_packet(
        res.brain_path,
        brain_root=brain,
        private_root=private,
        digest=digest,
        token=pkt["ack_token"],
    )
    assert ack["coverage_complete"] is True


def test_forged_reference_denied(tmp_path):
    brain, private = tmp_path / "brain", tmp_path / "private"
    brain.mkdir()
    private.mkdir()

    p = tmp_path / "idea.json"
    p.write_bytes(json.dumps(make_packet()).encode("utf-8"))
    res = ingest(p, brain_root=brain, private_root=private, format="idea-capture")[0]

    post = frontmatter.load(res.brain_path)
    post["source"] = "chatgpt"
    res.brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    with pytest.raises(ValueError):
        packet(res.brain_path, brain_root=brain, private_root=private)
