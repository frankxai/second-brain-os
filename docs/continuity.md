# Session continuity

When a machine crashes or a session dies, you lose track of what each AI session was
working on. Session continuity keeps a private record of it. The record answers four
questions: what you asked for, in which checkout, whether that checkout had
uncommitted work, and whether you ever approved the work to go ahead.

Second Brain OS doesn't run continuity itself. The parts come from other Starlight
projects:

| Part | Where it lives | What it does |
|---|---|---|
| Collector | `agentic-ops` `lifecycle/sis-continuity.js` | Exports what each bound session was asked to do as a checksummed bundle |
| Store and trust rules | Starlight Intelligence System (SIS) `continuity-cli` | Imports bundles, quarantines claims it can't trust, keeps admission with you |
| "What was I doing" page | Starlight Agent Canvas `/continuity` | Shows the store, read-only |
| Setup, backup and restore | This repo, `sbo-continuity` | Drafts the trust policy and protects the store |

The store lives at `~/.starlight/continuity/store` (or `$SIS_CONTINUITY_HOME/store`).
It's outside both vaults. It contains private IDs, paths and request digests, so its
backups go in `private/`. They never go in `brain/`.

## Setup

You need Python with this package installed (see [Getting started](getting-started.md)).
Node.js and SIS are only needed to import and view work. Setup checks for them and
tells you what's missing.

**Without a terminal:** double-click `scripts/continuity-setup.cmd` on Windows or
`scripts/continuity-setup.command` on macOS. A window opens and walks you through
the same steps as below.

**From a terminal:**

```bash
sbo-continuity setup --bundle <folder the collector exported>
sbo-continuity approve
```

`setup` does four things:

1. Looks for the SIS continuity CLI at `STARLIGHT_CONTINUITY_CLI`, the same setting
   Canvas uses. It should point to SIS `dist/continuity-cli.js`.
2. Reads your open goals from Codex's goal store (`~/.codex/goals_1.sqlite`, or pass
   `--goals`). It reads a private snapshot so Codex is never blocked, and it skips
   finished goals.
3. Writes a **draft** trust policy to `~/.starlight/continuity/trust-policy.draft.json`.
   Each open goal becomes one work. If you pass `--bundle`, the bundle's own records
   fill in the project, owner, collector, SIS revision and checkout for the goals it
   covers. The bundle is checked against its manifest first. No ID is made up.
   Anything your records don't supply stays empty and is listed under
   `draft.needsOwnerInput`.
4. Adds a "What was I doing" note to your brain vault if `SBO_BRAIN_VAULT_ROOT` is set.

The draft does nothing on its own, because SIS only reads `trust-policy.json`.
`approve` turns it on:

- It only runs at an interactive terminal. An agent or script can't approve a policy.
- It refuses while any required field is empty and names the field. Open the draft
  in any text editor, fill in the field, and run `approve` again.
- It shows each work with its project, owner and checkout, and you answer y or n
  for each one.
- You type `approve` to finish. It never overwrites a policy that's already active.

After that, import bundles with SIS as usual
(`node dist/continuity-cli.js import <bundle folder>`).

## What was I doing

Open the **What was I doing** note in your brain vault (`_moc/What was I doing.md`)
and click the link. It opens `http://localhost:3000/continuity` in Starlight Agent
Canvas. Start Canvas first with `pnpm dev` in its folder. If Canvas runs elsewhere,
set `SBO_CANVAS_URL`. `sbo-continuity open` opens the same page.

The page shows each recovered work with its state, owner, checkout, uncommitted-work
flag, admission and missing proof. It is read-only. Nothing resumes on its own.
Paused or blocked work waits until you reconcile it at a terminal with SIS
`reconcile`.

The note contains only the link. No store data enters the brain vault.

## Back up and restore

```bash
sbo-continuity backup                     # into private/_continuity-backups/<time>/
sbo-continuity backup --to <new folder>   # anywhere outside brain/ and the store
sbo-continuity restore --from <backup folder>
```

A backup contains every file in the store (`events.jsonl`, `observations.jsonl`,
`quarantine.jsonl`, `imports.jsonl`), the active `trust-policy.json`, and
`continuity-backup.json`, which lists each file's SHA-256 and size. The manifest is
written last, so a folder without it is an unfinished backup and restore refuses it.

