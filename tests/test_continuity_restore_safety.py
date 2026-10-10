"""Untrusted portable backups must preserve trust and interrupted local work."""
import json
from hashlib import sha256

import pytest

from sbo_ingestion import continuity as c


def backup_fixture(tmp_path, relative="store/events.jsonl"):
    backup = tmp_path / "backup"
    (backup / "store").mkdir(parents=True)
    data = b"restored fixture\n"
    (backup / "store" / "events.jsonl").write_bytes(data)
    (backup / "trust-policy.json").write_bytes(data)
    (backup / c.BACKUP_MANIFEST).write_text(json.dumps({
        "schemaVersion": c.BACKUP_SCHEMA, "complete": True,
        "files": {relative: {"sha256": sha256(data).hexdigest(), "bytes": len(data)}},
    }))
    paths = c.Paths(tmp_path / "home")
    paths.store.mkdir(parents=True)
    (paths.store / "events.jsonl").write_bytes(b"original fixture\n")
    paths.policy.write_bytes(b"active fixture policy\n")
    return paths, backup


@pytest.mark.parametrize("relative", [
    "store/..\\trust-policy.json", "store/events.jsonl:stream",
    "store/C:events.jsonl", "store/.import.lock", "store/.import.lock.reclaim",
    "policy/unexpected.json",
])
def test_restore_refuses_unsafe_portable_names_before_changes(tmp_path, relative):
    paths, backup = backup_fixture(tmp_path, relative)
    with pytest.raises(c.ContinuityError, match="unexpected file"):
        c.restore(paths, backup, replace=True)
    assert paths.policy.read_bytes() == b"active fixture policy\n"
    assert (paths.store / "events.jsonl").read_bytes() == b"original fixture\n"


def test_restore_avoids_interrupted_staging_collision(tmp_path, monkeypatch):
    paths, backup = backup_fixture(tmp_path)
    monkeypatch.setattr(c, "_stamp", lambda: "fixed-stamp")
    interrupted = paths.home / ".store.restoring-fixed-stamp"
    interrupted.mkdir()
    (interrupted / "partial").write_bytes(b"previous interrupted work")
    result = c.restore(paths, backup, replace=True)
    assert (paths.store / "events.jsonl").read_bytes() == b"restored fixture\n"
    assert (result["movedAside"] / "events.jsonl").read_bytes() == b"original fixture\n"
    assert (interrupted / "partial").read_bytes() == b"previous interrupted work"


def test_staging_allocation_failure_preserves_active_store(tmp_path, monkeypatch):
    paths, backup = backup_fixture(tmp_path)

    def denied(*args, **kwargs):
        raise PermissionError("fixture allocation failure")

    monkeypatch.setattr(c.tempfile, "mkdtemp", denied)
    with pytest.raises(PermissionError):
        c.restore(paths, backup, replace=True)
    assert (paths.store / "events.jsonl").read_bytes() == b"original fixture\n"


def test_copy_failure_rolls_back_original_store(tmp_path, monkeypatch):
    paths, backup = backup_fixture(tmp_path)

    def denied(*args, **kwargs):
        raise OSError("fixture copy failure")

    monkeypatch.setattr(c.shutil, "copyfile", denied)
    with pytest.raises(OSError, match="copy failure"):
        c.restore(paths, backup, replace=True)
    assert (paths.store / "events.jsonl").read_bytes() == b"original fixture\n"
    assert paths.policy.read_bytes() == b"active fixture policy\n"


@pytest.mark.parametrize("manifest", [[], None, {"schemaVersion": c.BACKUP_SCHEMA,
    "complete": True, "files": {"store/events.jsonl": None}}])
def test_malformed_manifest_is_an_actionable_refusal(tmp_path, manifest):
    paths, backup = backup_fixture(tmp_path)
    (backup / c.BACKUP_MANIFEST).write_text(json.dumps(manifest))
    with pytest.raises(c.ContinuityError):
        c.restore(paths, backup, replace=True)
    assert (paths.store / "events.jsonl").read_bytes() == b"original fixture\n"
