# /sbo-verify — Verify SBO installation health

Run all health checks:

1. Privacy verification (`scripts/verify-privacy.{ps1,sh}` on the private vault).
2. Brain vault sanity: confirm `CLAUDE.md`, `_capture.md`, `_inbox/`, `notes/`, `people/`, `patterns/` exist with correct ownership.
3. MCP wiring: query the Obsidian MCP server for `list_files_in_vault` — should return brain/ files only, never private/ files.
4. Symlink resolution (personal instance only): if `_agents/`, `_meta/family.md`, etc. are symlinks, confirm targets resolve.
5. Banned-phrase scan: read the last 10 files in `_inbox/` and report any voice violations.

Report a verdict: PASS / WARN / FAIL with specific items.

## Reflection mode: the 4-check gate

When invoked by `/reflect` (or any agent producing questions + lenses instead of a summary), run these four checks against every candidate before it's allowed to reach a file. Each is independent — one failure drops the candidate, no averaging across checks.

1. **Citation-real** — every `{source_path, anchor}` cited actually exists, actually resolves inside `brain/`, and actually contains the claim it's cited for. A citation to a note that doesn't say what the question claims it says is a FAIL, not a WARN.
2. **Contradiction-queued-for-human** — if the candidate question or lens contradicts a prior `patterns/*-reflection.md` entry or a human-authored note, it does not get silently resolved. Queue it as an open contradiction in the reflection-delta log for the human to adjudicate. The verifier never picks a side.
3. **Lens-framing** — the synthesis must read as a lens (a way of looking that keeps the question open), not a verdict (a conclusion, a recommendation, a judgment call). If it tells the human what to do or what's true, it fails this check regardless of citation quality.
4. **Privacy** — no content sourced from or referencing `private/`, no person names outside what's already in `brain/people/`, no inferred psychology/values/relationship content (that's paid-tier territory, and paid-tier requires validity disclosures this gate does not grant).

Run this gate **as a distinct critic pass** — a separate invocation from whatever generated the candidates, with no memory of *why* the generator wrote what it wrote. A generator grading its own homework is not verification. If your harness can't spawn a separate pass, at minimum re-read each candidate cold, citation-first, before judging it.

### sip_attestation block schema

Every artifact that survives the gate carries this block at the end of the file:

```yaml
sip_attestation:
  sip_version: 1.1.1
  vertical: second-brain-os
  artifact: reflection | pattern | people-map | note
  generated_by: { agent name, e.g. reflection-engine }
  generated_at: { ISO timestamp }
  verified_by: sbo-verify
  verified_at: { ISO timestamp }
  checks:
    citation_real: pass | fail
    contradiction_queued: pass | fail | n/a
    lens_framing: pass | fail | n/a
    privacy: pass | fail
  verdict: PASS | WARN | FAIL
```

`verdict: FAIL` means the artifact does not get written. `WARN` may ship with the specific warning inline in the file body, never suppressed.

Built on SIP.
