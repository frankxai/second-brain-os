# The Reflection Engine

> The 9-stage proactive pipeline that turns SBO from a filing system into a system that reasons over your own corpus while you sleep — and refuses to trust what it finds until it's cited and adversarially checked.

**Status:** v0.3.0. Stages 1-4 and 6-9 already ship as repo commands/agents. Stage 5 (REFLECT) is the new piece this release adds.

---

## The one-line pitch

Retrieval is a commodity. Every second-brain tool can find a note. The unit of value here is **attested, adversarially-verified synthesis you didn't ask for** — an insight that exists because the engine asked a question of your own corpus that you hadn't gotten around to asking yourself, then proved the answer before writing it down.

---

## The pipeline

Nine stages, each grounded in something you can point at on disk. No stage asserts anything that wasn't first retrieved from a real file.

| # | Stage | What it does | Cadence | Owner (repo command/agent) |
|---|---|---|---|---|
| 1 | **CAPTURE** | Raw signal lands untouched — chat exports, daily notes, manual drops. Nothing is interpreted yet. | on-capture | `sbo-ingest` (input edge) writing to `brain/_inbox/` and `_capture.md` |
| 2 | **INGEST** | Dual-write applies the privacy boundary at the door: raw conversation → `private/`, a `status: needs-summary` stub → `brain/_inbox/`. Append-only audit row for every event. | on-capture | `sbo-ingest` three modes (`agent`/`api`/`dry-run`) + `private/_distill/audit.jsonl` |
| 3 | **DISTILL** | Stubs become atomic notes. Reads the linked raw file in `private/` once, classifies by actionability (idea / learning / decision / project log / archive / discard), writes the summary, never overwrites the raw. | on-capture (light) + weekly (deep pass) | `/distill-inbox` |
| 4 | **CONNECT** | Refreshes the discovery layer plain filing misses: link-lists in `_moc/`, per-person cross-refs. | weekly | `/people-update` (people-map agent contract) |
| 5 | **REFLECT** | **The new stage.** Generates the 3-5 most salient questions your corpus raises right now, answers each with cited evidence, frames every answer as a lens rather than a verdict. See spec below. | weekly (+ monthly deep pass) | `/reflect` (reflection-engine agent contract) |
| 6 | **SURFACE** | The right memory shows up at the right moment instead of staying buried: `#review/weekly` items resurface, reflections land in `patterns/`, session-open context loads without re-onboarding. | on-demand (session open) + weekly | `_moc/` refresh + reflection output consumed at next session start |
| 7 | **ACT** | The highest-confidence verified insight becomes a content draft or a next-action proposal. A human gates anything that goes external — this stage never auto-publishes. | weekly | downstream of `/reflect` output, human-triggered |
| 8 | **VERIFY** | The adversarial pass every candidate insight must survive before it's trusted — not a separate cleanup step, a hard gate wired *inside* Reflect and Act. See spec below. | per-insight (inside Reflect/Act) | `/sbo-verify` + the adversarial-review check composed into `/reflect` |
| 9 | **COMPOUND** | Old insights decay, contradictions get flagged instead of silently overwritten, and the reflection-log tells next week's run which error classes to avoid repeating. | weekly (decay) + monthly (promotion review) | reflection-log delta (inside each `patterns/*-reflection.md`) + manual promotion review |

---

## REFLECT — the core spec

This is what separates SBO from a note-filing system. Each weekly run:

1. **Gather.** Pull four layers, in priority order: notes updated/created in the last 30 days; `status: evergreen` notes (your load-bearing claims); highest-link-degree notes (standing structural themes, not just recent ones); and the `_meta/` distilled layer plus prior `patterns/*.md` files, treated as first-class evidence — they already survived one VERIFY pass, so citing them is citing a lens-on-a-lens, and that lineage gets preserved in the citation. All ranking signals are cheap and local (frontmatter recency, link-degree) — no per-note LLM importance call.
2. **Question.** Generate 3-5 questions — never padded to hit a number. Each must fail fast if it's answerable by a single note (that's retrieval, not reflection), must cross-cut at least two of the four gather layers, and must name a tension, a recurrence, or a gap rather than describe something. An anti-convergence check against last week's reflection-log forces at least one question outside whatever theme the prior run flagged as over-mined.
3. **Retrieve evidence per question.** Minimum two citations per question from at least two different layers — one citation is a naked assertion waiting to happen. Every piece of evidence is captured as `{source_path, anchor, retrieved_at}` before any answer gets written, so the claim can be checked against the exact passage, not just the file.
4. **Synthesize a lens.** Structure is Evidence → Lens. Framing discipline enforced at the sentence level: "Evidence suggests…", "The reading is…" — never "X is…" or "this proves…". A lens can name a tension and propose a structural implication; it does not resolve the tension or moralize at you.
5. **Verify before writing.** No candidate reaches `patterns/` until it passes all four VERIFY checks (below). Failing even one drops it from the write set — it isn't softened, it's logged.
6. **Reflect on reflections.** A surviving insight becomes eligible as input to a future run — higher-order reflection over prior reflections, bounded by decay so the tree prunes itself instead of growing forever.

Output: `brain/patterns/{YYYY}-W{ww}-reflection.md` — one file per ISO week, distinct from the plain clustering output the pattern-detector agent already writes to `patterns/{YYYY}-W{ww}.md`.

