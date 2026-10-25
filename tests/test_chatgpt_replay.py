"""Actual filesystem effects and interruption replay; synthetic exports only."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import frontmatter
import pytest

from sbo_ingestion.ingest import ingest


def tree_bytes(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }


def run(source, tmp_path, account="synthetic"):
    return ingest(
        source,
        brain_root=tmp_path / "brain",
        private_root=tmp_path / "private",
        account_scope=account,
    )


def test_identical_replay_has_no_file_effects(branched_export, tmp_path):
    first = run(branched_export, tmp_path)
    before = tree_bytes(tmp_path / "private"), tree_bytes(tmp_path / "brain")
    repeated = run(branched_export, tmp_path)
    assert repeated[0].source_unchanged
    assert repeated[0].brain_path == first[0].brain_path
    assert before == (tree_bytes(tmp_path / "private"), tree_bytes(tmp_path / "brain"))
    original = next((tmp_path / "private/_distill/chatgpt/exports").rglob("original.json"))
    assert original.read_bytes() == branched_export.read_bytes()


def test_revision_retains_graph_raw_bytes_and_curated_note(branched_export, tmp_path):
    result = run(branched_export, tmp_path)[0]
    raw_before = result.private_path.read_bytes()
    result.brain_path.write_text(result.brain_path.read_text() + "\nHuman interpretation\n")
    curated = result.brain_path.read_bytes()
    data = json.loads(branched_export.read_text())
    data[0]["mapping"]["a2"]["message"]["content"]["parts"] = ["revised answer"]
    branched_export.write_text(json.dumps(data))
    revised = run(branched_export, tmp_path)[0]
    assert revised.source_revised
    assert result.brain_path.read_bytes() == curated
    history = next(
        (tmp_path / "private/_distill/chatgpt/history").rglob(
            sha256(raw_before).hexdigest() + ".md"
        )
    )
    assert history.read_bytes() == raw_before
    assert frontmatter.load(revised.private_path)["refresh_pending"] is True
    assert len(list((tmp_path / "private/_distill/chatgpt/sources").rglob("*.json"))) == 2
    assert len(list((tmp_path / "private/_distill/chatgpt/exports").rglob("original.json"))) == 2


def test_same_provider_id_in_two_accounts_stays_separate(branched_export, tmp_path):
    first = run(branched_export, tmp_path, "account-a")[0]
    second = run(branched_export, tmp_path, "account-b")[0]
    assert first.brain_path != second.brain_path
    assert first.private_path != second.private_path
    assert frontmatter.load(first.private_path)["account_scope"] == "account-a"
    assert frontmatter.load(second.private_path)["account_scope"] == "account-b"


@pytest.mark.parametrize("phase", ["pair", "audit", "index", "manifest"])
def test_ten_conversation_shards_resume_after_interruption(branched_export, tmp_path, phase):
    base = json.loads(branched_export.read_text())[0]
    conversations = []
    for n in range(10):
        obj = deepcopy(base)
        obj["id"] = f"synthetic-{n}"
        conversations.append(obj)
    source = tmp_path / "synthetic.zip"
    with ZipFile(source, "w") as z:
        z.writestr("conversations-000.json", json.dumps(conversations[:5]))
        z.writestr("conversations-001.json", json.dumps(conversations[5:]))
    child = r"""
import os, sys
import sbo_ingestion.ingest as intake
from pathlib import Path
source, root, phase = sys.argv[1:]
counts = [0]
def hook(original):
    def interrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        counts[0] += 1
        if phase in ('index', 'manifest') or counts[0] == 4:
            os._exit(23)
        return result
    return interrupted
if phase == 'pair':
    intake.write_pair = hook(intake.write_pair)
elif phase == 'audit':
    intake.audit.record_ingest = hook(intake.audit.record_ingest)
elif phase == 'index':
    intake.write_index = hook(intake.write_index)
else:
    intake.chatgpt_archive.write_manifest = hook(intake.chatgpt_archive.write_manifest)
