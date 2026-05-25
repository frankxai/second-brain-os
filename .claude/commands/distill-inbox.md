# /distill-inbox — Distill brain/_inbox/ stubs into atomic notes

You are a distillation agent operating inside an SBO vault. This command runs two phases: (A) fill `needs-summary` stubs with real atomic-note content drawn from raw private/ conversations, then (B) triage `triage`-status stubs into the right notes folder.

## Privacy boundary note

This command reads raw content from `private/` ONE TIME per stub — this is the intended and only occasion where you cross the vault boundary. After distillation, you write exclusively to `brain/`. Never reference private/ paths in output artifacts.

---

## Phase A — Fill needs-summary stubs

### Step 1: Find stubs

Scan `brain/_inbox/` recursively. List all files with `status: needs-summary` in their YAML frontmatter. Show the user:

```
Found X stub(s) awaiting distillation:
  - brain/_inbox/claude-ai/2026-05-14-designing-a-second-brain.md
  - brain/_inbox/images/2026-05-15-notebook-page.md
  ...
```

Confirm before proceeding if X > 5. Proceed automatically for 1–5 stubs.

### Step 2: For each needs-summary stub

**Read the stub** from `brain/_inbox/` — extract:
- `private_file` frontmatter field (relative path to raw content in private/)
- `title`, `date`, existing tags, `source_type` (conversation vs image)

**Read the raw content** from the path resolved from `private_file` using your file Read tool or bash. This is the permitted cross-boundary read.

**Generate an atomic note body:**

```
## [Improved title if needed]

**Core insight:** [1–2 sentences — what actually matters here, not a summary]

### Key points
- [concrete, specific — no vague abstractions]
- [claim + evidence or example, not just a topic label]
- [3–8 points]

### Connections
- Links to [[existing note]] if relevant
- Relates to project: [[project name]] if relevant

### Open loops
- [Any open question, follow-up action, or decision pending — or "None"]
```

Voice rules: direct, technical, warm. Pattern recognition stated as insight, not restated as summary. No "in summary", "to conclude", "it's worth noting", "delve into". Counts are exact or marked as approximate.

**Update the stub:**
- Replace body content with your atomic note
- Change `status: needs-summary` → `status: triage`
- Add newly discovered tags to the `tags` array
- Keep `private_file` ref intact (informational only)

**Append to audit log** after each stub:
```bash
python3 -c "
from pathlib import Path
from sbo_ingestion.audit import record_distill
record_distill(
    Path('private'),
    conversation_id='REPLACE_WITH_ID_FROM_FILENAME',
    agent='distill-inbox',
    summary_chars=REPLACE_WITH_LEN
)
"
```
The `conversation_id` is the UUID or hash portion of the filename. `summary_chars` is the character count of the atomic note body you wrote.

---

## Phase B — Triage triage-status stubs

For each stub with `status: triage` in `brain/_inbox/`:

Read the stub. Propose a destination based on content:

| Destination | When to use |
|---|---|
| `notes/ideas/{slug}.md` | Half-baked thought worth keeping |
| `notes/learnings/{slug}.md` | Concrete lesson or insight |
| `notes/decisions/{slug}.md` | Recorded decision with context |
| `projects/{project}/log.md` | Append to existing project log |
| `_archive/` | Not worth promoting, preserve for backlinks |
| *(delete)* | Clearly noise, no value |

Display proposals in this format:
```
[1] 2026-05-14-designing-a-second-brain.md
    → notes/learnings/second-brain-architecture.md
    "Key insight on dual-vault privacy model"

[2] ...
```

**DO NOT move files automatically.** Show all proposals. Wait for explicit human confirmation (e.g. "move all" or "skip 2, move rest"). Only execute after approval.

Execute approved moves using bash `mv` or Obsidian MCP `patch_content`. Update source file status to `archived` or delete per instruction.

---

## Phase C — Refresh MOCs

After all moves complete, update:
- `brain/_moc/HOME.md` — updated note counts per folder
- `brain/_moc/MOC-Patterns.md` — if patterns/ changed
- `brain/_moc/MOC-Projects.md` — if projects/ changed

Do not alter human-written structure in MOCs — only refresh link lists and counts.

---

Built on SIP.
