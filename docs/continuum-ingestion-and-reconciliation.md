# Starlight Continuum — ingestion, identity, branch and outcome reconciliation (proposal)

**Status:** REVIEW PROPOSAL; no activated importer/worker, production backfill or merged contract is implied.  
**Date:** 2026-10-25. **Work owner:** [SBO #10](https://github.com/frankxai/second-brain-os/issues/10); governance [Memory #8](https://github.com/frankxai/starlight-memory/issues/8), [SIS #48](https://github.com/frankxai/Starlight-Intelligence-System/issues/48), [SIS #49](https://github.com/frankxai/Starlight-Intelligence-System/issues/49). Portfolio coordination: [agentic-ops #211](https://github.com/frankxai/agentic-ops/issues/211) and local continuity [#181](https://github.com/frankxai/agentic-ops/issues/181).

## Decision and authority

Reuse the existing Second Brain OS two-vault importer for *private source intake*; do not create a new corpus database or separate public memory service. Reuse Starlight Memory for typed promotion, recall and retrieval policy, SIS for the multi-agent context/session handshake, GitHub as versioned engineering/execution truth, and existing Notion/Drive as curated human navigation and cross-assistant projections. Notion and Sheets are **not** the primary append-only event store. Preserve current Registry, PR admission, WIP caps, private vault selection and unmerged gates. A second brain captures; a code PR, CI receipt, live deployment, buyer acceptance and actual payment are distinct and independently verifiable.

Do not assume *all* ChatGPT, Claude, Gemini, Codex or Antigravity consumer chats are accessible. Official exports provide point-in-time coverage; source-authorized runtime hooks capture supported coding-agent sessions; Kura provides bounded visible-view captures with explicit limits. ChatGPT consumer history does not have a universal continuous collection API. External provider memories and embeddings are expendable **projections**. Human-only material remains private; no automatic public or shared promotion.

## Source ownership crosswalk

| Artifact | Owning system | Rule |
| --- | --- | --- |
| Raw export/capture, complete message graph, revision receipts | `second-brain-os/private` | Immutable source facts; no public sync |
| Reviewed note / daily inbox stub | `second-brain-os/brain` | Candidate until admitted |
| Epistemic state, trust, approved reusable claim and recall receipt | `starlight-memory` / SIS memory facade | Typed, permission-scoped |
| Project/goal/repository/venture authority and actual work state | Existing GitHub Registry + owning issue/PR | Never inferred from a chat |
| UI projections, ideas and learning views | Existing Notion backplane; Google Workspace context packet | Links + source-as-of + status, no forked registry |
| Agent harness hooks / handoffs / installed rules | Existing agentic-ops-hub and SIS adapter owners | Conformance tested per client |
| Run/commit/CI/deployment/effect receipts | Owning runtimes and control-plane collectors | Verify externally; not model self-report |

## Normalized object grammar (version 1 proposal)

`source`: `source_id`, `provider`, `account_scope`, `source_kind`, `source_url?`, `export_batch_id?`, `coverage_scope`, `privacy_class`, `captured_at`, `source_created_at?`, `source_updated_at?`.

`message_node`: `message_id`, `source_id`, `parent_message_id?`, `branch_id?`, `role`, `content_parts_ref`, `provider_status?`, `created_at?`, `hash`, `revision`, `tombstone?`. **Never flatten across branches.** Tool/system context may be access-controlled and excluded from public summaries, but its existence/structure is recorded.

`event`: `event_id`, `schema_version`, `tenant_id`, `principal_id`, `privacy_class`, `source_id`, `source_event_id?`, `session_id?`, `run_id?`, `parent_event_id?`, `occurred_at?`, `observed_at`, `event_kind`, `payload_ref`, `payload_sha256`, `idempotency_key`, `correlation_id?`, `policy_version`. Event kinds: session-open, prompt, response, tool-call, tool-result, proposal, edit, handoff, claim, code-change, test, review, deploy, accepted-outcome, session-close, correction, revocation.

`idea`: `idea_id`, `canonical_concept_id`, `source_anchors[]`, `origin_at`, `problem`, `opportunity`, `primary_owner`, `related_brands[]`, `related_goals[]`, `related_ideas[]`, `novelty`, `candidate_state`, `confidence`, `last_reviewed_at`. Ideas are not issues; cross-brand reuse yields one idea with many relationships, not duplicate copies.

`work_item`: `owning_issue_ref`, `goal_ref`, `agent_run_refs[]`, `intended_acceptance`, `actual_state`, `evidence_refs[]`, `reviewer`, `next_gate`. `artifact`: content identity, version, owning repo/Drive/Notion reference, rights, evidence, supersession and reproducible acceptance.

`knowledge_claim`: immutable source anchor, literal assertion, derivation, support and counterevidence, uncertainty, temporal validity, author/reviewer, epistemic state. `decision`: exact approval principal/time, option space, supersedes, affected objects, rollback/revision link. Never convert a prompt, generated statement or calendar plan into a ratified decision.

## Identity, ingest idempotency and collisions

1. Each imported ZIP/capture gets `import_batch_id` and a manifest: provider/account, source hash, size, inspected filenames/shards, source counts, capture window, revision and cursor. Store in private ingestion receipts; don't let ZIP filename determine message identity.
2. **Exact identity first:** provider + account scope + canonical provider conversation ID + message/node ID + revision or branch. If missing native IDs, use a scoped synthetic ID of normalized payload bytes plus capture provenance; mark provisional and never silently merge it with a claimed provider ID.
3. **Content-hash repeat:** same native ID and same source hash is no-op. Same ID and new hash is a new revision with preserved prior bytes and review_pending. Distinct native IDs but similar text are `possible_duplicate` candidates, not auto-deleted or silently merged.
4. URL/source-ID joins between Kura and exports require strict platform, account scope, source URL, ID and branch-coverage comparison. A captured view may be a subset of full export; preserve both. When an export contradicts a summarized browser view, surface a conflict, not overwrite human edits.
5. Preserve all ChatGPT `mapping` edges, `current_node` and alternative branches. Build each readable transcript as a **derived, branch-scoped projection** with selected path and source anchor. Do not mix mutually exclusive assistant continuations. Honor message edits, tool-call causality and missing/unknown timestamps.
6. Semantic equivalence is curation, not ingestion. Keep `duplicate_of`, `similar_to`, `supersedes`, `part_of`, `contradicts` relations separately. One concept can span products; distinct requirements remain distinct even when vocabulary overlaps.
7. Fail closed for cross-tenant identity collisions, malformed receipts, malformed vault notes, escaping symlinks and incompatible schema versions. Crash recovery replays idempotently from the last committed receipt with per-batch accounting.
8. Deletion/revocation propagates tombstones to permitted derivative caches/embeddings/provider shadows. Retain legally necessary audit metadata without retaining user-deleted contents contrary to the effective policy.
9. **No auto-archive/delete** of Drive/Notion documents, even with high semantic overlap. Produce a collision review with canonical candidate, exclusive facts, conflicting claims, proposed supersession and human approval.

## Session-close and prompt/output preservation

Record each supported harness session's explicit user prompt, assistant prompt/response reference, local changes, tool side effects, artifact hashes, PR and branch, objective, conclusion, blockers and completion status. Agent declarations of “done” remain `agent_reported`; CI, deployment, acceptance and payment are separate externally sourced receipts. For ordinary consumer chat, capture only what exports/opt-in capture expose; use end-of-session structured receipt when a tool is unable to export raw activity. Never claim background capture of hidden chat windows or inaccessible providers.

At session start fetch **bounded, permission-scoped** project context and the last accepted work receipt. At session close emit a proposed continuation patch that the owning gate may accept. Unsupported hook clients get a documented manual/export adapter, not a fake “connected” status. Supported platform interfaces, capture consent, scopes and hook semantics must be checked against current official documentation before implementation.

## Daily / weekly operations

**Daily, incrementally:** ingest new authorized sources once; checkpoint; produce candidate ideas and run deltas; route links to existing owning project queues; consolidate repeated conversation concepts; notify only on failed proof gates, consequential conflicts, overdue commitments, runaway spend, regression or decisions that cannot be delegated. Every run produces a machine receipt and a reviewer-readable delta.

**Weekly:** official export reconciliation, chat coverage manifest, dedup/conflict board, source freshness, cost per accepted outcome, abandoned and superseded ideas, a curated 1-page founder review, lesson/pattern extraction and 1-3 approved next bets. Sunday personal reflection remains private and should not be misclassified as work.

## Founder cockpit: minimum views

- **Now:** decisions requiring approval, broken production workflows, urgent customer outcomes, high-cost runs.
- **Atlas:** portfolio > ventures/brands > goals > capabilities > ideas > owning work > evidence.
- **Activity:** agent/team/client session streams and proof stages; unreviewed versus ratified counts.
- **Harvest:** novel ideas, cross-brand reuse, duplicate candidates, superseded proposals and lessons.
- **Coverage:** per-provider last cursor/export window, accessible vs unavailable, ingestion failures, dedup rates, accepted events and lag.
- **Quality:** accepted outcome rate, rollback/reopen rate, human review time, evidence completeness, benefit/cost; avoid counting agent messages or merged PRs as customer value.

## Required conformance fixtures (synthetic only)

- A ChatGPT fork with two competing assistant branches; selected-path projection returns one branch without discarding either.
- Edited prompt and same-message-ID differing content produce a new source revision, not a duplicate concept.
- Sharded ZIP twice; and duplicate Kura visible-view capture of exported conversation: exactly one canonical identity, separate source-view coverage, zero duplicate promoted notes.
- Two distinct user prompts with similar wording and different desired outcomes remain distinct source events; curation may group, never erase.
- Existing human-edited Obsidian note remains byte-identical after re-import; changes issue a `refresh_pending` receipt.
- Killed importer at each phase resumes with exactly one committed event/effect, preserved original bytes and no skipped shard.
- Consent withdrawal propagates source tombstone; denied tenant/brand access and injected instructions never become agent policy.
- Code agent claims success but CI fails; state remains `failed_verification`. PR merged but deployment unverified remains `merged_not_live`.
- One cross-brand idea maps to one `canonical_concept_id` and two explicit brand relations with distinct approval queues.
- Export/capture coverage report clearly identifies unexported/inaccessible accounts; no false `100%` progress.

## Readiness gates / first delivery

**Phase A** inventory all existing vault roots and hashes, repo PRs, indexes, import logs, source adapters and queue owners **read-only**. Do not choose a vault or migrate user data without an explicit verified target and backup/restore test. Existing SBO #10 records multiple possible vaults and an unmade activation decision.

**Phase B** implement tree-faithful ChatGPT parser + immutable raw revisions + coverage report + deterministic dedup receipts in SBO. Inspect current `src/sbo_ingestion/handlers/chatgpt.py`: `_walk_mapping` currently sorts all nodes by `create_time` and `_parse_conversation` retains only human/assistant text; this does not preserve branches or system/tool structure. Add backward-compatible interfaces or a versioned migration with consumer tests. Never silently change established vault identities.

**Phase C** implement thin hook/capture adapters and deterministic resumable session-close behavior through existing owners. Add accepted outcome joins from GitHub / CI / Vercel through source-bound connectors; any completion status remains unknown until independently tested.

**Phase D** pilot one real user-authorized ten-conversation export and one agent-session resume against a sandboxed/private vault; prove ingest → candidate → human ratification → retrieval → correction → revocation → restore. Keep real exports out of CI/logs/public PRs.

**Phase E** promote to an active daily pipeline only when production identity, consent, permissions, failure recovery, cost ceiling, telemetry and human-approval boundaries are tested. Rollback disables ingest and derived projections while preserving recoverable private source receipts as policy permits.

### Explicit stop conditions

No new repo or database before checking canonical owners. No destructive merge, archive or vault migration. No external SaaS sent private raw transcripts by default. No unreviewed new schedule/always-on agent fleet. No merge to main without existing PR gates and independent reviewer. End the first coding-agent run with exact audited state, tests, blockers and a bounded follow-up—not unverified “full rollout”.

## Context references

- [SBO capture/replay SOP](./automation.md) (existing; no new watcher installed)
- [Existing continuity strategy issue](https://github.com/frankxai/agentic-ops/issues/211)
- [Source governance epic](https://github.com/frankxai/Starlight-Intelligence-System/issues/48)
- [Memory identity/admission issue](https://github.com/frankxai/starlight-memory/issues/8)
- [Cross-harness actual activation](https://github.com/frankxai/agentic-ops/issues/181)
