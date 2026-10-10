"""Session continuity setup, backup and restore for a two-vault install.

SIS owns the continuity store and its trust rules (``src/continuity-import.ts``).
This module only prepares and protects them:

- ``setup`` checks for SIS and drafts a trust policy from the user's own native
  goal records. It never activates the draft; ``approve`` does that, and only at
  an interactive terminal.
- ``backup`` and ``restore`` copy ``~/.starlight/continuity/store`` into the
  private vault and back, byte for byte, with a checksum manifest.
- ``doctor`` and ``unlock`` explain and clear an import lock or reclaim mutex
  that a crash left behind.

Nothing here admits, resumes or runs work. The store holds private IDs, paths
and request digests, so backups go to the private vault and never the brain vault.
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import webbrowser
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import click

POLICY_SCHEMA = "starlight.continuity-trust.v1"
BUNDLE_SCHEMA = "starlight.continuity-bundle.v1"
MANIFEST_SCHEMA = "starlight.continuity-manifest.v1"
BACKUP_SCHEMA = "sbo.continuity-backup.v1"
BUNDLE_FILES = ("events.jsonl", "continuity.json", "recovery.txt")
LOCK_NAME = ".import.lock"
MUTEX_NAME = ".import.lock.reclaim"
BACKUP_MANIFEST = "continuity-backup.json"
POLICY_DIR = "policy"
# Mirrors agentic-ops lifecycle/codex-goals.js: the states a native goal may report.
NATIVE_STATES = {
    "active": "active",
    "paused": "paused",
    "blocked": "blocked",
    "usage_limited": "blocked",
    "budget_limited": "blocked",
    "complete": "complete",
}
MAX_GOAL_DB_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_FILE_BYTES = 16 * 1024 * 1024
# The collector binds at most 32 sessions per export; a longer draft is not reviewable.
MAX_DRAFT_WORKS = 32
DEFAULT_CANVAS_URL = "http://localhost:3000"
NOTE_NAME = "What was I doing.md"


class ContinuityError(Exception):
    """A refusal the user can act on. The message names the next step."""


class Terminal(Protocol):
    interactive: bool

    def ask(self, question: str) -> str: ...


class _ProcessTerminal:
    @property
    def interactive(self) -> bool:
        return sys.stdin.isatty() and sys.stdout.isatty()

    def ask(self, question: str) -> str:
        return input(question)


# ---------------------------------------------------------------- locations


@dataclass(frozen=True)
class Paths:
    home: Path

    @property
    def store(self) -> Path:
        return self.home / "store"

    @property
    def policy(self) -> Path:
        return self.home / "trust-policy.json"

    @property
    def draft(self) -> Path:
        return self.home / "trust-policy.draft.json"

    @classmethod
    def from_env(cls) -> Paths:
        # Same variable SIS reads, so both always look at one store.
        home = os.environ.get("SIS_CONTINUITY_HOME")
        return cls(Path(home) if home else Path.home() / ".starlight" / "continuity")


def default_goal_store() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return (Path(codex_home) if codex_home else Path.home() / ".codex") / "goals_1.sqlite"


def _vault(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value) if value else None


def _is_within(root: Path, target: Path) -> bool:
    root, target = root.resolve(), target.resolve()
    return target == root or root in target.parents


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_private(path: Path, text: str, *, exclusive: bool) -> None:
    _write_private_bytes(path, text.encode("utf-8"), exclusive=exclusive)


def _write_private_bytes(path: Path, data: bytes, *, exclusive: bool) -> None:
    """Write via a sibling temp file so a crash never leaves half a policy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        if exclusive:
            # os.link fails if the target exists, which makes activation race-free.
            os.link(tmp, path)
        else:
            os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ---------------------------------------------------------------- native goals


@dataclass(frozen=True)
class NativeGoal:
    goal_id: str
    thread_id: str
    objective: str
    native_status: str
    state: str
    updated_at: str


