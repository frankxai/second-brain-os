# /people-update — Refresh brain/people/ via the people-map agent

Run the people-map agent contract (see `_agents/people-map.md`):
1. Read all files in `brain/_inbox/`, `brain/notes/`, `brain/projects/` from the last 90 days.
2. Extract person mentions (full names, "Jane" + context that resolves to "Jane Doe", etc.).
3. For each person, build/update `brain/people/{slug}.md` per the per-person template.
4. Refresh `brain/_moc/MOC-People.md` with most-mentioned over last 90d.

Rules from the contract:
- Never invent relationship types — write `unknown` if unclear.
- Never include sensitive content. If a mention can't be anonymized without losing meaning, write `[private context]` and skip.
- Deduplicate aggressively but conservatively.

End each per-person file with the SIP attestation block.

Built on SIP.
