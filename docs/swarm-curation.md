# Swarm Curation

> Optional. A multi-model pattern for maintaining a large vault: cheap audits, mid-tier builds, top-tier verification. Proven in production on a real vault; safe to run standalone.

## Why three models, not one

A single model doing audit + build + verify on the same pass is grading its own homework. It also wastes spend — audit work (find orphans, check frontmatter, count links) doesn't need your most expensive model, and verify work (does every wikilink actually resolve) needs to be adversarial, not agreeable. Splitting the pass by capability tier fixes both problems:

| Tier | Model class | Job | Why this tier |
|---|---|---|---|
| Audit | Haiku-class (fast, cheap) | Find orphans, missing frontmatter, link-graph hubs | High-volume, low-judgment scanning. Don't pay Opus prices to count backlinks. |
| Build | Sonnet-class (balanced) | Write domain MOCs, atomic notes, orphan "## Related" appends | Real synthesis work — needs judgment, not just pattern matching. |
| Verify | Opus-class (deepest reasoning) | Confirm frontmatter correctness, resolve every wikilink, fix broken links | Adversarial pass. Must catch what the builder missed, including the builder's own confident mistakes. |

The rule that makes this work: **verify is a distinct critic, never the generator.** The same discipline as the `/sbo-verify` gate — a model checking its own synthesis will rubber-stamp it. A model checking someone else's synthesis will actually look.

## The pattern

```
1. AUDIT (Haiku tier, N parallel agents)
   - Scan brain/ for orphan notes (zero backlinks, zero forward links)
   - Scan for missing/malformed frontmatter
   - Build a link-graph hub report (which notes have the most in-links — candidates for MOC anchors)
   - Output: an audit report, not edits. No writes at this tier.

2. BUILD (Sonnet tier, driven by the audit report)
   - For each hub cluster: write or refresh a domain MOC
   - For each orphan: either fold it into an existing note or promote it to
     an atomic note with a declarative, LLM-wiki-style title (a title that
     states the claim, not a vague topic label — "X causes Y under Z" beats
     "Notes on X")
   - For each orphan that stays standalone: append a "## Related" section
     linking it back into the graph
   - Output: real file writes, staged for verification

3. VERIFY (Opus tier, distinct critic pass)
   - Confirm every note touched still has correct frontmatter
   - Resolve every wikilink the build tier added or touched — a link that
     points at a note that doesn't exist is a FAIL, not a warning
   - Fix broken links directly, or flag for human if the fix is ambiguous
   - Output: verdict (PASS / WARN / FAIL) + a diff of what it fixed
```

Each tier's output is the next tier's input. Nothing at Build tier gets treated as done until Verify tier has looked at it cold.

## Declarative LLM-wiki titles

A wiki built for LLM retrieval reads differently than one built for human skimming. Prefer titles that assert the claim:

- Weak: `Notes on onboarding friction`
- Strong: `Onboarding friction spikes when the first session has no clear next action`

The strong version is retrievable by an LLM doing semantic search without opening the file, and it forces the note itself to actually contain a claim instead of a grab-bag of loosely related thoughts.

## Receipts (a real production run)

- **12 agents** dispatched across the three tiers
- **7 domain MOCs** generated from the audit's hub report
- **Verdict: PASS** — all touched frontmatter correct, all wikilinks resolved, zero broken links after the fix pass

These are scale stats, not vault contents — the point is the process held up at real volume, not what was in any specific note.

## Copy-paste orchestration outline

Adapt model names to whatever your harness exposes; the tiering is the point, not the exact model string.

```
# Phase 1 — Audit (cheap, parallel, read-only)
dispatch N agents (fast/cheap tier) with:
  task: "Scan {vault}/notes/ and {vault}/_moc/. Report: (a) orphan notes
         with zero backlinks and zero forward links, (b) notes with
         missing or malformed frontmatter, (c) top 10 link-graph hubs
         by in-link count. Output a structured report. Do not edit
         any file."
  scope: read-only, no writes

# Phase 2 — Build (mid tier, driven by Phase 1 output)
for each hub cluster in audit_report.hubs:
  dispatch 1 agent (balanced tier) with:
    task: "Write or refresh {vault}/_moc/MOC-{cluster}.md from these
           linked notes: {cluster.notes}. Declarative section headers.
           Link every note in the cluster."

for each orphan in audit_report.orphans:
  dispatch 1 agent (balanced tier) with:
    task: "Either fold {orphan} into the nearest matching existing note,
           or promote it to notes/{domain}/{slug}.md with a declarative
           title stating its claim, plus a '## Related' section linking
           back to at least 2 notes in the graph."

# Phase 3 — Verify (deepest tier, distinct critic, adversarial)
dispatch 1 agent (deepest-reasoning tier) with:
  task: "Cold review every file touched in Phase 2. For each: confirm
         frontmatter is well-formed, resolve every wikilink (does the
         target file actually exist at that path), and fix any broken
         link you find. You did not write any of these files — review
         them as if handed to you by a stranger. Report verdict PASS /
         WARN / FAIL per file plus a diff of anything you fixed."
  constraint: read+fix only within {vault}/, no access to private/
```

## Where this composes with SBO

- Audit tier maps naturally onto `pattern-detector`'s "recurring topics / hub" scan, just run standalone and cheap.
- Build tier is the same shape as `/distill-inbox`'s triage-then-promote flow, generalized from inbox items to the whole `notes/` tree.
- Verify tier is `/sbo-verify` applied to link integrity instead of (or in addition to) privacy and citation checks — same discipline, different checklist.

None of this requires the paid tier. It's a run pattern, not an agent contract — copy the outline above and point it at your own vault.

Built on SIP.
