"""Untrusted portable backups must preserve trust and interrupted local work."""
import json
import os
from hashlib import sha256
from pathlib import Path
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


def test_restore_keeps_store_identity_and_excludes_a_late_sis_writer(tmp_path, monkeypatch):
    paths, backup = backup_fixture(tmp_path)
    identity = paths.store.stat().st_ino
    allocate = c.tempfile.mkdtemp
    refused = []

    def writer_during_staging(*args, **kwargs):
        staging = allocate(*args, **kwargs)
        try:
            fd = os.open(paths.store / c.LOCK_NAME, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            refused.append(True)
        else:
            os.close(fd)
            raise AssertionError("SIS could acquire its writer lock during restore")
        return staging

    monkeypatch.setattr(c.tempfile, "mkdtemp", writer_during_staging)
    result = c.restore(paths, backup, replace=True)
    assert refused
    assert paths.store.stat().st_ino == identity
    assert (result["movedAside"] / "events.jsonl").read_bytes() == b"original fixture\n"
    assert not (result["movedAside"] / c.LOCK_NAME).exists()
    assert c.store_locks(paths.store) == []


def test_store_populated_during_staging_still_requires_replace(tmp_path, monkeypatch):
    paths, backup = backup_fixture(tmp_path)
    (paths.store / "events.jsonl").unlink()
    allocate = c.tempfile.mkdtemp

    def populate(*args, **kwargs):
        staging = allocate(*args, **kwargs)
        (paths.store / "events.jsonl").write_bytes(b"concurrent fixture\n")
        return staging

    monkeypatch.setattr(c.tempfile, "mkdtemp", populate)
    with pytest.raises(c.ContinuityError, match="--replace"):
        c.restore(paths, backup)
    assert (paths.store / "events.jsonl").read_bytes() == b"concurrent fixture\n"
    assert c.store_locks(paths.store) == []


def test_restore_install_failure_rolls_back_under_the_same_lock(tmp_path, monkeypatch):
    paths, backup = backup_fixture(tmp_path)
    replace = c.os.replace

    def fail_install(source, target, *args, **kwargs):
        if Path(source).parent.name.startswith(".store.restoring-"):
            assert (paths.store / c.LOCK_NAME).exists()
            assert (paths.store / c.MUTEX_NAME).exists()
            raise OSError("fixture install failure")
        return replace(source, target, *args, **kwargs)

    monkeypatch.setattr(c.os, "replace", fail_install)
    with pytest.raises(OSError, match="install failure"):
        c.restore(paths, backup, replace=True)
    assert (paths.store / "events.jsonl").read_bytes() == b"original fixture\n"
    assert c.store_locks(paths.store) == []


def test_unlock_refuses_an_interrupted_restore_transition(tmp_path, monkeypatch):
    paths, _ = backup_fixture(tmp_path)
    owner = {"pid": 1234, "host": c.socket.gethostname(), "token": "restore-fixture",
             "operation": "restore", "recovery": "store.before-restore-fixture"}
    for name in [c.LOCK_NAME, c.MUTEX_NAME]:
        (paths.store / name).write_text(json.dumps(owner))
    monkeypatch.setattr(c, "_pid_alive", lambda pid: False)
    terminal = SimpleNamespace(interactive=True, ask=lambda question: "unlock")
    with pytest.raises(c.ContinuityError, match="restore.*inspect|inspect.*restore"):
        c.unlock(paths, terminal)
    assert (paths.store / c.LOCK_NAME).exists()
    assert (paths.store / c.MUTEX_NAME).exists()


def test_failed_rollback_preserves_recovery_files_and_both_fences(tmp_path, monkeypatch):
    paths, backup = backup_fixture(tmp_path)
    replace = c.os.replace

    def fail_install_and_rollback(source, target, *args, **kwargs):
        parent = Path(source).parent.name
        if parent.startswith((".store.restoring-", "store.before-restore-")):
            raise OSError("fixture transition failure")
        return replace(source, target, *args, **kwargs)

    monkeypatch.setattr(c.os, "replace", fail_install_and_rollback)
    with pytest.raises(c.ContinuityError, match="rollback failed"):
        c.restore(paths, backup, replace=True)
    mutex = json.loads((paths.store / c.MUTEX_NAME).read_text())
    assert (Path(mutex["recovery"]) / "events.jsonl").read_bytes() == b"original fixture\n"
    assert (paths.store / c.LOCK_NAME).exists()
    assert paths.policy.read_bytes() == b"active fixture policy\n"
    assert list(paths.home.glob(".store.restoring-*/events.jsonl"))


def test_restore_cannot_remove_another_reclaimers_mutex(tmp_path):
    paths, backup = backup_fixture(tmp_path)
    mutex = paths.store / c.MUTEX_NAME
    record = json.dumps({"pid": os.getpid(), "host": c.socket.gethostname(),
                         "token": "other-reclaimer"}).encode()
    mutex.write_bytes(record)
    with pytest.raises(c.ContinuityError, match="locked"):
        c.restore(paths, backup, replace=True)
    assert mutex.read_bytes() == record
    assert (paths.store / "events.jsonl").read_bytes() == b"original fixture\n"
    assert not (paths.store / c.LOCK_NAME).exists()
