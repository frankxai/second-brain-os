# /sbo-verify — Verify SBO installation health

Run all health checks:

1. Privacy verification (`scripts/verify-privacy.{ps1,sh}` on the private vault).
2. Brain vault sanity: confirm `CLAUDE.md`, `_capture.md`, `_inbox/`, `notes/`, `people/`, `patterns/` exist with correct ownership.
3. MCP wiring: query the Obsidian MCP server for `list_files_in_vault` — should return brain/ files only, never private/ files.
4. Symlink resolution (personal instance only): if `_agents/`, `_meta/family.md`, etc. are symlinks, confirm targets resolve.
5. Banned-phrase scan: read the last 10 files in `_inbox/` and report any voice violations.

Report a verdict: PASS / WARN / FAIL with specific items.

Built on SIP.