def read_native_goals(db_path: Path) -> list[NativeGoal]:
    """Read Codex's own goal records from a consistent private snapshot.

    Codex owns the database. SQLite's online backup copies it without blocking
    the WAL writer, and every query runs against the copy, which is then deleted.
    """
    if not db_path.is_file():
        raise ContinuityError(f"No native goal store at {db_path}. Pass --goals with its path.")
    if db_path.stat().st_size > MAX_GOAL_DB_BYTES:
        raise ContinuityError(
            f"The goal store at {db_path} is larger than 64 MB; refusing to read it."
        )
    with tempfile.TemporaryDirectory(prefix="sbo-goals-") as scratch:
        snapshot = Path(scratch) / "goals.sqlite"
        try:
            live = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
            try:
                copy = sqlite3.connect(snapshot)
                try:
                    live.backup(copy)
                finally:
                    copy.close()
            finally:
                live.close()
            db = sqlite3.connect(f"{snapshot.as_uri()}?mode=ro", uri=True)
            try:
                if db.execute("pragma quick_check").fetchone()[0] != "ok":
                    raise ContinuityError(
                        f"The goal store at {db_path} failed its integrity check."
                    )
                rows = db.execute(
                    "select thread_id, goal_id, objective, status, updated_at_ms from thread_goals"
                ).fetchall()
            finally:
                db.close()
        except sqlite3.Error as error:
            raise ContinuityError(
                f"The goal store at {db_path} is unreadable ({error})."
            ) from error
    goals = []
    for thread_id, goal_id, objective, status, updated_ms in rows:
        if status not in NATIVE_STATES or not isinstance(objective, str) or not objective.strip():
            continue
        if (
            not isinstance(goal_id, str)
            or not goal_id
            or not isinstance(thread_id, str)
            or not thread_id
        ):
            continue
        updated = datetime.fromtimestamp(int(updated_ms or 0) / 1000, UTC).isoformat()
        goals.append(
            NativeGoal(goal_id, thread_id, objective, status, NATIVE_STATES[status], updated)
        )
    return sorted(goals, key=lambda g: g.updated_at, reverse=True)


# ---------------------------------------------------------------- bundles


def read_verified_bundle(directory: Path) -> dict:
    """Load a collector bundle after recomputing every manifest checksum.

    The manifest proves the files are the ones the collector wrote, not who wrote
    them. SIS repeats this and much more on import.
    """
    try:
        manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
    except (OSError, ValueError) as error:
        raise ContinuityError(f"No readable manifest.json in {directory}.") from error
    checksums = manifest.get("checksums") if isinstance(manifest, dict) else None
    if (
        manifest.get("schemaVersion") != MANIFEST_SCHEMA
        or manifest.get("complete") is not True
        or not isinstance(checksums, dict)
        or sorted(checksums) != sorted(BUNDLE_FILES)
    ):
        raise ContinuityError(f"The bundle in {directory} is incomplete. Export it again.")
    for name in BUNDLE_FILES:
        path = directory / name
        if not path.is_file() or path.stat().st_size > MAX_BUNDLE_FILE_BYTES:
            raise ContinuityError(
                f"The bundle in {directory} is missing {name} or it is too large."
            )
        if _sha256_file(path) != checksums[name]:
            raise ContinuityError(
                f"{name} in {directory} does not match its checksum. Export it again."
            )
    bundle = json.loads((directory / "continuity.json").read_text("utf-8"))
    if not isinstance(bundle, dict) or bundle.get("schemaVersion") != BUNDLE_SCHEMA:
        raise ContinuityError(f"{directory} is not a {BUNDLE_SCHEMA} bundle.")
    return bundle


def _source_ref_prefix(uri: str) -> str:
    """The scheme part of a source reference, e.g. ``session:`` from ``session:abc``."""
    head, sep, _ = uri.partition(":")
    return f"{head}:" if sep and head else ""


# ---------------------------------------------------------------- draft policy


