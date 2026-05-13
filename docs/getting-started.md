# Getting Started with Second Brain OS

> 30 minutes to wire. Up to 24 hours to first insight (Claude.ai export delivery window).

## Prerequisites

- **Obsidian** ≥ 1.6.0 — https://obsidian.md
- **Python** ≥ 3.11 with `pip` or `uv`
- **Claude Desktop** OR **Claude Code CLI** (for MCP)
- **Anthropic API key** — https://console.anthropic.com
- **Optional but recommended:** A password manager for the Local REST API key.

## Day 0 — wire it up (30 min)

### 1. Clone the repo

```bash
git clone https://github.com/frankxai/second-brain-os
cd second-brain-os
```

### 2. Install the Python ingestion package

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -e .
```

### 3. Run setup

```bash
# Windows:
pwsh ./scripts/setup.ps1

# macOS/Linux:
./scripts/setup.sh
```

This creates `~/second-brain/brain/` and `~/second-brain/private/` from the skeletons, runs privacy verification, and prints a Claude Desktop config snippet.

### 4. Open Obsidian and add the brain vault

- File → Open another vault → Open folder as vault → select `~/second-brain/brain/`.
- When Obsidian asks about installing the community plugins listed in the vault, accept.

The 10 community plugins to install:
- Local REST API (the MCP backbone)
- Templater
- Dataview
- QuickAdd
- Smart Connections
- Tasks
- Periodic Notes
- Calendar
- Excalidraw
- Omnisearch

### 5. Generate the Local REST API key

Settings → Community plugins → Local REST API → Settings → copy the API key.

### 6. Wire the MCP server

Add the snippet from `setup.{ps1,sh}` output to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json` on Linux, `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows).

Restart Claude Desktop. The `sbo-obsidian` MCP server should appear in your MCP list.

### 7. Add the private vault as a SEPARATE Obsidian vault

- File → Open another vault → Open folder as vault → select `~/second-brain/private/`.
- **DO NOT install Local REST API in this vault.** SBO's privacy contract depends on it.
- **DO NOT enable Obsidian Sync in this vault.** The `.obsidian-no-sync` marker is the assertion.

### 8. Request your AI chat exports

- **Claude.ai:** Settings → Privacy → Export data. Email arrives within 24h with a download link (24h expiry).
- **ChatGPT:** Settings → Data Controls → Export. Email arrives within minutes to hours.

## Day 1 — ingest (5 min once exports arrive)

```bash
export SBO_BRAIN_VAULT_ROOT=~/second-brain/brain
export SBO_PRIVATE_VAULT_ROOT=~/second-brain/private
export ANTHROPIC_API_KEY=<your-key>

# Claude.ai (JSONL)
sbo-ingest ~/Downloads/conversations.jsonl

# ChatGPT (JSON)
sbo-ingest ~/Downloads/conversations.json
```

Each conversation becomes two files:
- `private/chat-history/{platform}/YYYY-MM-DD-{id}.md` — full raw transcript
- `brain/_inbox/{platform}/YYYY-MM-DD-{slug}.md` — summary + insights + suggested destinations

## Day 1+ — daily flow

- **Anytime:** drop into `brain/_capture.md` whenever a thought passes through.
- **Sunday:** run `/palace` (Starlight Chronicle) → triage `_inbox/` → promote to atomic notes → `/people-update` and `/patterns-detect`.
- **Sensitive content:** copy raw text into the right `private/` folder. Distill anonymized patterns into `private/_distill/pending/`, then manually copy to `brain/patterns/` when ready.

## Troubleshooting

See `docs/privacy-model.md` and `docs/ingestion-guide.md`.

## Next steps

- `docs/composition-guide.md` — wiring SBO to your SIS / Library OS / Chronicle installations (optional).
- `docs/paid-tier.md` — adding the 8 depth agents (Big 5, 16P, business-map, etc.).
- `docs/cross-ai-portability.md` — running SBO commands in ChatGPT / Cursor / Codex / Gemini.

Built on SIP.
