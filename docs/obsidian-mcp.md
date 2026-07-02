# Obsidian MCP Setup

> Complete setup for wiring Claude Code / Claude Desktop to your `brain/` vault via the Local REST API plugin. This is the wiring behind every command in this repo (`/distill-inbox`, `/patterns-detect`, `/people-update`, `/sbo-verify`, `/reflect`). Read this before you file a bug — the failure modes below cost hours the first time.

---

## What you're wiring

The **Local REST API** community plugin turns your Obsidian vault into an HTTP server. An MCP server (`obsidian-local-rest-api` or equivalent) talks to that HTTP server and exposes vault operations (read, write, search, patch, append) as MCP tools your coding agent can call.

Two things have to both be true for this to work: the plugin has to be running inside Obsidian, and your MCP client has to hit the right endpoint with the right token.

---

## Setup steps

### 1. Install the plugin

Inside Obsidian: Settings → Community plugins → Browse → search "Local REST API" → Install → Enable.

### 2. Copy the API key

Settings → Local REST API (in the left plugin list) → copy the **API Key** shown there. You'll paste this into your MCP config as a bearer token. Treat it like a password — it grants read/write to your vault.

### 3. The gotcha that costs hours: HTTP vs HTTPS

The plugin exposes **two** ports:

- `27123` — plain HTTP
- `27124` — HTTPS with a **self-signed certificate**

**Use `http://127.0.0.1:27123/mcp/`. Do not use the HTTPS 27124 endpoint.**

Claude's native MCP client validates TLS certificates and rejects self-signed ones outright — silently, with no useful error surfaced to you. You'll see the MCP server listed as connected in some clients but every tool call will fail or hang. If you're debugging "MCP configured correctly but nothing works," this is very likely why. Point at 27123 over plain HTTP on localhost and move on.

### 4. The second gotcha: insecure HTTP is OFF by default

Plain HTTP (port 27123) is **disabled by default** in the plugin. The setting is called something like "Enable Non-encrypted (HTTP) Server" and it defaults to **off** — meaning port 27123 doesn't actually respond until you flip it on.

Go to Settings → Local REST API and enable the non-encrypted/insecure HTTP server explicitly. This is a deliberate default from the plugin author (HTTPS-by-default is the safer posture for a general audience) but it means the endpoint this doc tells you to use won't work until you toggle it.

### 5. Obsidian must be running

The REST API only exists while the Obsidian app process is running with the vault open — it's not a background daemon, it's a plugin inside the app. If Obsidian is closed, every MCP tool call fails with a connection error indistinguishable from a config problem. Check "is Obsidian open" before you check anything else.

### 6. Restart your MCP client after any config change

Claude Code and Claude Desktop both cache the MCP server list at startup. If you edit the config (new token, changed port, added the server for the first time), restart the client. A config edit with no restart looks identical to a broken config.

---

## Working config

For Claude Code, add to your MCP config (`.claude/settings.json`-adjacent MCP config, or wherever you register servers — check `claude mcp list` to confirm where yours lives):

```json
{
  "mcpServers": {
    "obsidian": {
      "type": "http",
      "url": "http://127.0.0.1:27123/mcp/",
      "headers": {
        "Authorization": "Bearer <your-api-key-from-step-2>"
      }
    }
  }
}
```

For Claude Desktop, the equivalent block goes in `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows: `%APPDATA%\Claude\claude_desktop_config.json`), under the same `mcpServers` key.

Point the vault root at your `brain/` directory specifically, **not** the parent directory that also contains `private/`. The MCP server's filesystem operations cannot escape whatever root it's configured with — that's the entire privacy boundary this repo depends on. See [`docs/privacy-model.md`](privacy-model.md).

---

## Test it with curl

Before touching an MCP client at all, confirm the plugin itself is answering:

```bash
curl -s http://127.0.0.1:27123/ \
  -H "Authorization: Bearer <your-api-key>"
```

A healthy response returns JSON describing the server (name, version, an "OK"-shaped status). Anything else — connection refused, a TLS error, an empty response — means the problem is the plugin/port, not your MCP client, and you should go back to steps 3-5 before debugging further up the stack.

To confirm vault access specifically:

```bash
curl -s http://127.0.0.1:27123/vault/ \
  -H "Authorization: Bearer <your-api-key>"
```

This should list files at the vault root. If it lists files from a directory you didn't expect (e.g. anything under `private/`), stop and fix your vault root config immediately — that's a privacy boundary breach, not a cosmetic bug.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| MCP server shows "connected" but every tool call errors or times out | Pointed at `https://127.0.0.1:27124/` — client rejects the plugin's self-signed cert | Switch to `http://127.0.0.1:27123/mcp/` |
| Connection refused on port 27123 | Insecure HTTP server toggle is off (the default) | Settings → Local REST API → enable the non-encrypted/HTTP server |
| Connection refused on both ports | Obsidian isn't running, or the vault isn't open | Open Obsidian with the target vault loaded |
| 401 / Unauthorized on every request | Wrong or stale API key in the `Authorization` header | Re-copy the key from Settings → Local REST API; confirm no extra whitespace |
| Config looks right, still broken | Client hasn't picked up the change | Fully restart Claude Code / Claude Desktop, don't just reopen a window |
| MCP tools list vault files outside `brain/` | Vault root points at the parent dir instead of `brain/` specifically | Fix the vault root in Obsidian's Local REST API settings and/or your MCP config |
| Works today, broken tomorrow with no config change | Windows/macOS rebooted and Obsidian didn't reopen, or the vault switched | Confirm Obsidian is running with the correct vault before re-debugging config |
| curl to `/vault/` works, but Claude's MCP tools still fail | Client-side MCP registration issue, not the plugin | Re-check the `mcpServers` block syntax and restart the client |

---

## Related docs

- [`docs/privacy-model.md`](privacy-model.md) — why the vault root boundary is load-bearing, not optional
- [`docs/architecture.md`](architecture.md) — the two-vault layout this MCP server points into
- [`docs/reflection-engine.md`](reflection-engine.md) — the pipeline that runs on top of this wiring
