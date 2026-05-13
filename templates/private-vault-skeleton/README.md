# private/ — the air-gapped vault

> **No MCP server points here. No LLM has access. By design.**

This is the private side of your Second Brain OS. Sensitive content lives here permanently. Only anonymized patterns leave, via your manual copy-paste into `brain/patterns/`.

## What goes here

- `chat-history/claude-ai/`, `chat-history/chatgpt/` — full raw imports from your AI chat exports. Written by the ingestion script.
- `journal/` — daily journals, morning pages.
- `relationships/` — sensitive relationship notes.
- `health/` — medical, fitness, sleep, mental health.
- `finances/` — money, taxes, investments.
- `_distill/pending/` — drafts of anonymized patterns you're considering promoting to `brain/patterns/`.

## What goes OUT

The `_distill/pending/` folder is the ONE bridge. You write anonymized pattern-extractions here, review them, then **manually copy-paste** into `brain/patterns/` in the other vault. There is no script for this. There is no automation. Manual copy-paste is the boundary.

## What MUST NOT be installed in this vault

- **Local REST API plugin** — never. This exposes the vault on localhost. Setup scripts check.
- **Obsidian Sync** — never. The `.obsidian-no-sync` marker file is the assertion.
- **Smart Connections** — never. This sends content to external embedding APIs.
- **Text Generator / Copilot for Obsidian** — never. These call LLMs with vault content.

## Recommended plugins (private vault only)

- Templater
- Tasks
- Calendar
- Periodic Notes

That's it.

## OS-level hardening

See the SBO repo's `docs/privacy-model.md` for the 6-item OS-level hardening checklist:
1. Windows Search exclusion
2. macOS Spotlight exclusion (`.metadata_never_index` is shipped)
3. Backup tool exclusion (OneDrive / iCloud / Time Machine)
4. Obsidian Sync prohibition (`.obsidian-no-sync` is shipped)
5. Local REST API plugin prohibition
6. Clipboard history caveat

Run `scripts/verify-privacy.{ps1,sh}` to verify.

## Built on SIP

The privacy contract is non-waivable. See SBO repo root `SKILL.md`.