intake.ingest(Path(source), brain_root=Path(root)/'brain',
              private_root=Path(root)/'private', account_scope='synthetic')
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    interrupted = subprocess.run(
        [sys.executable, "-c", child, str(source), str(tmp_path), phase],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert interrupted.returncode == 23, interrupted.stderr
    resumed = run(source, tmp_path)
    assert len(resumed) == 10
    assert len({r.private_path for r in resumed}) == 10
    events = [
        json.loads(line)
        for line in (tmp_path / "private/_distill/audit.jsonl").read_text().splitlines()
    ]
    assert len(events) == 10
    assert len({e["completion_id"] for e in events}) == 10
    assert all(frontmatter.load(r.brain_path)["status"] == "needs-summary" for r in resumed)
    assert all("alternate answer" not in r.private_path.read_text() for r in resumed)
    before = tree_bytes(tmp_path / "private"), tree_bytes(tmp_path / "brain")
    run(source, tmp_path)
    assert before == (tree_bytes(tmp_path / "private"), tree_bytes(tmp_path / "brain"))
    manifest = json.loads(
        next((tmp_path / "private/_distill/chatgpt/imports").rglob("*.json")).read_text()
    )
    assert len(manifest["records"]) == 10
    assert manifest["account_denominator"] is None
    assert manifest["exporter_window"] is None
    assert manifest["unknown"]


def test_legacy_raw_is_preserved_before_graph_upgrade(branched_export, tmp_path):
    result = run(branched_export, tmp_path, None)[0]
    raw = frontmatter.load(result.private_path)
    for key in ["source_schema", "source_graph", "source_content_sha256"]:
        del raw[key]
    raw.content = "Historical flattened transcript; do not lose it"
    result.private_path.write_text(frontmatter.dumps(raw))
    old = result.private_path.read_bytes()
    run(branched_export, tmp_path, None)
    assert (
        next(
            (tmp_path / "private/_distill/chatgpt/history").rglob(sha256(old).hexdigest() + ".md")
        ).read_bytes()
        == old
    )


def test_private_archive_symlink_is_rejected(branched_export, tmp_path):
    (tmp_path / "private/_distill").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (tmp_path / "private/_distill/chatgpt").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("host cannot create directory symlinks")
    with pytest.raises(ValueError, match="escapes|symlinks"):
        run(branched_export, tmp_path)
    assert list(outside.iterdir()) == []


def test_corrupt_completed_manifest_is_rejected(branched_export, tmp_path):
    run(branched_export, tmp_path)
    receipt = next((tmp_path / "private/_distill/chatgpt/imports").rglob("*.json"))
    payload = json.loads(receipt.read_text())
    payload["counts"]["captured"] = 9999
    receipt.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="receipt counts"):
        run(branched_export, tmp_path)


def test_old_revision_cannot_silently_replace_newer_source(branched_export, tmp_path):
    original = branched_export.read_bytes()
    result = run(branched_export, tmp_path)[0]
    data = json.loads(original)
    data[0]["title"] = "Revision B"
    branched_export.write_text(json.dumps(data))
    run(branched_export, tmp_path)
    latest = result.private_path.read_bytes()
    branched_export.write_bytes(original)
    with pytest.raises(ValueError, match="requires review before reactivation"):
        run(branched_export, tmp_path)
    assert result.private_path.read_bytes() == latest


def test_revised_source_retries_after_graph_staging(branched_export, tmp_path, monkeypatch):
    import sbo_ingestion.dual_write as dual_write

    result = run(branched_export, tmp_path)[0]
    old = result.private_path.read_bytes()
    data = json.loads(branched_export.read_text())
    data[0]["title"] = "Pending revision B"
    branched_export.write_text(json.dumps(data))
    original_write = dual_write._atomic_write_text

    def interrupt(path, *args, **kwargs):
        if path == result.private_path:
            raise OSError("synthetic revision staging interruption")
        return original_write(path, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(dual_write, "_atomic_write_text", interrupt)
        with pytest.raises(OSError, match="revision staging"):
            run(branched_export, tmp_path)
    assert result.private_path.read_bytes() == old
    resumed = run(branched_export, tmp_path)[0]
    assert "Pending revision B" in resumed.private_path.read_text()
    assert resumed.source_revised


def test_renamed_identical_json_is_noop(branched_export, tmp_path):
    run(branched_export, tmp_path)
    before = tree_bytes(tmp_path / "private"), tree_bytes(tmp_path / "brain")
    renamed = tmp_path / "renamed-export.json"
    renamed.write_bytes(branched_export.read_bytes())
    result = run(renamed, tmp_path)[0]
    assert result.source_unchanged
    assert before == (tree_bytes(tmp_path / "private"), tree_bytes(tmp_path / "brain"))


def test_saved_original_rebuilds_deleted_derived_view(branched_export, tmp_path):
    first = run(branched_export, tmp_path)[0]
    note_bytes = first.brain_path.read_bytes()
    selected = frontmatter.load(first.private_path).content
    first.private_path.unlink()
    saved = next((tmp_path / "private/_distill/chatgpt/exports").rglob("original.json"))
    restored = run(saved, tmp_path)[0]
    assert frontmatter.load(restored.private_path).content == selected
    assert restored.brain_path.read_bytes() == note_bytes
    envelope = json.loads(
        (tmp_path / "private" / frontmatter.load(restored.private_path)["source_graph"]).read_text()
    )
    assert envelope["original"]["mapping"]["a1"]["message"]["content"]["parts"] == [
        "alternate answer"
    ]


@pytest.mark.parametrize(
    "field,value",
    [("author", "assistant"), ("content", 42), ("id", []), ("content", {"parts": "bad"})],
)
def test_malformed_message_fails_with_bounded_error(branched_export, tmp_path, field, value):
    obj = json.loads(branched_export.read_text())
    obj[0]["mapping"]["a2"]["message"][field] = value
    branched_export.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="Invalid ChatGPT"):
        run(branched_export, tmp_path)
    assert (
        next((tmp_path / "private/_distill/chatgpt/exports").rglob("original.json")).read_bytes()
        == branched_export.read_bytes()
    )
