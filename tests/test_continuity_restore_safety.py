"""Untrusted portable backups must preserve trust and interrupted local work."""
import json
import os
from hashlib import sha256
from types import SimpleNamespace

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


def add_policy(backup, data=b'{"fixture":"verified policy"}\r\n'):
    folder = backup / c.POLICY_DIR
    folder.mkdir()
    (folder / "trust-policy.json").write_bytes(data)
    path = backup / c.BACKUP_MANIFEST
    manifest = json.loads(path.read_text())
    manifest["files"][f"{c.POLICY_DIR}/trust-policy.json"] = {
        "bytes": len(data), "sha256": sha256(data).hexdigest(),
    }
    path.write_text(json.dumps(manifest))
    return data


def test_policy_changed_after_verification_is_refused_before_store_mutation(tmp_path, monkeypatch):
    paths, backup = backup_fixture(tmp_path)
    add_policy(backup)
    verify = c.verify_backup

    def mutate_after_verify(source):
        result = verify(source)
        (backup / c.POLICY_DIR / "trust-policy.json").write_bytes(b"unverified fixture")
        return result

    monkeypatch.setattr(c, "verify_backup", mutate_after_verify)
    with pytest.raises(c.ContinuityError, match="checksum"):
        c.restore(paths, backup, replace=True)
    assert paths.policy.read_bytes() == b"active fixture policy\n"
    assert (paths.store / "events.jsonl").read_bytes() == b"original fixture\n"


def test_policy_appearing_during_activation_is_preserved(tmp_path, monkeypatch):
    paths, backup = backup_fixture(tmp_path)
    expected = add_policy(backup)
    paths.policy.unlink()
    copyfile, link = c.shutil.copyfile, c.os.link
    concurrent = b"concurrently activated fixture policy\n"

    def race_copy(source, target, *args, **kwargs):
        if target == paths.policy:
            paths.policy.write_bytes(concurrent)
        return copyfile(source, target, *args, **kwargs)

    def race_link(source, target, *args, **kwargs):
        if target == paths.policy:
            paths.policy.write_bytes(concurrent)
        return link(source, target, *args, **kwargs)

    monkeypatch.setattr(c.shutil, "copyfile", race_copy)
    monkeypatch.setattr(c.os, "link", race_link)
    c.restore(paths, backup, replace=True)
    assert paths.policy.read_bytes() == concurrent
    assert (paths.home / "trust-policy.restored.json").read_bytes() == expected


def test_restored_policy_preserves_exact_verified_bytes(tmp_path):
    paths, backup = backup_fixture(tmp_path)
    expected = add_policy(backup)
    paths.policy.unlink()
    c.restore(paths, backup, replace=True)
    assert paths.policy.read_bytes() == expected


@pytest.mark.skipif(os.name != "nt", reason="Windows process API")
@pytest.mark.parametrize("open_handle,last_error", [(42, 0), (0, 6)])
def test_failed_windows_process_query_cannot_authorize_lock_removal(
    tmp_path, monkeypatch, open_handle, last_error
):
    paths, _ = backup_fixture(tmp_path)
    lock = paths.store / c.LOCK_NAME
    lock.write_text(json.dumps({"pid": 1234, "host": c.socket.gethostname(), "token": "fixture"}))
    closed = []
    api = SimpleNamespace(
        OpenProcess=lambda *args: open_handle,
        GetExitCodeProcess=lambda *args: 0,
        CloseHandle=lambda handle: closed.append(handle),
    )
    monkeypatch.setattr(c.ctypes, "WinDLL", lambda *args, **kwargs: api)
    monkeypatch.setattr(c.ctypes, "get_last_error", lambda: last_error)
    terminal = SimpleNamespace(interactive=True, ask=lambda question: "unlock")
    with pytest.raises(c.ContinuityError, match="running"):
        c.unlock(paths, terminal)
    assert lock.exists()
    assert closed == ([open_handle] if open_handle else [])


@pytest.mark.skipif(os.name != "nt", reason="Windows process API")
def test_windows_query_recognizes_this_live_process_without_signalling():
    assert c._pid_alive(os.getpid()) is True


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
