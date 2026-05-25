---
name: sbo-distill
description: >
  Distill brain/_inbox/ stubs into atomic notes in a Second Brain OS vault.
  Phase A: fill needs-summary stubs with real content by reading raw conversations 
  from private/. Phase B: triage triage-status stubs into the right notes folder.
  Triggers on: "distill inbox", "process my inbox", "fill my stubs", "/distill-inbox",
  "sbo-distill", or when the user wants to promote _inbox items to atomic notes.
---

# SBO Inbox Distillation

Transform brain/_inbox/ stubs into atomic notes. Two phases: fill raw stubs with real summaries, then triage into the right folder.

## Privacy boundary

This skill reads raw content from `private/` ONE TIME per stub for distillation. After writing the atomic note to `brain/`, never reference private/ paths in output.

## Phase A — Fill needs-summary stubs

### Find stubs

Scan `brain/_inbox/` recursively. List files with `status: needs-summary` in frontmatter.

```bash
grep -rl "status: needs-summary" "$SBO_BRAIN_VAULT_ROOT/_inbox/"
```

Show count. Confirm before proceeding if > 5 stubs.

### For each stub

1. Read the stub → extract `private_file` path from frontmatter
2. Read raw content: `cat "private/$PRIVATE_FILE_PATH"` (use bash or file Read)
3. Generate atomic note:

```
## [Title — improve if needed]

**Core insight:** [What actually matters — 1-2 sentences, not a summary]

### Key points
- [Concrete claim + evidence or example]
- [3-8 points, specific not vague]

### Connections
- [[Related note]] if any
- Project: [[project]] if relevant

### Open loops
- [Pending question/action, or "None"]
```

Voice rules: direct, specific, no AI-slop ("delve", "dive into", "it's worth noting", "certainly"). Counts exact or labeled approximate.

4. Update stub:
   - Replace body with atomic note
   - `status: needs-summary` → `status: triage`
   - Add newly discovered tags
   - Keep `private_file` ref

5. Append to audit log:
```bash
python3 -c "
from pathlib import Path; from sbo_ingestion.audit import record_distill
record_distill(Path('private'), conversation_id='ID', agent='sbo-distill', summary_chars=N)
"
```

## Phase B — Triage

For each `status: triage` stub, propose destination:

| Destination | Use when |
|---|---|
| `notes/ideas/{slug}.md` | Half-baked thought worth keeping |
| `notes/learnings/{slug}.md` | Concrete lesson or insight |
| `notes/decisions/{slug}.md` | Recorded decision |
| `projects/{proj}/log.md` | Append to project log |
| `_archive/` | Keep but don't promote |
| *(delete)* | Noise |

Show all proposals. **Do not move files automatically.** Execute only after explicit human approval.

## Phase C — Refresh MOCs

After moves: update `brain/_moc/HOME.md`, `MOC-Patterns.md`, `MOC-Projects.md` with current link lists. Don't alter human-written structure.

Built on SIP.
