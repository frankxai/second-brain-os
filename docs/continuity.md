# Session Continuity & Recovery Runbook

> Non-coder session continuity and crash recovery inside the two-vault Second Brain OS install.

## Overview

Session continuity allows non-coder founders to resume active tasks and recover after unexpected crashes or session interruptions. Continuity operates within Second Brain OS's strict two-vault architecture (`brain/` and `private/`), using a local continuity cache at `~/.starlight/c`.

---

## 1. Guided Setup & SIS Detection

When setting up session continuity:

1. **Substrate Verification:** Setup checks if Starlight Intelligence System (SIS) is installed (`~/.starlight` or `SBO_SIS_ROOT`).
2. **Native Goal Discovery:** SBO scans your existing `projects/` folder for native goal records. It **never invents fake goal IDs or stub records**.
3. **Draft Trust Policy:** SBO creates a draft policy at `_meta/trust-policy.md` containing discovered native goals with `status: pending_approval` and `approved: false`.
4. **Human Approval:** Open `_meta/trust-policy.md` inside Obsidian and set `approved: true` in the frontmatter once you have verified the goal list.

---

## 2. One-Click "What Was I Doing?" View (`/continuity`)

Non-coder founders can instantly check session state without opening a terminal:

1. Open your Obsidian `brain/` vault.
2. In the `_moc/HOME.md` file, click **[[Continuity.canvas|/continuity]]**.
3. The Canvas view opens displaying:
   - **Active Session State:** Current task, status, and last active checkpoint.
   - **Recovery Anchors:** Links to your approved trust policy and recent project notes.
   - **Recovery Actions:** Next steps if a session was interrupted.

---

## 3. Two-Vault Crash Recovery Runbook (`~/.starlight/c`)

If your computer restarts unexpectedly or your AI session crashes, follow these steps to restore continuity state:

### Understanding `~/.starlight/c`
- `~/.starlight/c` holds active session checkpoints and state files.
- Automated snapshots are saved to `~/.starlight/c_backups/` before major operations.
- Vault notes in `brain/` and `private/` remain untouched during continuity cache recovery.

### Step-by-step Recovery Procedure

1. **Open Obsidian Canvas:** Open `[[Continuity.canvas|/continuity]]` to inspect the last active task state.
2. **Locate Continuity Snapshots:**
   - In your file explorer (Finder or Windows Explorer), navigate to `~/.starlight/c_backups/`.
   - Identify the most recent folder timestamp (e.g. `backup_20261012_120000`).
3. **Restore Continuity Cache:**
   - Copy the contents of the chosen backup folder into `~/.starlight/c/`.
   - Replace any corrupted checkpoint files.
4. **Resume Session:** Re-open your AI agent or session. The agent will read `~/.starlight/c/active_session.json` and resume your task seamlessly.

---

## Built on SIP

Governed by Starlight Intelligence Protocol v1.1.1 standards for sovereign context retention and zero token waste.
