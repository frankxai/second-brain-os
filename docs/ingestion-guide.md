# Ingestion Guide

> How to export from Claude.ai and ChatGPT, then run `sbo-ingest`.

## Claude.ai

### Request the export

1. Open Claude.ai in a browser.
2. Click your avatar (lower-left) → **Settings** → **Privacy**.
3. Click **Export data**.
4. Confirm. You'll receive an email with a download link.

**Delivery window:** within 24 hours. Link expires 24h after delivery.

### What you get

A ZIP archive containing `conversations.json` or `conversations.jsonl` (Claude.ai's format has varied — `sbo-ingest` accepts both).

Each line / record:
- `uuid` — conversation ID
- `name` — conversation title
- `created_at`, `updated_at`
- `chat_messages` — array of messages with `uuid`, `text`, `sender` (human|assistant), `created_at`.

### Run ingest

```bash
sbo-ingest path/to/conversations.jsonl
```

## ChatGPT

### Request the export

1. Open ChatGPT in a browser (not the mobile app).
2. Click your name (lower-left) → **Settings** → **Data Controls**.
3. Click **Export data** → **Confirm export**.
4. Email arrives within minutes to hours.

**Note:** Not available on ChatGPT Business / Enterprise plans.

### What you get

A ZIP archive containing:
- `conversations.json` — full message history with `mapping` tree per conversation
- `chat.html` — human-readable browser version (ignore for ingestion)

### Run ingest

```bash
sbo-ingest path/to/conversations.json
```

## What happens during ingest

For each conversation:

1. **Parse** the raw export into a `Conversation` object (handler).
2. **Summarize** via Anthropic API (Haiku, cached system prompt).
3. **Voice-check** the summary against the AI-slop banned-phrase list.
4. **Dual-write:**
   - `private/chat-history/{platform}/YYYY-MM-DD-{conversation-id}.md` (full raw)
   - `brain/_inbox/{platform}/YYYY-MM-DD-{slug}.md` (summary + insights)

The brain file links to the private file by relative path. Your MCP server cannot resolve the link (that's the privacy contract).

## Cost considerations

- Default model: `claude-haiku-4-5-20251001` — cheap.
- Prompt caching reduces re-cost for the system prompt significantly on subsequent calls within ~5 min windows.
- A typical 50-message conversation costs ~$0.005 to summarize.
- 1,000 conversations ≈ $5 first-time, less with cache utilization.

## Selective ingest

To ingest only conversations from the last 30 days, pre-filter the JSONL:

```bash
# Linux/macOS
jq -c 'select(.created_at >= "2026-04-12")' conversations.jsonl > recent.jsonl
sbo-ingest recent.jsonl
```

## Re-ingest behavior

Files are overwritten if you run ingest twice on the same conversation. The brain file's `imported` frontmatter updates; the private file's `imported` updates too. Conversation IDs are stable, so no duplication.

## Phase 2 — when MCP-to-MCP memory bridges exist

When Anthropic / OpenAI ship native memory MCP servers, SBO will add handlers under `src/sbo_ingestion/handlers/claude_memory_mcp.py` etc. The JSON-dump path will still work (as a bridge), but realtime MCP-to-MCP will become the recommended path. The public API of `ingest()` does not change.

Built on SIP.