def draft_policy(goals: list[NativeGoal], bundle: dict | None, *, created_at: str) -> dict:
    """Build a draft trust policy using only identifiers found in the user's records.

    Each open native goal becomes one work. When a verified bundle carries an event
    for that goal, its work, project, actor, collector and checkout fill the entry.
    Anything no record supplies stays empty and is listed in ``draft.needsOwnerInput``;
    ``approve`` refuses until those are filled.
    """
    events_by_goal: dict[str, dict] = {}
    observations: list[dict] = []
    revision = None
    if bundle:
        revision = bundle.get("sisSourceRevision")
        observations = [o for o in bundle.get("observations", []) if isinstance(o, dict)]
        for event in bundle.get("events", []):
            data = event.get("data") if isinstance(event, dict) else None
            ref = data.get("goalSourceRef") if isinstance(data, dict) else None
            if isinstance(ref, str) and ref.startswith("codex-goal:"):
                events_by_goal.setdefault(ref, event)

    works, sources, collectors, operators, missing = [], [], [], [], []
    for goal in goals:
        if goal.state == "complete":
            continue
        if len(works) == MAX_DRAFT_WORKS:
            break
        ref = f"codex-goal:{goal.goal_id}"
        event = events_by_goal.get(ref)
        work: dict = {"workId": ref, "projectId": "", "ownerActorId": ""}
        if event:
            work["workId"] = event.get("workId") or ref
            work["projectId"] = event.get("projectId") or ""
            work["ownerActorId"] = event.get("actorId") or ""
            observation = next(
                (
                    o
                    for o in observations
                    if o.get("workId") == work["workId"] and o.get("goalSourceRef") == ref
                ),
                None,
            )
            repo = observation.get("repository") if observation else None
            if isinstance(repo, dict) and repo.get("origin") and repo.get("branch"):
                work["checkout"] = {"origin": repo["origin"], "branch": repo["branch"]}
            harness = (event.get("data") or {}).get("harness")
            prefix = _source_ref_prefix((event.get("source") or {}).get("uri") or "")
            collector = {"harness": harness, "sourceRefPrefix": prefix}
            if harness and prefix and collector not in collectors:
                collectors.append(collector)
            if event.get("actorId") and event["actorId"] not in operators:
                operators.append(event["actorId"])
        index = len(works)
        for field in ("projectId", "ownerActorId"):
            if not work[field]:
                missing.append(f"works[{index}].{field}")
        works.append(work)
        sources.append(
            {
                "workId": work["workId"],
                "goalSourceRef": ref,
                "threadId": goal.thread_id,
                "nativeStatus": goal.native_status,
                "updatedAt": goal.updated_at,
                "matchedBundleEvent": bool(event),
            }
        )

    revisions = [revision] if isinstance(revision, str) and revision else []
    if not revisions:
        missing.append("supportedSourceRevisions")
    if not collectors:
        missing.append("collectors")
    if not operators:
        missing.append("operators")
    return {
        "schemaVersion": POLICY_SCHEMA,
        "supportedSourceRevisions": revisions,
        "collectors": collectors,
        "operators": operators,
        "works": works,
        "draft": {
            "createdAt": created_at,
            "status": "draft - not active until you run sbo-continuity approve",
            "sources": sources,
            "needsOwnerInput": missing,
        },
    }


def policy_gaps(policy: dict) -> list[str]:
    """Fields an active policy needs that are empty or malformed."""
    gaps = []
    if policy.get("schemaVersion") != POLICY_SCHEMA:
        gaps.append("schemaVersion")
    if not _nonempty_strings(policy.get("supportedSourceRevisions")):
        gaps.append("supportedSourceRevisions")
    if not _nonempty_strings(policy.get("operators")):
        gaps.append("operators")
    collectors = policy.get("collectors")
    if (
        not isinstance(collectors, list)
        or not collectors
        or not all(
            isinstance(c, dict) and _text(c.get("harness")) and _text(c.get("sourceRefPrefix"))
            for c in collectors
        )
    ):
        gaps.append("collectors")
    works = policy.get("works")
    if not isinstance(works, list) or not works:
        gaps.append("works")
        return gaps
    seen = set()
    for index, work in enumerate(works):
        for field in ("workId", "projectId", "ownerActorId"):
            if not isinstance(work, dict) or not _text(work.get(field)):
                gaps.append(f"works[{index}].{field}")
        if isinstance(work, dict):
            if work.get("workId") in seen:
                gaps.append(f"works[{index}].workId (duplicate)")
            seen.add(work.get("workId"))
    return gaps


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_strings(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_text(v) for v in value)


def approve_draft(paths: Paths, terminal: Terminal) -> dict:
    """Activate the draft after the owner reviews each work at an interactive terminal."""
    if not terminal.interactive:
        raise ContinuityError(
            "Approving a trust policy needs you at an interactive terminal; "
            "agents and scripts cannot approve it."
        )
    if paths.policy.exists():
        raise ContinuityError(
            f"A trust policy is already active at {paths.policy}. "
            "Edit it by hand, or move it aside first."
        )
    try:
        draft = json.loads(paths.draft.read_text("utf-8"))
    except (OSError, ValueError) as error:
        raise ContinuityError(
            f"No readable draft at {paths.draft}. Run sbo-continuity setup first."
        ) from error
    policy = {k: v for k, v in draft.items() if k != "draft"}
    gaps = policy_gaps(policy)
    if gaps:
        raise ContinuityError(
            "The draft is missing "
            + ", ".join(gaps)
            + f". Fill them in {paths.draft}, then run approve again."
        )
    kept = []
    for work in policy["works"]:
        checkout = work.get("checkout")
        where = f" on {checkout['origin']} {checkout['branch']}" if checkout else ""
        answer = terminal.ask(
            f"Trust {work['workId']} (project {work['projectId']}, "
            f"owner {work['ownerActorId']}){where}? [y/N] "
        )
        if answer.strip().lower() in ("y", "yes"):
            kept.append(work)
    if not kept:
        raise ContinuityError("You did not trust any work, so no policy was written.")
    policy["works"] = kept
    if terminal.ask("Type approve to activate this trust policy: ").strip() != "approve":
        raise ContinuityError("Not approved. Nothing was written.")
    try:
        _write_private(paths.policy, json.dumps(policy, indent=2) + "\n", exclusive=True)
    except FileExistsError as error:
        raise ContinuityError(
            f"A trust policy appeared at {paths.policy} while you were approving."
        ) from error
    return policy


