"""Unit tests for sbo_ingestion.audit."""

from __future__ import annotations

import json
from pathlib import Path

from sbo_ingestion.audit import (
    _audit_path,
    _relpath,
    append,
    record_distill,
    record_import_receipt,
    record_ingest,
)

def test_audit_path(tmp_path: Path) -> None:
    assert _audit_path(tmp_path) == tmp_path / "_distill" / "audit.jsonl"

def test_relpath(tmp_path: Path) -> None:
    base = tmp_path / "b"
    t = base / "c.txt"
    assert _relpath(t, base) == "c.txt"
    # When t is not relative to 'other', it falls back to absolute path
    other = tmp_path / "other"
    assert _relpath(t, other) == str(t).replace("\\", "/")

def test_append_creates_file(tmp_path: Path) -> None:
    path = append(tmp_path, {"test": "value"})
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["test"] == "value"

def test_append_with_completion_id_deduplicates(tmp_path: Path) -> None:
    entry = {"test": "v", "completion_id": "c1"}
    append(tmp_path, entry)
    path = _audit_path(tmp_path)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    append(tmp_path, entry)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    append(tmp_path, {"test": "v2", "completion_id": "c2"})
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2

def test_record_ingest(tmp_path: Path) -> None:
    path = record_ingest(
        tmp_path, conversation_id="c1", mode="api", fmt="chatgpt",
        raw_path=tmp_path / "raw.txt", brain_path=tmp_path / "brain.md",
        private_root_for_rel=tmp_path, brain_root_for_rel=tmp_path,
        brain_preserved=True, source="src",
    )
    content = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    assert content["action"] == "ingest"
    assert content["conversation_id"] == "c1"
    assert content["brain_preserved"] is True
    assert content["raw_path"] == "raw.txt"

def test_record_import_receipt(tmp_path: Path) -> None:
    path = record_import_receipt(
        tmp_path, source_name="export.zip", source_size=100,
        fmt="claude.ai", selected_members=("m1",),
        conversation_count=2, brain_created=1, brain_preserved=1,
    )
    assert path.exists()
    content = json.loads(path.read_text(encoding="utf-8"))
    assert content["schema"] == "sbo-import-receipt.v1"
    assert content["source_name"] == "export.zip"

def test_record_distill(tmp_path: Path) -> None:
    path = record_distill(
        tmp_path, conversation_id="c1", agent="agent1",
        model="model1", summary_chars=100, completion_id="comp1",
    )
    content = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    assert content["action"] == "distill"
    assert content["agent"] == "agent1"
    assert content["summary_chars"] == 100
