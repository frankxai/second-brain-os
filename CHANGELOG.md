# Changelog

All notable changes to this project are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Direct ChatGPT export ZIP ingestion, including current numbered
  `conversations-NNN.json` shards in deterministic order without extracting the
  archive.
- Fail-closed ZIP validation for mixed, nested, duplicated, or gapped conversation
  members and duplicate conversation IDs across shards.
- Identity-addressed brain paths, preservation of previously distilled notes on
  re-ingestion, path-safe source IDs, and atomic raw/brain/index writes.
- Private completed-import receipts with selected ZIP members and created/preserved
  conversation counts.

### Changed

- ChatGPT corpora are streamed shard-by-shard and only lightweight index metadata
  is retained after each conversation is dual-written, avoiding whole-corpus RAM
  growth on multi-gigabyte exports.

## [0.3.0] — 2026-07-02

### Added

- **`/reflect`** — the reflection engine, Stage 5 of the (now documented) 9-stage pipeline. Weekly: gather the highest-signal ~100 notes cheaply (frontmatter-only ranking, no per-note LLM call), generate 3-5 questions that cross-cut the corpus, synthesize each as a lens rather than a verdict, run the candidate through the VERIFY gate, write survivors to `brain/patterns/{YYYY}-W{ww}-reflection.md`, and log a reflection-delta so the next run diversifies instead of re-mining the same theme.
- **VERIFY hard gate** — `.claude/commands/sbo-verify.md` gained a reflection mode: four independent checks (citation-real, contradiction-queued-for-human, lens-framing, privacy-safe) run as a distinct critic pass, never the same generation that produced the candidate. A single FAIL drops the candidate; nothing is softened or averaged across checks. Surviving artifacts carry a `sip_attestation` YAML block recording what verified them and when.
- **`memories.json` ingestion** — new `src/sbo_ingestion/handlers/memories.py` parses a Claude.ai export's own pre-distilled cross-conversation memory (tolerant of list / wrapper-dict / flat-dict / string shapes) and writes it to a dedicated `brain/_inbox/{platform}/_memory-export.md`, flagged `weight: high` so downstream agents treat it as durable ground truth rather than one conversation among many. Auto-detected as a sibling of the conversations export, or passed explicitly via `--memories`.
- **Per-conversation summary capture** — `Conversation.summary` (Claude.ai handler) and `dual_write.write_pair` now carry the export's own per-conversation `summary` field straight into brain frontmatter when present, instead of only ever re-deriving one.
- **`_INDEX.md` corpus map** — `dual_write.write_index` regenerates a newest-first `{date, title, summary}` table per platform in `brain/_inbox/{platform}/_INDEX.md` on every ingest run, so an agent can read the whole corpus shape in one file instead of opening every stub.
- **Zero-setup tests** — root-level `conftest.py` inserts `src/` onto `sys.path` so `pytest` collects and runs in a fresh clone without `pip install -e .` first. Locked in by `tests/test_conftest_bootstrap.py`.
- **`docs/reflection-engine.md`** — full spec for the 9-stage pipeline (CAPTURE → INGEST → DISTILL → CONNECT → REFLECT → SURFACE → ACT → VERIFY → COMPOUND), the REFLECT and VERIFY stages in detail, and an honest, non-strawman comparison against BASB, Mem0, Zep/Graphiti, Stanford Generative Agents, and Letta/MemGPT.
- **`docs/obsidian-mcp.md`** — complete MCP wiring guide for Claude Code/Desktop against the Local REST API plugin: the HTTP-vs-HTTPS self-signed-cert gotcha, the insecure-HTTP-off-by-default toggle, working config, curl smoke tests, and a troubleshooting table.
- **`docs/swarm-curation.md`** — optional multi-model audit → build → verify pattern for maintaining a large vault (cheap tier scans, mid tier builds, deepest tier adversarially verifies as a distinct critic). Includes a real production receipt: 12 agents, 7 domain MOCs, verdict PASS, zero broken wikilinks after the fix pass.
- 19 new tests: `test_handlers_memories.py` (6), `test_index.py` (4), `test_conftest_bootstrap.py` (3), plus additions to `test_dual_write.py`, `test_handlers_claude_ai.py`, and `test_ingest.py` covering the new frontmatter fields and `_INDEX.md` output. Suite total: 58, all passing.

### Changed

- `.claude/skills/second-brain-os/SKILL.md` — command list now includes `/reflect`; `/sbo-verify` entry notes it also runs the 4-check reflection gate.
- README rewritten front-to-back: one-line positioning, an honest field-comparison table, a "Proven at scale" receipts block, the pipeline as an ASCII diagram, and a "What's new in v0.3.0" section.

## [0.2.0] — 2026-06-XX

### Added

- **Coding-agent-native ingestion** — `agent` mode is now the default (`--mode agent`). Writes raw + a `status: needs-summary` stub with no Anthropic API call; a coding-agent session (Claude Code, ChatGPT, Cursor, Codex, Gemini CLI) fills the stub later via `/distill-inbox` at zero extra API spend.
- **`/distill-inbox`** — real command that triages `brain/_inbox/` into atomic notes (proposals only; never auto-moves files; never touches `private/`).
- Cross-AI portability guide — running `/distill-inbox` and friends from ChatGPT, Cursor, Codex, and Gemini, not just Claude Code.

### Fixed

- CI privacy checks split into vault-shape checks (safe to run anywhere) vs. machine-level checks (require a real local vault), so the OSS template's CI doesn't false-positive on a repo that has no live vault.

## [0.1.1] — 2026-05-XX

### Added

- `--dry-run` flag — verify the install and the dual-write boundary without burning API credits.
- GitHub Actions test workflow with a dynamic passing/failing badge.
- OSS hygiene: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates.

## [0.1.0] — 2026-05-XX

Initial release.

### Added

- SIP file-contract scaffold; `brain/` and `private/` vault skeleton templates.
- Ingestion package (`sbo_ingestion`) with TDD coverage: Claude.ai JSONL handler, ChatGPT `conversations.json` handler, Anthropic-backed summarizer with prompt caching, voice-check guardrail against AI-slop phrasing, dual-write orchestrator, and the `sbo-ingest` CLI.
- Privacy-hardening verification scripts (`scripts/verify-privacy.{ps1,sh}`).
- Setup scripts for Windows (`setup.ps1`) and Unix (`setup.sh`).
- OSS agent contracts, slash commands, and the substrate `SKILL.md`.
- Full documentation set (7 docs) and the initial README.

[0.3.0]: https://github.com/frankxai/second-brain-os/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/frankxai/second-brain-os/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/frankxai/second-brain-os/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/frankxai/second-brain-os/releases/tag/v0.1.0
