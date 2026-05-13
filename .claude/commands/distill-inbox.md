# /distill-inbox — Triage brain/_inbox/ into atomic notes

Read every file in `brain/_inbox/` (last 30 days). For each, propose a destination:
- `notes/ideas/{slug}.md` — half-baked thought worth keeping
- `notes/learnings/{slug}.md` — concrete lesson learned
- `notes/decisions/{slug}.md` — recorded decision with context
- `projects/{existing-project}/log.md` — append to existing project log
- `_archive/` — not worth promoting, but preserved for backlinks
- (delete) — clearly noise, no value

Show me each proposal with a one-line summary and the file path. I confirm in batch.

DO NOT move files automatically. DO NOT touch private/ vault. Manual confirmation is the boundary.

After confirmation, execute the moves using the Obsidian MCP `patch_content` + `append_content` tools.

Built on SIP.
