---
name: sbo-verify
description: >
  Health-check a Second Brain OS installation. Verifies vault structure, privacy 
  boundary, MCP wiring, and voice rules. Triggers on: "verify my vault", 
  "check my second brain setup", "/sbo-verify", "is my vault healthy", 
  "check the SBO installation".
---

# SBO Installation Verification

Run a full health check on the Second Brain OS installation.

## Checks

### 1. Privacy boundary
```bash
# Confirm private/ is NOT inside brain/ and NOT accessible via Obsidian MCP
echo "Brain root: $SBO_BRAIN_VAULT_ROOT"
echo "Private root: $SBO_PRIVATE_VAULT_ROOT"
# They should be siblings, not nested
```

Verify `private/` has `.metadata_never_index` and `.obsidian-no-sync` files.

### 2. Vault structure
Confirm these paths exist under `brain/`:
- `CLAUDE.md`
- `_capture.md`
- `_inbox/claude-ai/`
- `_inbox/chatgpt/`
- `notes/ideas/`, `notes/learnings/`, `notes/decisions/`
- `people/`, `patterns/`, `projects/`
- `_moc/HOME.md`

### 3. Audit log
```bash
tail -5 "$SBO_PRIVATE_VAULT_ROOT/_distill/audit.jsonl" 2>/dev/null || echo "No audit log yet"
```
Show last 5 entries if present.

### 4. Pending stubs
```bash
grep -rl "status: needs-summary" "$SBO_BRAIN_VAULT_ROOT/_inbox/" 2>/dev/null | wc -l
```
Report how many stubs need distillation.

### 5. Voice scan
Read last 5 files in `brain/_inbox/`. Check for banned phrases: "delve into", "dive into", "it's worth noting", "certainly", "absolutely", "in conclusion", "to summarize".

## Report format

```
SBO Health Check — YYYY-MM-DD

✓ Privacy boundary: brain/ and private/ are siblings, correctly separated
✓ Vault structure: all required folders present
✓ Audit log: 2 entries (last: 2026-05-14)
⚠ Pending stubs: 2 files with status: needs-summary — run /sbo-distill
✓ Voice scan: no banned phrases in last 5 inbox files

Verdict: PASS (1 warning)
```

Built on SIP.