# ---------------------------------------------------------------- locks


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) on Windows sends CTRL_C_EVENT, so ask the kernel instead.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # HANDLE is pointer-sized even on Windows, where C long stays 32-bit.
        kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            # Only INVALID_PARAMETER proves the positive PID does not exist.
            # Permission and other query failures cannot authorize lock removal.
            return ctypes.get_last_error() != 87
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass(frozen=True)
class LockState:
    path: Path
    kind: str  # running | crashed | other-host | unreadable
    owner: dict | None

    def advice(self) -> str:
        name = self.path.name
        if self.kind == "running":
            return f"{name}: an import is running (pid {self.owner['pid']}). Wait for it to finish."
        if self.owner and self.owner.get("operation") == "restore":
            return (
                f"{name}: a restore was interrupted; inspect the active store and "
                f"the recovery folder {self.owner.get('recovery')} before repairing it. "
                "Unlock cannot clear an unfinished restore."
            )
        if self.path.name == MUTEX_NAME:
            return (
                f"{name}: a crashed lock reclaim left this behind, "
                "and SIS stops imports until it is gone. "
                "Run sbo-continuity unlock after confirming no import is running."
            )
        if self.kind == "crashed":
            return (
                f"{name}: the import that held it has exited. "
                "The next import reclaims it on its own; "
                "sbo-continuity unlock also clears it."
            )
        if self.kind == "other-host":
            return (
                f"{name}: held by host {self.owner['host']}. "
                "Check that machine has no import running, "
                "then run sbo-continuity unlock."
            )
        return f"{name}: unreadable. Confirm no import is running, then run sbo-continuity unlock."


def inspect_lock(path: Path) -> LockState | None:
    if not path.exists():
        return None
    try:
        owner = json.loads(path.read_text("utf-8"))
        valid = (
            isinstance(owner, dict)
            and isinstance(owner.get("pid"), int)
            and isinstance(owner.get("host"), str)
            and isinstance(owner.get("token"), str)
        )
    except (OSError, ValueError):
        valid = False
    if not valid:
        return LockState(path, "unreadable", None)
    if owner["host"] != socket.gethostname():
        return LockState(path, "other-host", owner)
    return LockState(path, "running" if _pid_alive(owner["pid"]) else "crashed", owner)


def store_locks(store: Path) -> list[LockState]:
    return [s for s in (inspect_lock(store / MUTEX_NAME), inspect_lock(store / LOCK_NAME)) if s]


def unlock(paths: Paths, terminal: Terminal) -> list[Path]:
    """Remove a lock and mutex left by a crash, after the operator confirms.

    SIS leaves this to an operator on purpose: clearing a reclaim mutex
    automatically would itself race. A live holder on this host is never removed.
    """
    states = store_locks(paths.store)
    if not states:
        return []
    running = [s for s in states if s.kind == "running"]
    if running:
        raise ContinuityError(running[0].advice())
    interrupted = [s for s in states if s.owner and s.owner.get("operation") == "restore"]
    if interrupted:
        raise ContinuityError(interrupted[0].advice())
    if not terminal.interactive:
        raise ContinuityError("Clearing a lock needs you at an interactive terminal.")
    for state in states:
        click.echo(state.advice())
    if terminal.ask("Type unlock once you are sure no import is running: ").strip() != "unlock":
        raise ContinuityError("Not confirmed. Nothing was removed.")
    removed = []
    # Mutex first: SIS re-checks the lock owner under it, so the lock goes last.
    for state in states:
        current = inspect_lock(state.path)
        if current is None:
            continue
        if current.kind == "running" or current.owner != state.owner:
            raise ContinuityError(
                f"{state.path.name} changed while you were confirming. Run unlock again."
            )
        state.path.unlink()
        removed.append(state.path)
    return removed


