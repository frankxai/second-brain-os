# pattern-detector agent contract

> Weekly pattern surfacing across recent notes + inbox summaries. Read-only for the human; written by pattern-detector only.

## Trigger

- `/patterns-detect` slash command (manual).
- Weekly via Starlight Chronicle Palace Review.

## Reads

- `brain/notes/**/*.md` (last 30 days by mtime or frontmatter `created`)
- `brain/_inbox/**/*.md` summaries (last 30 days by `imported` frontmatter)

## Writes

- `brain/patterns/{YYYY}-W{ww}.md` (one file per ISO week)

## Per-week file template

```yaml
---
week: {YYYY-Www}
analyzed_at: {ISO timestamp}
note_count: {int}
inbox_count: {int}
agent: pattern-detector
agent_version: 0.1.0
---

# Patterns — Week {ww}, {YYYY}

## Recurring topics

- {topic} (appeared {N} times across {sources})

## Emerging themes

- {short 1-2 sentence description with linked source notes}

## Decision velocity

- Made {N} decisions this week (vs {N} prior week).

## Anti-patterns surfaced

- {if any — repeated mistakes, unkept commitments, contradictions}

## Open loops

- {questions/topics raised but unresolved}
```

## Rules

1. **Show your work.** Every claim links to source notes. No naked assertions.
2. Counts are exact. If you can't count exactly, say so ("approximately").
3. **Never** infer about the human's psychology, relationships, or values — that's paid-tier territory and requires validity disclosures. You surface *topics* and *behaviors as observed in writing*, not interpretations.
4. End with the SIP attestation block.

## Built on SIP

This agent contract composes the SBO substrate.
