# Paid Tier — `@frankx/second-brain-pro`

> 8 depth agents for psychometric inference, business mapping, decision history, and content-engine integration. Available at frankx.ai/second-brain.

**Status:** Phase 3 — not yet shipped. This page describes the planned product. Updates land here as the paid tier ships.

## What's in the OSS template (free, MIT)

- Two-vault skeleton.
- Dual-write ingestion pipeline.
- Two starter agents: `people-map` + `pattern-detector`.
- Privacy hardening scripts.
- Setup scripts.
- All docs.

That's a complete substrate. You can use SBO indefinitely without paying anything.

## What the paid tier adds

8 depth agents. Each agent ships as a markdown contract (under `_agents/`) + a slash command (under `.claude/commands/`) + a subagent definition.

### 1. `big5-inferer` — Big 5 personality

**Cadence:** monthly.
**Reads:** last 90 days of `_inbox/` summaries + `notes/`.
**Writes:** `_meta/psychometrics/big-5.md`.
**Output:** estimated scores on Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism with confidence intervals + supporting note links.

**Validity disclosure (non-removable):** "This is an LLM's inference from your language patterns. It is NOT a clinical assessment. Big 5 has stronger empirical backing than MBTI/16P. Cross-reference with IPIP-NEO (free, validated). Treat as a starting point for self-reflection, not an identity declaration."

### 2. `16p-mapper` — MBTI / 16P

**Cadence:** quarterly.
**Validity disclosure:** "MBTI has weaker empirical backing than Big 5. Type instability across re-tests is well-documented. Use as a vocabulary, not a measurement."

### 3. `stp-mapper` — StrengthsFinder analog

**Cadence:** quarterly.
**Validity disclosure:** "This is a paraphrase, not a CliftonStrengths assessment. Use the official Gallup assessment for the formal version."

### 4. `enneagram-analyzer` — Enneagram typology

**Cadence:** quarterly.
**Validity disclosure:** "Enneagram is a typological framework, not a measurement. Useful as vocabulary."

### 5. `business-map` — businesses & ventures

**Cadence:** monthly.
**Reads:** `projects/`, `_inbox/` business mentions.
**Writes:** `_meta/businesses.md`.
**Output:** per-business cards: status, revenue (if mentioned), stage, dependencies, open decisions.

### 6. `decision-history-miner`

**Cadence:** monthly.
**Reads:** `notes/decisions/`, `_inbox/`.
**Writes:** `_meta/decisions-history.md`.
**Output:** chronological decision log with context, reasoning, outcomes (when observable in later notes).

### 7. `ikigai-extractor`

**Cadence:** quarterly.
**Reads:** `_inbox/` + `notes/learnings/`.
**Writes:** `_meta/values.md`.
**Output:** values + ikigai-quadrant mapping (what you love / what you're good at / what the world needs / what you can be paid for).

### 8. `content-engine-integration`

**Cadence:** weekly.
**Reads:** `_inbox/`, `patterns/`.
**Writes:** feeds FrankX content pipeline at `content/ingest/` (Frank-instance only) or `content/ingest-staging/` (generic install).
**Output:** content seeds — surfaces ideas worth turning into blogs, social posts, or talking-head shorts.

## How the paid tier works (planned)

1. Purchase via Lemon Squeezy at frankx.ai/second-brain.
2. You receive an install token + npm package access.
3. Install: `npx @frankx/second-brain-pro install` (in your brain vault root).
4. The installer drops 8 agent contracts into `_agents/` and 8 slash commands into `.claude/commands/`.
5. You run them via Starlight Chronicle Palace Review or on-demand.

## Pricing (planned)

- **Toolkit** (€197) — agent contracts + setup guide + access to private community.
- **Mastery** (€497) — Toolkit + 90-min setup call with Frank + private Slack.

## Why pay

The OSS template is genuinely complete for substrate-tier use. The paid tier is for users who want the depth layer (psychometrics, business mapping, decision history) without writing the agent contracts themselves. The moat is not the prompts (they're markdown; copy-paste reproduces them) — it's the **curated combination + maintenance + community + Frank's direct support**.

If you're a high-signal practitioner who can write your own agent contracts, the OSS template gives you the architecture; you can extend it freely. If you'd rather buy depth than build it, the paid tier is for you.

Built on SIP.