# ---------------------------------------------------------------- backup and restore


def _store_files(store: Path) -> list[Path]:
    files = []
    for entry in sorted(store.iterdir()):
        if entry.name in (LOCK_NAME, MUTEX_NAME):
            continue
        if entry.is_dir() or entry.is_symlink():
            raise ContinuityError(
                f"Unexpected entry {entry.name} in the store. Inspect it before backing up."
            )
        files.append(entry)
    return files


def _refuse_if_locked(store: Path, action: str) -> None:
    states = store_locks(store)
    if states:
        raise ContinuityError(
            f"Cannot {action} while the store is locked. " + " ".join(s.advice() for s in states)
        )


def backup(paths: Paths, destination: Path | None = None) -> Path:
    """Copy the store and active policy into a new folder in the private vault."""
    if not paths.store.is_dir():
        raise ContinuityError(
            f"No continuity store at {paths.store}; there is nothing to back up yet."
        )
    private = _vault("SBO_PRIVATE_VAULT_ROOT")
    if destination is None:
        if private is None:
            raise ContinuityError(
                "Set SBO_PRIVATE_VAULT_ROOT or pass --to; backups belong in the private vault."
            )
        destination = private / "_continuity-backups" / _stamp()
    brain = _vault("SBO_BRAIN_VAULT_ROOT")
    if brain is not None and _is_within(brain, destination):
        raise ContinuityError(
            "Backups hold private IDs and paths; "
            "the brain vault is readable over MCP. Use private/."
        )
    if _is_within(paths.home, destination):
        raise ContinuityError(
            "A backup inside the continuity folder would be lost with it. Choose another place."
        )
    _refuse_if_locked(paths.store, "back up")

    files = _store_files(paths.store)
    before = {f.name: f.stat() for f in files}
    try:
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    except FileExistsError as error:
        raise ContinuityError(
            f"{destination} already exists. Choose a new folder for each backup."
        ) from error
    try:
        entries = {}
        sources = [(f, f"store/{f.name}") for f in files]
        if paths.policy.is_file():
            sources.append((paths.policy, f"{POLICY_DIR}/{paths.policy.name}"))
        for source, relative in sources:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            os.chmod(target, 0o600)
            entries[relative] = {"sha256": _sha256_file(target), "bytes": target.stat().st_size}
            if entries[relative]["sha256"] != _sha256_file(source):
                raise ContinuityError(
                    f"{source.name} changed while it was copied. Run backup again."
                )
        # An import that started mid-copy would make the files inconsistent with each other.
        after = {f.name: f.stat() for f in _store_files(paths.store)}
        changed = set(before) != set(after) or any(
            (before[n].st_size, before[n].st_mtime_ns) != (after[n].st_size, after[n].st_mtime_ns)
            for n in before
        )
        if changed or store_locks(paths.store):
            raise ContinuityError(
                "An import ran during the backup. Run backup again once it finishes."
            )
        manifest = {
            "schemaVersion": BACKUP_SCHEMA,
            "createdAt": datetime.now(UTC).isoformat(),
            "host": socket.gethostname(),
            "files": entries,
            "complete": True,
        }
        # The manifest is written last; a folder without one is an interrupted backup.
        with (destination / BACKUP_MANIFEST).open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(manifest, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(destination / BACKUP_MANIFEST, 0o600)
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination


def verify_backup(source: Path) -> dict:
    try:
        manifest = json.loads((source / BACKUP_MANIFEST).read_text("utf-8"))
    except (OSError, ValueError) as error:
        raise ContinuityError(
            f"{source} has no readable {BACKUP_MANIFEST}; it is not a finished backup."
        ) from error
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("schemaVersion") != BACKUP_SCHEMA
        or manifest.get("complete") is not True
        or not isinstance(files, dict)
    ):
        raise ContinuityError(f"{source} is not a finished {BACKUP_SCHEMA} backup.")
    root = source.resolve()
    for relative, entry in files.items():
        parts = relative.split("/")
        if (
            len(parts) != 2
            or parts[0] not in ("store", POLICY_DIR)
            or parts[1] in ("", ".", "..", LOCK_NAME, MUTEX_NAME)
            or parts[1].casefold() in (LOCK_NAME, MUTEX_NAME)
            or any(char in parts[1] for char in "\\:")
            or any(ord(char) < 32 for char in parts[1])
            or parts[1].endswith((" ", "."))
            or (parts[0] == POLICY_DIR and parts[1] != "trust-policy.json")
        ):
            raise ContinuityError(f"The backup manifest names an unexpected file: {relative}")
        if not isinstance(entry, dict):
            raise ContinuityError(f"The backup manifest has no checksum record for {relative}.")
        path = source / relative
        if (
            not _is_within(root, path)
            or path.resolve().parent != (root / parts[0]).resolve()
            or path.is_symlink()
            or (source / parts[0]).is_symlink()
            or not path.is_file()
        ):
            raise ContinuityError(f"The backup is missing {relative}.")
        if path.stat().st_size != entry.get("bytes") or _sha256_file(path) != entry.get("sha256"):
            raise ContinuityError(
                f"{relative} in the backup does not match its checksum. Use another backup."
            )
    return manifest


