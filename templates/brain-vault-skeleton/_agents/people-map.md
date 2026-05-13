# people-map agent contract

> One file per person mentioned anywhere in `brain/`. Read-only for the human; rewrite by people-map only.

## Trigger

- `/people-update` slash command (manual).
- Weekly via Starlight Chronicle Palace Review.

## Reads

- `brain/_inbox/**/*.md` (last 90 days by `imported` frontmatter)
- `brain/notes/**/*.md`
- `brain/projects/**/*.md`

## Writes

- `brain/people/{slug}.md` (one file per person, slug = python-slugify of the name)

## Per-person file template

```yaml
---
name: {Full Name}
slug: {kebab-case}
first_mentioned: {ISO date}
last_mentioned: {ISO date}
mention_count: {int}
relationship: {collaborator | family | friend | vendor | unknown}
agent: people-map
agent_version: 0.1.0
updated_at: {ISO timestamp}
---

# {Full Name}

## Recent context

- {ISO date}: {one-sentence summary} ([source]({relative link to brain note}))

## Topics co-occurring

{comma-separated tags inferred from co-occurring notes}

## Open threads

- {actionable items mentioned alongside this person}
```

## Rules

1. **Never** invent a relationship type. If unclear, write `unknown`.
2. **Never** include sensitive content (relationship details, health, finance). If you find a mention you can't anonymize without losing meaning, write `[private context]` and skip.
3. Deduplicate aggressively. "Jane", "Jane Doe", "Jane D." → same person if context confirms; otherwise keep separate.
4. Sort recent context most-recent-first.
5. Each per-person file ends with a SIP attestation block (auto-emitted).

## Built on SIP

This agent contract composes the SBO substrate. Output carries the SIP attestation block.
