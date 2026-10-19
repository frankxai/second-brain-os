"""Tests for session continuity, SIS detection, draft trust policy, and recovery."""

from pathlib import Path

import frontmatter

from sbo_ingestion.continuity import (
    backup_continuity_state,
    check_sis_installed,
    discover_native_goals,
    restore_continuity_state,
    write_draft_trust_policy,
)


def test_check_sis_installed(tmp_path: Path) -> None:
    sis_dir = tmp_path / ".starlight"
    assert not check_sis_installed(sis_dir)
    sis_dir.mkdir(parents=True)
    assert check_sis_installed(sis_dir)


def test_discover_native_goals_never_invents_ids(tmp_path: Path) -> None:
    brain_root = tmp_path / "brain"
    projects_dir = brain_root / "projects"
    projects_dir.mkdir(parents=True)

    assert discover_native_goals(brain_root) == []

    (projects_dir / "q4-growth.md").write_text(
        "---\ngoal_id: GOAL-101\ntitle: Expand Sales\nstatus: active\n---\n# Q4\n",
        encoding="utf-8",
    )
    (projects_dir / "product-v2.md").write_text(
        "---\nstatus: in_progress\n---\n# Launch SBO v0.3.0\n",
        encoding="utf-8",
    )

    discovered = discover_native_goals(brain_root)
    assert len(discovered) == 2
    g1 = next(g for g in discovered if g["goal_id"] == "GOAL-101")
    assert g1["title"] == "Expand Sales"
    assert g1["path"] == "projects/q4-growth.md"


def test_write_draft_trust_policy(tmp_path: Path) -> None:
    brain_root = tmp_path / "brain"
    goals = [{"goal_id": "G-202", "title": "Automate Intake", "path": "p/1.md", "status": "active"}]

    policy_path = write_draft_trust_policy(brain_root, goals)
    assert policy_path.exists()
    assert policy_path.relative_to(brain_root).as_posix() == "_meta/trust-policy.md"

    post = frontmatter.load(policy_path)
    assert post.metadata["status"] == "pending_approval"
    assert post.metadata["approved"] is False
    assert "G-202" in post.content


def test_backup_and_restore_continuity_state(tmp_path: Path) -> None:
    c_dir = tmp_path / "c"
    c_dir.mkdir(parents=True)
    (c_dir / "session.json").write_text('{"task": "test"}', encoding="utf-8")

    backup_root = tmp_path / "backups"
    backup_path = backup_continuity_state(starlight_c_dir=c_dir, backup_root=backup_root)
    assert backup_path.exists()

    (c_dir / "session.json").write_text('{"task": "corrupt"}', encoding="utf-8")

    restored = tmp_path / "c_restored"
    restore_continuity_state(backup_path, starlight_c_dir=restored)
    assert (restored / "session.json").read_text(encoding="utf-8") == '{"task": "test"}'