@contextmanager
def _restore_locks(store: Path):
    """Hold SIS's stable writer path and fence its dead-lock reclaimer after a crash."""
    _refuse_if_locked(store, "restore")
    owner = {"pid": os.getpid(), "host": socket.gethostname(), "token": str(uuid4()),
             "operation": "restore", "recovery": None}
    acquired = []
    try:
        for name in (LOCK_NAME, MUTEX_NAME):
            path = store / name
            try:
                _write_private(path, json.dumps(owner), exclusive=True)
            except FileExistsError as error:
                raise ContinuityError(
                    "Cannot restore while another store writer is locked."
                ) from error
            acquired.append(path)
        yield owner
    finally:
        if not owner.get("recoveryRequired"):
            for path in reversed(acquired):
                try:
                    current = json.loads(path.read_text("utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(current, dict) and current.get("token") == owner["token"]:
                    path.unlink()


def _assert_restore_locks(store: Path, owner: dict) -> None:
    for name in (LOCK_NAME, MUTEX_NAME):
        try:
            current = json.loads((store / name).read_text("utf-8"))
        except (OSError, ValueError) as error:
            raise ContinuityError(
                "Restore lost its store lock; inspect before retrying."
            ) from error
        if not isinstance(current, dict) or current.get("token") != owner["token"]:
            raise ContinuityError("Restore lost its store lock; inspect before retrying.")


def restore(paths: Paths, source: Path, *, replace: bool = False) -> dict:
    """Keep the store's lock path stable; preserve its old contents before replacement."""
    manifest = verify_backup(source)
    store_entries = {r: e for r, e in manifest["files"].items() if r.startswith("store/")}
    policy_entry = manifest["files"].get(f"{POLICY_DIR}/trust-policy.json")
    policy_bytes = None
    if policy_entry is not None:
        policy_bytes = (source / POLICY_DIR / "trust-policy.json").read_bytes()
        if (
            len(policy_bytes) != policy_entry["bytes"]
            or sha256(policy_bytes).hexdigest() != policy_entry["sha256"]
        ):
            raise ContinuityError("The backed-up policy changed after checksum verification.")
    paths.home.mkdir(parents=True, exist_ok=True)
    if paths.store.is_symlink():
        raise ContinuityError("The store is a symbolic link; inspect it before restoring.")
    paths.store.mkdir(exist_ok=True, mode=0o700)
    moved_aside = None
    with _restore_locks(paths.store) as owner:
        staging = Path(tempfile.mkdtemp(dir=paths.home, prefix=f".store.restoring-{_stamp()}-"))
        moved, installed = [], []
        try:
            for relative, entry in store_entries.items():
                target = staging / relative.split("/", 1)[1]
                shutil.copyfile(source / relative, target)
                os.chmod(target, 0o600)
                if _sha256_file(target) != entry["sha256"]:
                    raise ContinuityError(
                        f"{relative} changed while it was restored. Run restore again."
                    )
            original = _store_files(paths.store)
            if original and not replace:
                raise ContinuityError(
                    f"{paths.store} already holds data. Run restore with --replace first."
                )
            if original:
                moved_aside = Path(tempfile.mkdtemp(
                    dir=paths.home, prefix=f"store.before-restore-{_stamp()}-"
                ))
            owner["recovery"] = str(moved_aside) if moved_aside else None
            _assert_restore_locks(paths.store, owner)
            _write_private(paths.store / MUTEX_NAME, json.dumps(owner), exclusive=False)
            for entry in original:
                _assert_restore_locks(paths.store, owner)
                os.replace(entry, moved_aside / entry.name)
                moved.append(entry.name)
            for entry in list(staging.iterdir()):
                _assert_restore_locks(paths.store, owner)
                os.replace(entry, paths.store / entry.name)
                installed.append(entry.name)
        except BaseException:
            if moved or installed:
                try:
                    _assert_restore_locks(paths.store, owner)
                    for name in reversed(installed):
                        os.replace(paths.store / name, staging / name)
                    for name in reversed(moved):
                        os.replace(moved_aside / name, paths.store / name)
                except BaseException as rollback_error:
                    owner["recoveryRequired"] = True
                    raise ContinuityError(
                        "Restore rollback failed; store locks and recovery files are preserved. "
                        f"Inspect {paths.store}, {moved_aside} and {staging}."
                    ) from rollback_error
            raise
        finally:
            if not owner.get("recoveryRequired"):
                shutil.rmtree(staging, ignore_errors=True)

    policy_result = None
    if policy_entry is not None:
        try:
            _write_private_bytes(paths.policy, policy_bytes, exclusive=True)
        except FileExistsError:
            if _sha256_file(paths.policy) == policy_entry["sha256"]:
                policy_result = "unchanged"
            else:
                # Preserve a policy activated while this restore was in flight.
                side = paths.home / "trust-policy.restored.json"
                _write_private_bytes(side, policy_bytes, exclusive=False)
                policy_result = f"kept the active policy; the backed-up one is at {side}"
        else:
            policy_result = "restored"
    return {"files": len(store_entries), "movedAside": moved_aside, "policy": policy_result}


# ---------------------------------------------------------------- SIS and Canvas


def find_sis_cli(explicit: str | None) -> tuple[Path | None, str]:
    value = explicit or os.environ.get("STARLIGHT_CONTINUITY_CLI", "").strip()
    if not value:
        return None, "STARLIGHT_CONTINUITY_CLI is not set. Point it at SIS dist/continuity-cli.js."
    cli = Path(value)
    if not cli.is_absolute() or not cli.is_file():
        return None, f"No SIS continuity CLI at {value}. Build SIS (npm run build) or fix the path."
    if shutil.which("node") is None:
        return None, "Node.js is not on PATH; SIS needs it."
    return cli, f"SIS continuity CLI found at {cli}."


def canvas_url() -> str:
    return os.environ.get("SBO_CANVAS_URL", DEFAULT_CANVAS_URL).rstrip("/") + "/continuity"


def note_text(url: str) -> str:
    return (
        "# What was I doing\n\n"
        f"[Open my recovered work]({url})\n\n"
        "This opens the continuity page in Starlight Agent Canvas, which reads the SIS\n"
        "continuity store on this machine. Start Canvas first (`pnpm dev` in its folder).\n\n"
        "The page shows what each session was asked to do, the exact checkout and whether\n"
        "it has uncommitted work. Nothing resumes on its own; paused work waits for you.\n\n"
        "This note holds only the link. The store itself stays outside both vaults, and its\n"
        "backups go to the private vault.\n"
    )


def write_note(brain: Path, url: str) -> Path | None:
    target = brain / "_moc" / NOTE_NAME
    if target.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(note_text(url), encoding="utf-8", newline="\n")
    return target


# ---------------------------------------------------------------- CLI


def _fail(error: ContinuityError) -> None:
    click.echo(str(error), err=True)
    raise SystemExit(1)


@click.group(
    help="Set up, back up and restore SIS session continuity for this Second Brain install."
)
def cli() -> None:
    pass


@cli.command(help="Check for SIS and draft a trust policy from your own native goal records.")
@click.option(
    "--goals",
    "goals_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Codex goal store (default: ~/.codex/goals_1.sqlite).",
)
@click.option(
    "--bundle",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="A verified collector bundle that fills project, owner and checkout.",
)
@click.option("--sis-cli", default=None, help="Path to SIS dist/continuity-cli.js.")
@click.option("--replace-draft", is_flag=True, help="Overwrite an earlier draft.")
def setup(
    goals_path: Path | None, bundle: Path | None, sis_cli: str | None, replace_draft: bool
) -> None:
    paths = Paths.from_env()
    try:
        found, message = find_sis_cli(sis_cli)
        click.echo(("ok    " if found else "todo  ") + message)
        if paths.policy.exists():
            click.echo(
                f"ok    A trust policy is already active at {paths.policy}. Setup leaves it alone."
            )
            return
        if paths.draft.exists() and not replace_draft:
            raise ContinuityError(
                f"A draft already exists at {paths.draft}. Review it, or pass --replace-draft."
            )
        goals = read_native_goals(goals_path or default_goal_store())
        verified = read_verified_bundle(bundle) if bundle else None
        policy = draft_policy(goals, verified, created_at=datetime.now(UTC).isoformat())
        if not policy["works"]:
            raise ContinuityError(
                "Your goal store has no open goals, so there is nothing to trust yet."
            )
        _write_private(paths.draft, json.dumps(policy, indent=2) + "\n", exclusive=False)
        click.echo(f"ok    Draft trust policy written to {paths.draft} (not active).")
        by_ref = {g.goal_id: g for g in goals}
        for source in policy["draft"]["sources"]:
            goal = by_ref[source["goalSourceRef"].split(":", 1)[1]]
            click.echo(f"      {source['workId']}  [{goal.state}]  {goal.objective.strip()[:70]}")
        gaps = policy["draft"]["needsOwnerInput"]
        if gaps:
            click.echo("todo  Fill these in the draft before approving: " + ", ".join(gaps))
        brain = _vault("SBO_BRAIN_VAULT_ROOT")
        if brain is not None and brain.is_dir():
            note = write_note(brain, canvas_url())
            if note:
                click.echo(f"ok    Added a 'What was I doing' note to {note.parent}.")
        click.echo("next  Run sbo-continuity approve to review and activate it.")
    except ContinuityError as error:
        _fail(error)


@cli.command(help="Review the draft and activate it. Needs you at an interactive terminal.")
def approve() -> None:
    try:
        policy = approve_draft(Paths.from_env(), _ProcessTerminal())
    except ContinuityError as error:
        _fail(error)
    click.echo(f"Trust policy active with {len(policy['works'])} work(s).")


@cli.command(help="Report SIS, policy, store and lock state.")
def doctor() -> None:
    paths = Paths.from_env()
    healthy = True
    found, message = find_sis_cli(None)
    click.echo(("ok    " if found else "todo  ") + message)
    if paths.policy.is_file():
        click.echo(f"ok    Trust policy active at {paths.policy}.")
    elif paths.draft.is_file():
        click.echo("todo  A draft policy is waiting. Run sbo-continuity approve.")
    else:
        click.echo("todo  No trust policy yet. Run sbo-continuity setup.")
    if paths.store.is_dir():
        files = [
            f
            for f in paths.store.iterdir()
            if f.is_file() and f.name not in (LOCK_NAME, MUTEX_NAME)
        ]
        click.echo(
            f"ok    Store at {paths.store}: "
            + (", ".join(f"{f.name} {f.stat().st_size} B" for f in files) or "empty")
        )
        for state in store_locks(paths.store):
            healthy = healthy and state.kind == "running"
            click.echo(("wait  " if state.kind == "running" else "fix   ") + state.advice())
    else:
        click.echo("ok    No store yet; the first import creates it.")
    click.echo(f"view  {canvas_url()}")
    raise SystemExit(0 if healthy else 1)


@cli.command(name="unlock", help="Clear an import lock or reclaim mutex left by a crash.")
def unlock_command() -> None:
    try:
        removed = unlock(Paths.from_env(), _ProcessTerminal())
    except ContinuityError as error:
        _fail(error)
    click.echo("Removed " + ", ".join(p.name for p in removed) if removed else "No lock to clear.")


@cli.command(name="backup", help="Copy the store and policy into the private vault.")
@click.option("--to", "destination", type=click.Path(path_type=Path, file_okay=False), default=None)
def backup_command(destination: Path | None) -> None:
    try:
        target = backup(Paths.from_env(), destination)
    except ContinuityError as error:
        _fail(error)
    click.echo(f"Backup written to {target}")


@cli.command(name="restore", help="Restore a backup after checking every checksum.")
@click.option(
    "--from", "source", required=True, type=click.Path(path_type=Path, file_okay=False, exists=True)
)
@click.option("--replace", is_flag=True, help="Move an existing store aside instead of refusing.")
def restore_command(source: Path, replace: bool) -> None:
    try:
        result = restore(Paths.from_env(), source, replace=replace)
    except ContinuityError as error:
        _fail(error)
    click.echo(f"Restored {result['files']} store file(s).")
    if result["movedAside"]:
        click.echo(f"The previous store is kept at {result['movedAside']}.")
    if result["policy"]:
        click.echo(f"Trust policy: {result['policy']}.")


@cli.command(name="open", help="Open the 'what was I doing' page in Canvas.")
def open_command() -> None:
    url = canvas_url()
    click.echo(url)
    webbrowser.open(url)


if __name__ == "__main__":
    cli()
