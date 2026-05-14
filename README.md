# Second Brain OS

> A build-in-public AI second-brain template for Obsidian. Two-vault hard privacy separation. Composes the Starlight Intelligence Protocol (SIP).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built on SIP](https://img.shields.io/badge/Built%20on-SIP%20v1.1.1-blue.svg)](https://github.com/frankxai/Starlight-Intelligence-System)
[![Tests](https://github.com/frankxai/second-brain-os/actions/workflows/test.yml/badge.svg)](https://github.com/frankxai/second-brain-os/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

**Status:** v0.1.0 — first OSS release.

---

## What this is

A bootable template that gives you a working AI-augmented two-vault Obsidian system.

- **`brain/` vault** — MCP-wired. Your LLM (Claude Desktop, Claude Code, etc.) reads + writes here. Publishable.
- **`private/` vault** — air-gapped. No MCP server points here. No LLM has access. Sensitive content lives here permanently.
- **Dual-write ingestion** — Claude.ai + ChatGPT exports → raw to `private/`, summary + insights to `brain/_inbox/`.
- **Two starter agents** — `people-map` (per-person index) + `pattern-detector` (weekly pattern surfacing).
- **Paid tier** — 8 depth agents (Big 5, 16P, business-map, decision-history, ikigai, content-engine, …). See `docs/paid-tier.md`.

## 30 minutes to wire. Up to 24 hours to first insight.

The Claude.ai data export has a **24-hour delivery window**. You can wire the entire system in 30 minutes, but you can't ingest until the export email arrives. Plan accordingly.

## Quick start

```bash
git clone https://github.com/frankxai/second-brain-os
cd second-brain-os

# Install the ingestion package
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .

# Run setup
pwsh ./scripts/setup.ps1     # Windows
./scripts/setup.sh            # macOS / Linux
```

See [`docs/getting-started.md`](docs/getting-started.md) for the full walkthrough.

### Smoke-test the install (no API key required)

```bash
sbo-ingest tests/fixtures/claude-ai-export-sample.jsonl \
  --brain-root /path/to/brain \
  --private-root /path/to/private \
  --dry-run
```

`--dry-run` skips summarization. You get the dual-write structure (raw → `private/`, stub-summary → `brain/_inbox/`) so you can verify the boundary holds before spending a single token.

## What you get

```
~/second-brain/
├── brain/                 # 10 community plugins, MCP-wired, agent-maintained zones
│   ├── _capture.md
│   ├── _inbox/{claude-ai,chatgpt,manual}/
│   ├── notes/{ideas,learnings,decisions}/
│   ├── projects/
│   ├── people/            # auto-maintained by people-map agent
│   ├── patterns/          # weekly pattern-detector output
│   ├── _meta/             # paid-tier psychometrics, businesses, decisions-history
│   ├── _moc/              # Maps of Content
│   └── _agents/           # agent prompt contracts
└── private/               # air-gapped, no MCP, no LLM
    ├── chat-history/{claude-ai,chatgpt}/
    ├── journal/
    ├── relationships/
    ├── health/
    ├── finances/
    └── _distill/pending/
```

## Docs

| Doc | What |
|---|---|
| [Getting Started](docs/getting-started.md) | 30-min wire walkthrough + Day 1 flow |
| [Ingestion Guide](docs/ingestion-guide.md) | Claude.ai + ChatGPT export workflows |
| [Privacy Model](docs/privacy-model.md) | Threat model + 6-item OS-hardening checklist |
| [Architecture](docs/architecture.md) | Three edges, two vaults, agent zones |
| [Composition Guide](docs/composition-guide.md) | Wiring to SIS / Library OS / Chronicle (optional) |
| [Paid Tier](docs/paid-tier.md) | 8 depth agents (Big 5, 16P, business-map, …) |
| [Cross-AI Portability](docs/cross-ai-portability.md) | Running SBO commands in ChatGPT / Cursor / Codex / Gemini |

## Privacy

> MCP never has a path to `private/`. The boundary is filesystem, not config.

Read `docs/privacy-model.md` before ingesting sensitive content. Run `scripts/verify-privacy.{ps1,sh}` weekly.

## Composition

SBO is a vertical that composes SIP. It declines canon. The personal-instance pattern symlinks live commands and skills from your other substrates — see `docs/composition-guide.md`. The OSS template stands alone with no external dependencies beyond Python + Obsidian + Anthropic API.

## Testing

```bash
pytest -v
```

28 tests covering: Claude.ai handler (6), ChatGPT handler (4), summarizer with mocked Anthropic (3), voice check (5), dual-write (7), end-to-end ingest (3).

## License

MIT. See [`LICENSE`](LICENSE).

## Built on SIP

Starlight Intelligence Protocol v1.1.1. See [Starlight-Intelligence-System](https://github.com/frankxai/Starlight-Intelligence-System).

---

Built by [Frank Riemer](https://frankx.ai). For builders, not consumers.
