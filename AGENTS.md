# Second Brain OS — Agents

> Agents that operate inside an SBO vault. OSS template ships 2; paid tier adds 8.

## OSS starter agents (free)

### people-map
- **Trigger:** `/people-update` slash command (or scheduled weekly via Starlight Chronicle).
- **Reads:** `brain/_inbox/**/*.md`, `brain/notes/**/*.md`, `brain/projects/**/*.md`.
- **Writes:** `brain/people/{slug}.md` (one file per person mentioned).
- **Contract:** see `_agents/people-map.md` in any brain vault.

### pattern-detector
- **Trigger:** `/patterns-detect` slash command (weekly via Chronicle).
- **Reads:** `brain/notes/`, `brain/_inbox/` summaries (last 30 days).
- **Writes:** `brain/patterns/YYYY-Www.md`.
- **Contract:** see `_agents/pattern-detector.md`.

## Paid tier agents (FrankX premium)

Installed via `@frankx/second-brain-pro` npm package on purchase. Not in this OSS template.

1. **big5-inferer** — Big 5 personality inference. Monthly. Writes `_meta/psychometrics/big-5.md`. Ships with mandatory validity disclosure.
2. **16p-mapper** — MBTI/16P typology. Quarterly. Validity disclosure.
3. **stp-mapper** — StrengthsFinder analog. Quarterly. Validity disclosure.
4. **enneagram-analyzer** — Enneagram typology. Quarterly. Validity disclosure.
5. **business-map** — extracts businesses, ventures, projects. Monthly. Writes `_meta/businesses.md`.
6. **decision-history-miner** — pulls decisions from `notes/decisions/` + `_inbox/`. Monthly. Writes `_meta/decisions-history.md`.
7. **ikigai-extractor** — values + ikigai analysis. Quarterly. Writes `_meta/values.md`.
8. **content-engine-integration** — feeds the FrankX content pipeline. Weekly.

## Built on SIP

All agents emit SIP attestation blocks on artifact creation. Validity disclosures are non-removable.
