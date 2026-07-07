# Second Brain OS â€” Agents

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

1. **big5-inferer** â€” Big 5 personality inference. Monthly. Writes `_meta/psychometrics/big-5.md`. Ships with mandatory validity disclosure.
2. **16p-mapper** â€” MBTI/16P typology. Quarterly. Validity disclosure.
3. **stp-mapper** â€” StrengthsFinder analog. Quarterly. Validity disclosure.
4. **enneagram-analyzer** â€” Enneagram typology. Quarterly. Validity disclosure.
5. **business-map** â€” extracts businesses, ventures, projects. Monthly. Writes `_meta/businesses.md`.
6. **decision-history-miner** â€” pulls decisions from `notes/decisions/` + `_inbox/`. Monthly. Writes `_meta/decisions-history.md`.
7. **ikigai-extractor** â€” values + ikigai analysis. Quarterly. Writes `_meta/values.md`.
8. **content-engine-integration** â€” feeds the FrankX content pipeline. Weekly.

## Built on SIP

All agents emit SIP attestation blocks on artifact creation. Validity disclosures are non-removable.

## Design Taste Kernel

For any site, app, landing page, dashboard, visual identity, brand, motion, media, social, or frontend task, apply the shared Design Taste Kernel before handoff:

- C:\Users\frank\starlight\repos\DESIGN_TASTE.md
- C:\Users\frank\starlight\repos\WEB_EXPERIENCE_STANDARD.md
- C:\Users\frank\starlight\repos\MOTION_TASTE_RUBRIC.md
- C:\Users\frank\starlight\repos\MULTI_AGENT_DESIGN_COUNCIL.md
- C:\Users\frank\starlight\repos\VISUAL_QA_GATE.md

When motion, scroll, generated media, GIF/video, or premium polish matters, route through the Motion Design Studio plugin/skills and verify the result visually.