Backup refuses to run:

- while the store has an import lock or reclaim mutex (see below);
- if an import changes the store while it copies. Run it again;
- into the brain vault, which MCP can read;
- into an existing folder.

Restore checks every checksum before it changes anything. It copies into a staging
folder next to the store, checks each file again, then swaps the staging folder in.
It's careful with what's already there:

- If a store with data exists, restore refuses unless you pass `--replace`. With
  `--replace`, the old store is renamed to `store.before-restore-<time>` and kept.
  Delete it yourself once you've checked the restore.
- If no trust policy is active, the backed-up one is restored. If a different one is
  active, restore keeps it. The backed-up copy goes to `trust-policy.restored.json`
  for you to compare, because the policy decides what SIS trusts.

Restored files are byte-for-byte the same as the backup, and that includes a torn last
line left by a crashed import. SIS ignores a torn last line on read and trims it
before its next write.

**Keep a second copy.** The privacy checklist excludes `private/` from OneDrive,
iCloud and Time Machine, so a backup in `private/` alone dies with the disk. After a
backup, copy its folder to an encrypted USB drive or another offline place. Restore
works from any folder.

## After a crash

Run `sbo-continuity doctor`. It reports SIS, the policy, the store files and any lock,
with the next step for each. It exits 1 when something needs you.

SIS serializes imports with `store/.import.lock`. It records the process ID, host and
a token for the import that holds it.

| What doctor says | What happened | What to do |
|---|---|---|
| An import is running | A live process on this machine holds the lock | Wait. It is never removed while the process lives |
| The import that held it has exited | The import crashed | Nothing. The next import reclaims it on its own. `sbo-continuity unlock` also clears it |
| A crashed lock reclaim left `.import.lock.reclaim` | An import crashed while reclaiming a lock | SIS stops imports until it's gone. Run `sbo-continuity unlock` |
| Held by host X | The store was copied or synced from another machine | Check that machine has no import running, then `sbo-continuity unlock` |
| Unreadable | The lock file is damaged | Check that no import is running, then `sbo-continuity unlock` |

`unlock` needs you at an interactive terminal. It refuses outright if the holder
process is still alive on this machine. It lists what it found, asks you to type
`unlock`, checks each file again, and removes the mutex before the lock. It never
touches store data.

An interrupted import is safe to run again. SIS writes observations, then events,
then the receipt, so a replay fills in whatever is missing and counts what's already
stored as duplicates. If SIS reports a corrupt complete line, restore the latest backup.

## Honest limits

- **Owner presence is not authentication.** Typing a work ID at a terminal, or typing
  `approve` or `unlock`, shows that someone is at this machine's keyboard. It doesn't
  prove who they are. Anyone with your login can do the same.
- **Collector claims are not signed.** A bundle's manifest proves its files are
  consistent. It doesn't prove who produced them. Every imported claim stays marked
  `collector-claimed`. Signed collector attestation is a protocol change pending the
  SIP Board. Until it lands, the boundary is your trust policy plus the store being
  private to your account.
- **Paused, blocked and complete are reported labels.** They come from the native
  goal store or from you. They are not verified lifecycle transitions.
- **Only Codex goals are drafted.** Codex is the harness with a native goal store
  today. Claude and Grok sessions still work through collector bundles, but you add
  their works to the policy yourself.
- **Windows file permissions** come from the folder's inherited NTFS ACLs. On macOS and
  Linux, files are written owner-only. On Windows that isn't verified.
- **Nothing here resumes, admits or runs work.** Admission stays with SIS `reconcile`
  at an interactive terminal.

## Proof

`tests/test_continuity.py` builds a store with CRLF lines, non-ASCII text, a torn last
line and an empty file. It backs the store up, deletes the whole continuity folder,
restores, and compares every byte. It also runs the fresh-machine walkthrough: setup,
approve, a crash that leaves a lock and a reclaim mutex, doctor, unlock, backup,
wipe and restore.

To run the same round trip against real SIS, set `SBO_SIS_SRC` to a SIS `src/` folder
with Node and `npx` available. The test drafts and approves a policy, imports a bundle
with SIS, backs up, wipes, restores, and checks that SIS reports the same status and
that a replayed import changes nothing.
