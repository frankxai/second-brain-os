# Second Brain OS

**A bootable AI second-brain template for Obsidian, with a hard privacy boundary between what your LLM can read and what it can't.**

Ingest your Claude.ai and ChatGPT exports into a dual-vault Obsidian system: a `brain/` vault your coding agent reads and writes, and an air-gapped `private/` vault no LLM ever touches. The compute that summarizes your conversations is the coding-agent session you already pay for — not an extra API bill.

For builders who want a working second brain on day one and the boundary enforced by the filesystem, not by trust.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built on SIP](https://img.shields.io/badge/Built%20on-SIP%20v1.1.1-blue.svg)](https://github.com/frankxai/Starlight-Intelligence-System)
[![Tests](https://github.com/frankxai/second-brain-os/actions/workflows/test.yml/badge.svg)](https://github.com/frankxai/second-brain-os/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

**Status:** v0.1.0 — alpha. Ingestion pipeline is tested and CI-green across three OSes and three Python versions; the vault templates and agents are stable; the paid depth-agent layer is documented but lives off-repo.

---

## The two vaults

The architecture is one decision repeated everywhere: the LLM can reach `brain/`, and it has no path to `private/`.

| Vault | MCP access | Holds | Publishable |
|---|---|---|---|
| `brain/` | Wired (Claude Desktop, Claude Code, …) | Summaries, notes, projects, people, patterns | Yes |
| `private/` | None — no MCP server points here | Raw conversations, journal, health, finances | No, permanently |

Ingestion dual-writes: raw conversation to `private/`, a summary stub to `brain/_inbox/`. The boundary is filesystem, not config. The threat model is in [`docs/privacy-model.md`](docs/privacy-model.md) — read it before ingesting sensitive content.

## How it works

- **Dual-write ingestion** — `sbo-ingest` parses a Claude.ai or ChatGPT export, writes raw to `private/`, stubs to `brain/_inbox/`.
- **Coding-agent distillation** — `/distill-inbox` in any coding-agent session turns stubs into real summaries by reading the raw conversation in `private/`. No extra API spend.
- **Audit log** — every ingest and distill event is appended to `private/_distill/audit.jsonl`. Inspectable, never silent.
- **Two starter agents** — `people-map` (per-person index) and `pattern-detector` (weekly pattern surfacing), shipped as markdown contracts under `_agents/`.
- **Depth layer (off-repo)** — 8 optional depth agents (Big 5, 16P, business-map, decision-history, ikigai, content-engine, …) are documented in [`docs/paid-tier.md`](docs/paid-tier.md). The OSS template stands alone without them.

## Quick start

```bash
git clone https://github.com/frankxai/second-brain-os
cd second-brain-os

# Install the ingestion package
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# Scaffold the vaults
./scripts/setup.sh            # macOS / Linux
pwsh ./scripts/setup.ps1      # Windows
```

Then ingest (default `agent` mode — no API key needed):

```bash
sbo-ingest path/to/conversations.jsonl --brain-root /path/to/brain --private-root /path/to/private
```

Raw lands in `private/`; stubs with `status: needs-summary` land in `brain/_inbox/`. In any coding-agent session, run `/distill-inbox` — the agent walks each stub, reads the linked raw conversation, writes a real summary, sets `status: triage`, and logs to the audit file.

Full walkthrough: [`docs/getting-started.md`](docs/getting-started.md). One catch worth planning around: the Claude.ai data export has a **24-hour delivery window**, so you can wire the system in 30 minutes but can't ingest until the export email arrives.

## The three ingestion modes

`sbo-ingest` has three modes. Default is `agent`.

| Mode | Cost | Compute | When |
|---|---|---|---|
| `agent` *(default)* | $0 extra | Your coding-agent session | You have Claude Code / ChatGPT / Cursor / Codex / Gemini open. Best quality — the agent cross-references your vault. |
| `api` | ~$0.005/convo on Haiku 4.5 | Anthropic API | Batch automation, or no coding-agent session handy. Set `--mode api` or `$ANTHROPIC_API_KEY`. |
| `dry-run` | $0 | None — stubs only | Smoke-test the install and verify the dual-write boundary. |

Smoke-test against the shipped fixture:

```bash
sbo-ingest tests/fixtures/claude-ai-export-sample.jsonl --brain-root /path/to/brain --private-root /path/to/private --mode dry-run
```

Running `/distill-inbox` outside Claude Code — in ChatGPT, Cursor, Codex, or Gemini — is covered in [`docs/cross-ai-portability.md`](docs/cross-ai-portability.md).

## Vault layout

```
~/second-brain/
├── brain/                 # MCP-wired, agent-maintained
│   ├── _capture.md
│   ├── _inbox/{claude-ai,chatgpt,manual}/   # status: needs-summary lives here
│   ├── notes/{ideas,learnings,decisions}/
│   ├── projects/
│   ├── people/            # maintained by people-map
│   ├── patterns/          # pattern-detector output
│   ├── _meta/             # reserved for depth-agent output
│   ├── _moc/              # Maps of Content
│   └── _agents/           # agent prompt contracts
└── private/               # air-gapped — no MCP, no LLM
    ├── chat-history/{claude-ai,chatgpt}/    # raw conversations, UUID-named
    ├── journal/  relationships/  health/  finances/
    └── _distill/
        ├── audit.jsonl    # append-only ingest + distill log
        └── pending/       # private patterns awaiting promotion to brain
```

The `brain/` template ships with a 10-plugin Obsidian config (local-rest-api, dataview, templater, smart-connections, tasks, omnisearch, and more — see `templates/brain-vault-skeleton/.obsidian/community-plugins.json`).

## Docs

| Doc | What |
|---|---|
| [Getting Started](docs/getting-started.md) | 30-min wire walkthrough + Day 1 flow |
| [Ingestion Guide](docs/ingestion-guide.md) | Claude.ai + ChatGPT export workflows + the three modes |
| [Privacy Model](docs/privacy-model.md) | Threat model + privacy-hardening checklist |
| [Architecture](docs/architecture.md) | Three edges, two vaults, agent zones |
| [Composition Guide](docs/composition-guide.md) | Wiring to SIS / Library OS / Chronicle (optional) |
| [Paid Tier](docs/paid-tier.md) | The 8 depth agents |
| [Cross-AI Portability](docs/cross-ai-portability.md) | Running `/distill-inbox` in ChatGPT / Cursor / Codex / Gemini |

## Privacy

> MCP never has a path to `private/`. The boundary is filesystem, not config.

Coding agents that run `/distill-inbox` read `private/` once per conversation — at the moment you invoke the command, with your explicit consent — produce the summary, and never copy raw content into `brain/`. The audit log records every read. Run `scripts/verify-privacy.{sh,ps1}` weekly; CI runs it against the vault skeleton on every push.

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```

37 tests: Claude.ai handler (6), ChatGPT handler (4), summarizer with mocked Anthropic (3), voice check (5), dual-write (7), end-to-end ingest including the three modes and audit log (12). CI runs the full matrix on ubuntu / macos / windows × Python 3.11 / 3.12 / 3.13.

## Composition

Second Brain OS is a vertical that composes the [Starlight Intelligence Protocol](https://github.com/frankxai/Starlight-Intelligence-System) (v1.1.1) and declines its canon. The OSS template stands alone with no external dependencies beyond Python and Obsidian. The personal-instance pattern can symlink live commands and skills from your other substrates — see [`docs/composition-guide.md`](docs/composition-guide.md). The Anthropic API is optional, needed only for `--mode api`.

## License

MIT. See [`LICENSE`](LICENSE).

---

Built by [Frank Riemer](https://frankx.ai). For builders, not consumers.
