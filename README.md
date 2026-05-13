# Second Brain OS

> A build-in-public AI second-brain template for Obsidian. Two-vault hard privacy separation. Composes SIP (Starlight Intelligence Protocol).

**Status:** v0.1.0 — pre-release. Not yet pushed to public GitHub.

## What this is

A bootable template that gives you a working AI-augmented two-vault Obsidian system in 30 minutes (with a 24h Claude.ai export delivery window before first ingestion).

- `brain/` vault — MCP-wired, LLM-accessible, publishable.
- `private/` vault — air-gapped, no MCP, no LLM. Sensitive content lives here permanently; only anonymized patterns move out via your manual copy-paste.
- Dual-write ingestion: Claude.ai + ChatGPT exports → raw to `private/`, summary + insights to `brain/_inbox/`.
- Two starter agents (people-map, pattern-detector). Paid tier adds 8 depth agents.

## 30 min to wire. Up to 24h to first insight.

The Claude.ai data export has a 24-hour delivery window. You can't ingest before the email arrives. Plan accordingly.

## Quick start

```bash
git clone https://github.com/frankxai/second-brain-os
cd second-brain-os
# Windows
pwsh ./scripts/setup.ps1
# macOS/Linux
./scripts/setup.sh
```

See `docs/getting-started.md` for the full walkthrough.

## Docs

- [Getting Started](docs/getting-started.md) — 30-min wire walkthrough.
- [Privacy Model](docs/privacy-model.md) — threat model + 6-item hardening checklist.
- [Ingestion Guide](docs/ingestion-guide.md) — exporting from Claude.ai + ChatGPT.
- [Composition Guide](docs/composition-guide.md) — wiring to SIS / Library OS / Starlight Chronicle (optional).
- [Cross-AI Portability](docs/cross-ai-portability.md) — running SBO commands in ChatGPT / Cursor / Codex / Gemini.
- [Architecture](docs/architecture.md) — the three edges, two vaults, agent zones.
- [Paid Tier](docs/paid-tier.md) — what the 8 depth agents do.

## License

MIT. See `LICENSE`.

## Built on SIP

Starlight Intelligence Protocol v1.1.1. See [Starlight-Intelligence-System](https://github.com/frankxai/Starlight-Intelligence-System).

---

Built by [Frank Riemer](https://frankx.ai). Made for builders, not consumers.
