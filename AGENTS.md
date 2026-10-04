# Second Brain OS — Agents

> This file has two audiences: (1) coding agents contributing to this repo, and (2) the product's own agents that run inside an SBO vault. Read the section relevant to your task.

## Working in this repo (for coding agents)

- **Branch:** `main` is the trunk. Cut a feature branch per change (`agent/<harness>/<scope>` if you're one of several parallel agents — see the estate-wide multi-agent protocol in the parent `starlight/repos/CLAUDE.md`). Never commit directly to `main` from an automated session unless told to.
- **Install:** `python -m venv .venv && source .venv/bin/activate` (or `.venv\Scripts\activate` on Windows), then `pip install -e .`.
- **Test:** `pytest -v` must be green before you open a PR. The suite covers the Claude.ai/ChatGPT handlers, the summarizer (mocked Anthropic), voice check, dual-write, the distill CLI, end-to-end ingest across all three modes, and an adversarial suite (path traversal, NTFS streams, prompt injection, malformed timestamps). CI (`.github/workflows/test.yml`) runs the full matrix on ubuntu/macos/windows x Python 3.11/3.12/3.13.
- **Privacy gate:** if you touch `scripts/`, `templates/`, or `src/sbo_ingestion/dual_write.py`, also run `bash scripts/verify-privacy.sh templates/private-vault-skeleton` (or the `.ps1` on Windows) and confirm it exits 0 with zero failures. Machine-level items (Windows Search exclusion, macOS Time Machine exclusion) report WARN with their manual remediation and do not fail the run. This is the check that the `private/` vault stays air-gapped from MCP.
- **Voice gate:** no AI-slop phrases in docs or generated content (delve, dive into, it's worth noting, certainly, absolutely) — enforced by `src/sbo_ingestion/voice_check.py` and checked in CI.
- **Non-negotiable invariant:** nothing you add may give MCP (or any LLM connector) a path into `private/`. The two-vault boundary is filesystem-level, not config-level — don't "fix" it with a permission flag.
- **Full PR checklist:** see [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Don't touch:** maintainer-local harness state (`.asph-wip/`, `.grok/`, `.agent-harness.json`) is gitignored. If it reappears in `git status`, ignore it rather than staging it.

## What ships in this template

Two OSS starter agents (below) plus a paid tier of 8. This repo is the OSS template only — the paid agents live in the separate `@frankx/second-brain-pro` package. See `docs/paid-tier.md` for the OSS/paid line.

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
