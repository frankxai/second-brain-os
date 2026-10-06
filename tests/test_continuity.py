"""Continuity setup, backup and restore.

The fixture store carries the awkward bytes a real store can hold: CRLF, non-ASCII
text, a torn final line from a crashed writer and an empty file. Restore must
reproduce every one of them exactly.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest
from click.testing import CliRunner

from sbo_ingestion import continuity as c

REVISION = "12d794a389959a2360bd4c920689510f0949f02b"
ORIGIN = "https://github.com/example/founder-app.git"
BRANCH = "agent/codex/onboarding"
HEAD = "a" * 40


class FakeTerminal:
    def __init__(self, answers: list[str], interactive: bool = True):
        self.answers = list(answers)
        self.interactive = interactive
        self.questions: list[str] = []

    def ask(self, question: str) -> str:
        self.questions.append(question)
        return self.answers.pop(0)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    home = tmp_path / "machine" / ".starlight" / "continuity"
    brain = tmp_path / "second-brain" / "brain"
    private = tmp_path / "second-brain" / "private"
    brain.mkdir(parents=True)
    private.mkdir(parents=True)
    monkeypatch.setenv("SIS_CONTINUITY_HOME", str(home))
    monkeypatch.setenv("SBO_BRAIN_VAULT_ROOT", str(brain))
    monkeypatch.setenv("SBO_PRIVATE_VAULT_ROOT", str(private))
    monkeypatch.delenv("STARLIGHT_CONTINUITY_CLI", raising=False)
    return {"home": home, "brain": brain, "private": private, "tmp": tmp_path}


def make_goal_store(path: Path, rows: list[tuple]) -> Path:
    db = sqlite3.connect(path)
    db.execute(
        "create table thread_goals (thread_id text, goal_id text, objective text, status text, updated_at_ms integer)"
    )
    db.executemany("insert into thread_goals values (?, ?, ?, ?, ?)", rows)
    db.commit()
    db.close()
    return path


def goal_rows() -> list[tuple]:
    return [
        ("thread-1", "g-onboarding", "Ship the onboarding flow", "paused", 1_790_000_000_000),
        ("thread-2", "g-pricing", "Draft the pricing page", "usage_limited", 1_790_000_100_000),
        ("thread-3", "g-done", "Old finished goal", "complete", 1_780_000_000_000),
        ("thread-4", "g-empty", "   ", "active", 1_790_000_200_000),
        ("thread-5", "g-odd", "Unknown status", "archived", 1_790_000_300_000),
    ]


def _digest(text: str) -> str:
    return sha256(text.encode()).hexdigest()


def write_bundle(directory: Path, *, tamper: bool = False) -> Path:
    """Mirror of SIS test/_lib/continuity-fixture.ts writeBundle, with a native goal."""
    directory.mkdir(parents=True)
    observed = "2026-10-04T12:00:00.000Z"
    request = _digest("Ship the onboarding flow")
    event = {
        "schemaVersion": "1.0",
        "eventId": "capture:" + _digest("onboarding"),
        "workId": "work:onboarding",
        "correlationId": "work:onboarding",
        "projectId": "project:founder-app",
        "kind": "intent.captured",
        "source": {"system": "codex", "sourceId": "thread-1", "uri": "session:thread-1"},
        "actorId": "actor:founder",
        "occurredAt": observed,
        "observedAt": observed,
        "evidenceRefs": ["session:thread-1", "codex-goal:g-onboarding", f"sha256:{request}"],
        "visibility": "private",
        "retention": "operational",
        "summary": "Complete user directive captured; task admission and release proof remain external.",
        "data": {
            "harness": "codex",
            "requestDigest": request,
            "goalAuthority": "native-goal-store",
            "goalSourceRef": "codex-goal:g-onboarding",
            "sourceVerification": "collector-claimed",
            "reportedState": "paused",
            "stateVerification": "native-goal-store",
            "repositoryHead": HEAD,
            "mayAutomaticallyResume": False,
        },
    }
    observation = {
        "sessionKey": json.dumps(["codex", "thread-1"], separators=(",", ":")),
        "workId": "work:onboarding",
        "projectId": "project:founder-app",
        "reportedState": "paused",
        "stateVerification": "native-goal-store",
        "goalAuthority": "native-goal-store",
        "goalSourceRef": "codex-goal:g-onboarding",
        "requestDigest": request,
        "captureCompleteness": "complete",
        "repository": {
            "root": "C:/work/founder-app",
            "head": HEAD,
            "branch": BRANCH,
            "origin": ORIGIN,
            "dirty": True,
        },
        "mayAutomaticallyResume": False,
    }
    bundle = {
        "schemaVersion": c.BUNDLE_SCHEMA,
        "sisSourceRevision": REVISION,
        "observedAt": observed,
        "privacy": "metadata-only",
        "observations": [observation],
        "events": [event],
        "issues": [],
        "unboundSessions": [],
        "executionStarted": False,
        "admissionGranted": False,
        "completionClaimed": False,
    }
    files = {
        "events.jsonl": json.dumps(event) + "\n",
        "continuity.json": json.dumps(bundle, indent=2) + "\n",
        "recovery.txt": "No command has been executed.\n",
    }
    checksums = {}
    for name, text in files.items():
        (directory / name).write_bytes(text.encode())
        checksums[name] = _digest(text)
    if tamper:
        (directory / "recovery.txt").write_bytes(b"Run rm -rf now.\n")
    manifest = {
        "schemaVersion": c.MANIFEST_SCHEMA,
        "checksums": checksums,
        "eventCount": 1,
        "issueCount": 0,
        "complete": True,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return directory


STORE_FIXTURE = {
    "events.jsonl": b'{"eventId":"e1","summary":"caf\xc3\xa9 \xe2\x80\x94 r\xc3\xa9sum\xc3\xa9"}\r\n{"eventId":"e2"}\n',
    "observations.jsonl": b'{"workId":"work:onboarding"}\n{"workId":"work:onb',  # torn final line
    "quarantine.jsonl": b"",
    "imports.jsonl": b'{"digest":"' + b"f" * 64 + b'"}\n',
}
POLICY_BYTES = b'{\n  "schemaVersion": "starlight.continuity-trust.v1"\n}\n'


def seed_store(home: Path) -> dict[str, bytes]:
    store = home / "store"
    store.mkdir(parents=True)
    for name, data in STORE_FIXTURE.items():
        (store / name).write_bytes(data)
    (home / "trust-policy.json").write_bytes(POLICY_BYTES)
    return {
        **{f"store/{n}": d for n, d in STORE_FIXTURE.items()},
        "trust-policy.json": POLICY_BYTES,
    }


def tree_bytes(home: Path) -> dict[str, bytes]:
    out = {f"store/{p.name}": p.read_bytes() for p in sorted((home / "store").iterdir())}
    if (home / "trust-policy.json").exists():
        out["trust-policy.json"] = (home / "trust-policy.json").read_bytes()
    return out


def dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


# ---------------------------------------------------------------- restore is byte-identical


def test_restore_is_byte_identical_on_a_fresh_machine(env):
    original = seed_store(env["home"])
    backup_dir = c.backup(c.Paths.from_env())
    assert c._is_within(env["private"], backup_dir)

    shutil.rmtree(env["home"])  # the machine is gone
    result = c.restore(c.Paths.from_env(), backup_dir)

    assert tree_bytes(env["home"]) == original
    assert result == {"files": 4, "movedAside": None, "policy": "restored"}
    assert not any(p.name.startswith(".store.restoring") for p in env["home"].iterdir())


def test_backup_never_copies_locks_and_refuses_while_one_exists(env):
    seed_store(env["home"])
    lock = env["home"] / "store" / c.LOCK_NAME
    lock.write_text(json.dumps({"pid": os.getpid(), "host": socket.gethostname(), "token": "t"}))
    with pytest.raises(c.ContinuityError, match="import is running"):
        c.backup(c.Paths.from_env())
    assert not (env["private"] / "_continuity-backups").exists() or not any(
        (env["private"] / "_continuity-backups").iterdir()
    )
    lock.unlink()
    backup_dir = c.backup(c.Paths.from_env())
    assert not (backup_dir / "store" / c.LOCK_NAME).exists()


def test_backup_refuses_the_brain_vault(env):
    seed_store(env["home"])
    with pytest.raises(c.ContinuityError, match="readable over MCP"):
        c.backup(c.Paths.from_env(), env["brain"] / "backups" / "one")
    assert not (env["brain"] / "backups").exists()


def test_backup_needs_a_new_folder(env):
    seed_store(env["home"])
    target = env["private"] / "kept"
    target.mkdir()
    with pytest.raises(c.ContinuityError, match="already exists"):
        c.backup(c.Paths.from_env(), target)
    assert target.exists()


def test_restore_refuses_a_tampered_backup(env):
    seed_store(env["home"])
    backup_dir = c.backup(c.Paths.from_env())
    (backup_dir / "store" / "events.jsonl").write_bytes(b'{"eventId":"forged"}\n')
    shutil.rmtree(env["home"])
    with pytest.raises(c.ContinuityError, match="checksum"):
        c.restore(c.Paths.from_env(), backup_dir)
    assert not (env["home"] / "store").exists()


def test_restore_refuses_an_unfinished_backup(env):
    seed_store(env["home"])
    backup_dir = c.backup(c.Paths.from_env())
    (backup_dir / c.BACKUP_MANIFEST).unlink()
    with pytest.raises(c.ContinuityError, match="not a finished backup"):
        c.restore(c.Paths.from_env(), backup_dir, replace=True)


def test_restore_rejects_paths_outside_the_backup(env):
    seed_store(env["home"])
    backup_dir = c.backup(c.Paths.from_env())
    manifest = json.loads((backup_dir / c.BACKUP_MANIFEST).read_text())
    manifest["files"]["store/../../escape"] = {"sha256": "0", "bytes": 0}
    (backup_dir / c.BACKUP_MANIFEST).write_text(json.dumps(manifest))
    with pytest.raises(c.ContinuityError, match="unexpected file"):
        c.restore(c.Paths.from_env(), backup_dir, replace=True)


def test_restore_moves_an_existing_store_aside_and_keeps_a_different_policy(env):
    original = seed_store(env["home"])
    backup_dir = c.backup(c.Paths.from_env())
    (env["home"] / "store" / "events.jsonl").write_bytes(b'{"eventId":"newer"}\n')
    newer_policy = b'{"schemaVersion":"starlight.continuity-trust.v1","note":"edited"}\n'
    (env["home"] / "trust-policy.json").write_bytes(newer_policy)

    with pytest.raises(c.ContinuityError, match="--replace"):
        c.restore(c.Paths.from_env(), backup_dir)
    result = c.restore(c.Paths.from_env(), backup_dir, replace=True)

    restored = tree_bytes(env["home"])
    assert {k: v for k, v in restored.items() if k.startswith("store/")} == {
        k: v for k, v in original.items() if k.startswith("store/")
    }
    assert restored["trust-policy.json"] == newer_policy
    assert (env["home"] / "trust-policy.restored.json").read_bytes() == POLICY_BYTES
    assert (result["movedAside"] / "events.jsonl").read_bytes() == b'{"eventId":"newer"}\n'


def test_restore_refuses_a_locked_store(env):
    seed_store(env["home"])
    backup_dir = c.backup(c.Paths.from_env())
    (env["home"] / "store" / c.MUTEX_NAME).write_text("not json")
    with pytest.raises(c.ContinuityError, match="locked"):
        c.restore(c.Paths.from_env(), backup_dir, replace=True)


# ---------------------------------------------------------------- crash-left locks


def test_lock_states_name_the_right_next_step(env):
    store = env["home"] / "store"
    store.mkdir(parents=True)
    lock = store / c.LOCK_NAME
    host = socket.gethostname()

    lock.write_text(json.dumps({"pid": os.getpid(), "host": host, "token": "t"}))
    assert c.inspect_lock(lock).kind == "running"
    lock.write_text(json.dumps({"pid": dead_pid(), "host": host, "token": "t"}))
    assert c.inspect_lock(lock).kind == "crashed"
    lock.write_text(json.dumps({"pid": 1, "host": "laptop-elsewhere", "token": "t"}))
    assert c.inspect_lock(lock).kind == "other-host"
    lock.write_text("{torn")
    assert c.inspect_lock(lock).kind == "unreadable"


def test_unlock_clears_a_crashed_reclaimer_after_confirmation(env):
    store = env["home"] / "store"
    store.mkdir(parents=True)
    owner = json.dumps({"pid": dead_pid(), "host": socket.gethostname(), "token": "t"})
    (store / c.LOCK_NAME).write_text(owner)
    (store / c.MUTEX_NAME).write_text(owner)
    (store / "events.jsonl").write_bytes(b"{}\n")

    with pytest.raises(c.ContinuityError, match="interactive"):
        c.unlock(c.Paths.from_env(), FakeTerminal([], interactive=False))
    with pytest.raises(c.ContinuityError, match="Not confirmed"):
        c.unlock(c.Paths.from_env(), FakeTerminal(["yes"]))
    assert (store / c.MUTEX_NAME).exists()

    removed = c.unlock(c.Paths.from_env(), FakeTerminal(["unlock"]))
    assert [p.name for p in removed] == [c.MUTEX_NAME, c.LOCK_NAME]
    assert (store / "events.jsonl").read_bytes() == b"{}\n"


def test_unlock_never_removes_a_running_import(env):
    store = env["home"] / "store"
    store.mkdir(parents=True)
    (store / c.LOCK_NAME).write_text(
        json.dumps({"pid": os.getpid(), "host": socket.gethostname(), "token": "t"})
    )
    with pytest.raises(c.ContinuityError, match="running"):
        c.unlock(c.Paths.from_env(), FakeTerminal(["unlock"]))
    assert (store / c.LOCK_NAME).exists()


# ---------------------------------------------------------------- draft and approve


def test_draft_uses_only_ids_from_the_users_records(env):
    goals = c.read_native_goals(make_goal_store(env["tmp"] / "goals.sqlite", goal_rows()))
    assert [g.goal_id for g in goals] == ["g-pricing", "g-onboarding", "g-done"]

    draft = c.draft_policy(goals, None, created_at="2026-10-06T00:00:00+00:00")
    assert [w["workId"] for w in draft["works"]] == [
        "codex-goal:g-pricing",
        "codex-goal:g-onboarding",
    ]
    assert all(w["projectId"] == "" and w["ownerActorId"] == "" for w in draft["works"])
    assert (
        draft["supportedSourceRevisions"] == []
        and draft["operators"] == []
        and draft["collectors"] == []
    )
    assert "Ship the onboarding flow" not in json.dumps(
        draft
    )  # objective text stays out of the file
    assert c.policy_gaps({k: v for k, v in draft.items() if k != "draft"})


def test_draft_fills_from_a_verified_bundle(env):
    goals = c.read_native_goals(make_goal_store(env["tmp"] / "goals.sqlite", goal_rows()))
    bundle = c.read_verified_bundle(write_bundle(env["tmp"] / "bundle"))
    draft = c.draft_policy(goals, bundle, created_at="2026-10-06T00:00:00+00:00")

    onboarding = next(w for w in draft["works"] if w["workId"] == "work:onboarding")
    assert onboarding == {
        "workId": "work:onboarding",
        "projectId": "project:founder-app",
        "ownerActorId": "actor:founder",
        "checkout": {"origin": ORIGIN, "branch": BRANCH},
    }
    assert draft["supportedSourceRevisions"] == [REVISION]
    assert draft["collectors"] == [{"harness": "codex", "sourceRefPrefix": "session:"}]
    assert draft["operators"] == ["actor:founder"]
    assert draft["draft"]["needsOwnerInput"] == ["works[0].projectId", "works[0].ownerActorId"]


def test_tampered_bundle_is_refused(env):
    with pytest.raises(c.ContinuityError, match="checksum"):
        c.read_verified_bundle(write_bundle(env["tmp"] / "bundle", tamper=True))


def test_unreadable_goal_store_is_refused(env):
    bad = env["tmp"] / "goals.sqlite"
    bad.write_bytes(b"not a database" * 100)
    with pytest.raises(c.ContinuityError, match="unreadable"):
        c.read_native_goals(bad)
    with pytest.raises(c.ContinuityError, match="No native goal store"):
        c.read_native_goals(env["tmp"] / "missing.sqlite")


def test_approve_needs_the_owner_and_a_complete_draft(env):
    paths = c.Paths.from_env()
    goals = c.read_native_goals(make_goal_store(env["tmp"] / "goals.sqlite", goal_rows()))
    draft = c.draft_policy(goals, None, created_at="2026-10-06T00:00:00+00:00")
    c._write_private(paths.draft, json.dumps(draft), exclusive=False)

    with pytest.raises(c.ContinuityError, match="interactive terminal"):
        c.approve_draft(paths, FakeTerminal([], interactive=False))
    with pytest.raises(c.ContinuityError, match="missing supportedSourceRevisions"):
        c.approve_draft(paths, FakeTerminal([]))
    assert not paths.policy.exists()


# ---------------------------------------------------------------- the whole walkthrough


def test_fresh_machine_walkthrough(env, monkeypatch):
    """Setup drafts, the owner approves, a crash leaves a lock, backup and restore recover."""
    paths = c.Paths.from_env()
    goals_db = make_goal_store(env["tmp"] / "goals.sqlite", goal_rows()[:1])
    bundle = write_bundle(env["tmp"] / "bundle")

    runner = CliRunner()
    result = runner.invoke(c.cli, ["setup", "--goals", str(goals_db), "--bundle", str(bundle)])
    assert result.exit_code == 0, result.output
    assert "not active" in result.output and "Ship the onboarding flow" in result.output
    assert not paths.policy.exists()
    note = env["brain"] / "_moc" / c.NOTE_NAME
    assert "http://localhost:3000/continuity" in note.read_text()

    terminal = FakeTerminal(["y", "approve"])
    policy = c.approve_draft(paths, terminal)
    assert "draft" not in policy and c.policy_gaps(policy) == []
    assert json.loads(paths.policy.read_text()) == policy
    assert ORIGIN in terminal.questions[0]

    # SIS writes the store on import; stand in for it, then crash mid-reclaim.
    seed_store_files = {k: v for k, v in STORE_FIXTURE.items()}
    paths.store.mkdir(parents=True)
    for name, data in seed_store_files.items():
        (paths.store / name).write_bytes(data)
    owner = json.dumps({"pid": dead_pid(), "host": socket.gethostname(), "token": "t"})
    (paths.store / c.LOCK_NAME).write_text(owner)
    (paths.store / c.MUTEX_NAME).write_text(owner)

    doctor = runner.invoke(c.cli, ["doctor"])
    assert doctor.exit_code == 1 and "crashed lock reclaim" in doctor.output
    assert runner.invoke(c.cli, ["backup"]).exit_code == 1
    c.unlock(paths, FakeTerminal(["unlock"]))

    before = tree_bytes(env["home"])
    out = runner.invoke(c.cli, ["backup"])
    assert out.exit_code == 0, out.output
    backup_dir = Path(out.output.strip().removeprefix("Backup written to "))

    shutil.rmtree(env["home"])
    out = runner.invoke(c.cli, ["restore", "--from", str(backup_dir)])
    assert out.exit_code == 0, out.output
    assert tree_bytes(env["home"]) == before
    assert runner.invoke(c.cli, ["doctor"]).exit_code == 0


# ---------------------------------------------------------------- against real SIS (opt-in)


@pytest.mark.skipif(
    not os.environ.get("SBO_SIS_SRC"), reason="set SBO_SIS_SRC to a SIS src/ folder to run"
)
def test_real_sis_reads_the_restored_store_identically(env):
    """Import a bundle with SIS itself, back up, wipe, restore, and compare SIS status."""
    cli_ts = Path(os.environ["SBO_SIS_SRC"]) / "continuity-cli.ts"
    npx = shutil.which("npx")
    assert npx and cli_ts.is_file()

    def sis(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [npx, "--yes", "tsx", str(cli_ts), *args],
            capture_output=True,
            text=True,
            env={**os.environ, "SIS_CONTINUITY_HOME": str(env["home"])},
            timeout=180,
        )

    paths = c.Paths.from_env()
    goals = c.read_native_goals(make_goal_store(env["tmp"] / "goals.sqlite", goal_rows()[:1]))
    bundle_dir = write_bundle(env["tmp"] / "bundle")
    draft = c.draft_policy(
        goals, c.read_verified_bundle(bundle_dir), created_at="2026-10-06T00:00:00+00:00"
    )
    c._write_private(paths.draft, json.dumps(draft), exclusive=False)
    c.approve_draft(paths, FakeTerminal(["y", "approve"]))

    imported = sis("import", str(bundle_dir.resolve()))
    assert imported.returncode == 0, imported.stderr
    assert json.loads(imported.stdout)["status"] != "refused"
    before = sis("status", "--json")
    assert before.returncode == 0, before.stderr
    work = json.loads(before.stdout)["works"]
    assert [w["workId"] for w in work] == ["work:onboarding"] and work[0]["quarantined"] == 0

    files_before = tree_bytes(env["home"])
    backup_dir = c.backup(paths)
    shutil.rmtree(env["home"])
    c.restore(paths, backup_dir)

    assert tree_bytes(env["home"]) == files_before
    after = sis("status", "--json")
    assert after.returncode == 0, after.stderr
    assert json.loads(after.stdout) == json.loads(before.stdout)
    replay = sis("import", str(bundle_dir.resolve()))
    assert replay.returncode == 0 and tree_bytes(env["home"]) == files_before


def test_vault_template_note_matches_what_setup_writes():
    template = Path(__file__).parent.parent / "templates" / "brain-vault-skeleton" / "_moc" / c.NOTE_NAME
    assert template.read_text("utf-8") == c.note_text(c.DEFAULT_CANVAS_URL + "/continuity")
