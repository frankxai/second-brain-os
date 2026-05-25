---
name: sbo-ingest
description: >
  Ingest Claude.ai or ChatGPT conversation exports into a Second Brain OS vault. 
  Triggers on: "ingest my chats", "import conversations", "process my Claude export", 
  "add my ChatGPT history", "sbo-ingest", or when the user provides a .jsonl or 
  conversations.json file and has a second-brain vault set up.
---

# SBO Chat Ingestion

Process Claude.ai JSONL exports or ChatGPT conversations.json exports into your second brain vault.

## What I need

1. **The export file** — ask the user to provide the path to their export file, or drag it in
2. **Vault roots** — the path to their `brain/` and `private/` vault directories

Check for these env vars first (may already be set):
- `SBO_BRAIN_VAULT_ROOT` 
- `SBO_PRIVATE_VAULT_ROOT`
- `ANTHROPIC_API_KEY`

## If sbo-ingest CLI is available

Run:
```bash
sbo-ingest /path/to/export-file \
  --brain-root "$SBO_BRAIN_VAULT_ROOT" \
  --private-root "$SBO_PRIVATE_VAULT_ROOT"
```

Default mode is `agent` (no API spend) — writes stubs with `status: needs-summary` to `brain/_inbox/`. Run `/sbo-distill` afterward to fill them.

For immediate summarization:
```bash
sbo-ingest /path/to/export-file \
  --brain-root "$SBO_BRAIN_VAULT_ROOT" \
  --private-root "$SBO_PRIVATE_VAULT_ROOT" \
  --mode api \
  --api-key "$ANTHROPIC_API_KEY"
```

## If CLI is not available (pure Cowork)

Use your file Read tool to parse the export file directly:

**For Claude.ai JSONL** (one JSON object per line):
- Each object has: `uuid`, `name`, `created_at`, `updated_at`, `chat_messages` (array)
- Each message: `uuid`, `text`, `sender` (human/assistant), `created_at`

**For ChatGPT conversations.json** (JSON array):
- Each object has: `id`, `title`, `create_time`, `mapping` (message tree)
- Walk `mapping` values, sort by `create_time`, filter to role=user/assistant

For each conversation:
1. Write raw markdown to `private/chat-history/{platform}/YYYY-MM-DD-{uuid}.md`
2. Write summary stub to `brain/_inbox/{platform}/YYYY-MM-DD-{slug}.md` with frontmatter:
   ```yaml
   ---
   title: [conversation title]
   date: [YYYY-MM-DD]
   platform: [claude-ai|chatgpt]
   status: needs-summary
   tags: [draft, needs-triage]
   private_file: private/chat-history/...
   ---
   ```

## Cost note

- Agent mode (default): zero API spend. Stubs filled later via `/sbo-distill`.
- API mode: ~$0.005/conversation (Haiku). 1,000 conversations ≈ $5.

## After ingestion

Run `/sbo-distill` to fill stubs with real atomic notes.
Stubs land in `brain/_inbox/` and appear in Obsidian immediately.

Built on SIP.
