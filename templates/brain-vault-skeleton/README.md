# brain/ — the MCP-wired vault

> This is the LLM-accessible side of your Second Brain OS. The `private/` vault is its air-gapped sibling.

## Setup

This folder is a vault skeleton. To turn it into your live vault:

1. Copy it to your chosen location (e.g., `~/second-brain/brain/`).
2. Open it in Obsidian (Open another vault → Open folder as vault).
3. Install the 10 community plugins listed in `.obsidian/community-plugins.json` (Obsidian will prompt).
4. Install Local REST API plugin and generate an API key.
5. Configure your MCP server (Claude Desktop or Claude Code) to point at THIS folder.

## Folder ownership

See `CLAUDE.md` in this folder for the full contract.

## Daily flow

- Drop into `_capture.md` whenever something passes through your head.
- Ingestion script writes Claude.ai + ChatGPT summaries into `_inbox/{platform}/`.
- Sunday: run `/palace` → triage inbox → write atomic notes in `notes/` → run `/people-update` and `/patterns-detect`.

## Built on SIP

See the SBO repo root for the substrate skill and the SIP attestation contract.
