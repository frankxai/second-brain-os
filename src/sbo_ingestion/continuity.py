"""Session continuity, SIS detection, draft trust policy, and two-vault recovery."""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import frontmatter


def check_sis_installed(custom_path: Path | None = None) -> bool:
    """Check if Starlight Intelligence System (SIS) substrate is available."""
    if custom_path is not None:
        return custom_path.is_dir()
    env_root = os.environ.get("SBO_SIS_ROOT") or os.environ.get("SIS_ROOT")
    if env_root and Path(env_root).exists():
        return True
    home = Path.home()
    return any(
        p.exists()
        for p in (
            home / ".starlight",
            home / "Starlight-Intelligence-System",
            home / "second-brain" / "starlight",
        )
    )


def discover_native_goals(brain_root: Path) -> list[dict[str, str]]:
    """Scan brain vault for native goal records without inventing IDs."""
    goals: list[dict[str, str]] = []
    projects_dir = brain_root / "projects"
    if not projects_dir.exists():
        return goals

    for path in sorted(projects_dir.glob("**/*.md")):
        if path.name.startswith("."):
            continue
        try:
            post = frontmatter.load(path)
            metadata = post.metadata or {}
            goal_id = metadata.get("goal_id") or metadata.get("id")
            title = metadata.get("title") or metadata.get("name") or path.stem

            if goal_id or "goal" in metadata or "outcome" in metadata:
                goals.append(
                    {
                        "goal_id": str(goal_id) if goal_id else path.stem,
                        "title": str(title),
                        "path": path.relative_to(brain_root).as_posix(),
                        "status": str(metadata.get("status", "active")),
                    }
                )
            elif post.content:
                for line in post.content.splitlines():
                    if line.startswith("# ") or line.startswith("## Goal:"):
                        goals.append(
                            {
                                "goal_id": path.stem,
                                "title": line.lstrip("#").strip(),
                                "path": path.relative_to(brain_root).as_posix(),
                                "status": str(metadata.get("status", "active")),
                            }
                        )
                        break
        except Exception:
            continue
    return goals


def write_draft_trust_policy(brain_root: Path, goals: list[dict[str, str]]) -> Path:
    """Write a draft trust policy from native goals for user approval."""
    meta_dir = brain_root / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    policy_path = meta_dir / "trust-policy.md"
    now = datetime.now(UTC).isoformat()

    lines = (
        [
            f"- **Goal ID:** `{g['goal_id']}` | **Title:** {g['title']} | **Source:** `{g['path']}`"
            for g in goals
        ]
        if goals
        else ["- *No native goals discovered. Add goal files under `projects/`.*"]
    )

    content = f"""---
title: Session Continuity Draft Trust Policy
status: pending_approval
approved: false
created_at: {now}
---

# Session Continuity Trust Policy (Draft)

> **Human Approval Required:** Set `approved: true` in frontmatter when verified.

## Discovered Native Goals

{chr(10).join(lines)}

## Policy Rules

1. Session continuity context may only bind to approved native goal records.
2. Continuity cache in `~/.starlight/c` retains active task state and crash checkpoints.
3. Recovery restores from `~/.starlight/c` backups without modifying goal files.

Built on SIP.
"""
    policy_path.write_text(content, encoding="utf-8")
    return policy_path


def get_starlight_continuity_dir(custom_path: Path | None = None) -> Path:
    """Return location of ~/.starlight/c continuity state directory."""
    return custom_path or (Path.home() / ".starlight" / "c")


def backup_continuity_state(
    starlight_c_dir: Path | None = None,
    backup_root: Path | None = None,
) -> Path:
    """Backup ~/.starlight/c continuity directory."""
    source = get_starlight_continuity_dir(starlight_c_dir)
    if not source.exists():
        source.mkdir(parents=True, exist_ok=True)
        (source / "active_session.json").write_text('{"status": "idle"}', encoding="utf-8")

    dest_root = backup_root or (source.parent / "c_backups")
    dest_root.mkdir(parents=True, exist_ok=True)
    target_backup = dest_root / f"backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(source, target_backup)
    return target_backup


def restore_continuity_state(backup_path: Path, starlight_c_dir: Path | None = None) -> Path:
    """Restore ~/.starlight/c continuity directory from backup."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup path does not exist: {backup_path}")
    target = get_starlight_continuity_dir(starlight_c_dir)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(backup_path, target)
    return target