---

## VERIFY — the trust gate

Every candidate insight passes through a distinct critic pass — not the same generation that wrote it — checking four things:

1. **Citation-real.** Does every `{source_path, anchor}` actually exist, and does the passage at that anchor actually support the specific claim (not just sit topically nearby)? Re-open and confirm, don't trust the first pass.
2. **Not-contradicting.** Does this conflict with an existing vault node? A genuine conflict is never silently resolved either way — it's flagged for human review and excluded from this run's write.
3. **Lens-framed.** No verdict-shaped language, no unbounded identity claims. Anything touching values or self-knowledge inherits a non-removable validity disclosure: it's a reading over what you happened to write down, not a diagnosis.
4. **Privacy-safe.** Nothing from `private/` gets read or surfaced. Nothing exceeds what you already wrote in the cited notes.

Only on passing all four does the insight get written, with a trailing SIP attestation block recording what verified it, when, which citations it carries, and which checks it survived.

**The feedback flywheel.** Each run appends a reflection-log delta to the same output file: how many candidates survived out of how many were drafted, which ones got rejected and the specific reason (e.g. "cited a note that didn't actually support the claim — generator over-reaching on person inferences"), and whether multiple surviving questions independently converged on one theme. The next run loads that delta as context and is required to diversify away from a theme already flagged as over-mined. This is what makes the engine's error rate trend down over time instead of just running on schedule.

---

## Honest differentiation

Five systems get named a lot in this space. Here's what each does well, and the specific structural gap between it and this pipeline — not a rebrand of the same idea.

**vs. Tiago Forte's Building a Second Brain (CODE/PARA).** BASB has the cleanest pipeline mental model (Capture → Organize → Distill → Express) and the best filing heuristic. But it assumes a human runs all four stages by hand — nothing moves unless you touch a note. This pipeline inverts that: agents own Capture and Distill inside a hard write boundary (agents write `patterns/`, `people/`, `_meta/`; never your human-curated notes), and Reflect runs on a schedule whether you show up or not. BASB is a discipline you have to keep. This is a daemon that keeps running.

**vs. Mem0 and generic "AI memory" layers.** Mem0 does fast extract-and-store of conversational facts well — good recall latency, clean SDK. But it's a fact store with no epistemics: it remembers you said X, it never asks whether X is true or what X implies elsewhere in your corpus. It also typically ships your data to a managed cloud. This pipeline is local-first and non-waivable — nothing marked sensitive ever leaves the machine, embeddings are local, and there's no Reflect stage or adversarial verifier in Mem0 at all. The gap is architectural, not a missing feature you could bolt on.

**vs. Zep/Graphiti (temporal knowledge graphs).** Graphiti is genuinely excellent at bi-temporal entity-relationship recall at scale — "what did we know when," across a large graph. But at small-to-medium vault sizes, standing up a full temporal KG is construction for its own sake; you get graph-like value cheaply from embedding-based relevance plus frontmatter link-degree long before a dedicated graph engine earns its keep. The discipline here is knowing when not to build the thing a vendor sells you — restraint as a capability, not a missing integration.

**vs. Stanford's Generative Agents (the reflection paper itself).** This is where the core technique comes from — periodic synthesis of higher-order insight from raw observations, the "reflection tree." Full credit: that's the heart of Stage 5. But Generative Agents reflects to make a simulated character behave plausibly; there's no trust contract, a reflection is accepted purely because the model wrote it. This pipeline wraps the identical mechanism in three things the paper never needed: every reflection cites its source, is framed as a lens rather than a verdict, and must survive an adversarial pass before it's trusted. Same engine, opposite epistemic stance — theirs optimizes for believability, this one for defensibility.

**vs. Letta/MemGPT (sleep-time compute).** Letta has the precise framing right: a separate sleep-time agent reshapes shared memory while the primary agent is idle, at a fraction of the live token cost. But its sleep agent compresses and merges — it doesn't adversarially self-verify or attest anything, and it's a managed runtime. This pipeline's sleep-time agent runs fully local on a scheduled job, and adds the reflection-log feedback loop so the *next* run recalibrates on which insights survived verification last time. Letta gives you cheaper memory. This gives you memory that learns to distrust itself correctly.

**The moat, one sentence:** everyone else either stores or synthesizes — this pipeline synthesizes proactively, locally, and refuses to trust the synthesis until it's cited, lens-framed, and adversarially verified, then logs every rejection so the next run improves. No single competitor combines all four: proactive + sovereign/local + cited-lens + adversarial-verify-with-feedback.

---

## Related docs

- [`docs/architecture.md`](architecture.md) — the two-vault privacy boundary this pipeline writes inside
- [`docs/privacy-model.md`](privacy-model.md) — the threat model Stage 8's privacy check enforces
- [`docs/obsidian-mcp.md`](obsidian-mcp.md) — MCP setup so Claude Code/Desktop can run these commands against your vault
- [`.claude/commands/distill-inbox.md`](../.claude/commands/distill-inbox.md), [`patterns-detect.md`](../.claude/commands/patterns-detect.md), [`people-update.md`](../.claude/commands/people-update.md), [`sbo-verify.md`](../.claude/commands/sbo-verify.md) — the four existing commands this pipeline composes
