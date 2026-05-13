# Cross-AI Portability

> SBO commands work in Claude Code, Claude Desktop, ChatGPT, Cursor, Codex, Gemini CLI — anywhere that reads markdown prompts.

## The principle

SBO slash commands (`.claude/commands/*.md`) are plain-text markdown prompts. The `.claude/` prefix is Claude-specific naming, but the content is portable.

## Using SBO commands in other AIs

### ChatGPT (web)

1. Open `.claude/commands/people-update.md` in any text editor.
2. Copy the contents.
3. Paste into ChatGPT, prepending: "Run this command against my vault contents (I'll provide context below):"
4. Paste 5–10 representative vault files.
5. ChatGPT executes the people-map agent contract.

### Cursor

Cursor supports markdown rule files. Drop SBO commands into `.cursor/rules/`:

```bash
mkdir -p .cursor/rules
cp .claude/commands/*.md .cursor/rules/
```

Then Cursor will load them as context for relevant files.

### Codex (OpenAI)

Codex reads `AGENTS.md` files. SBO's `AGENTS.md` at the repo root is Codex-readable. For per-command behavior:

```bash
# Append SBO commands to AGENTS.md
cat .claude/commands/people-update.md >> AGENTS.md
```

### Gemini CLI

Gemini CLI reads `GEMINI.md`. Symlink:

```bash
ln -s AGENTS.md GEMINI.md
```

Or copy `.claude/commands/*.md` content into `GEMINI.md`.

### OpenCode

OpenCode reads `AGENTS.md`. Same as Codex.

## What stays Claude-specific

- The `Skill` tool invocation pattern (Claude Code only).
- MCP server wiring (Claude Desktop + Claude Code primarily; others have varying MCP support).
- The specific phrasing "Built on SIP" attestation is Claude-friendly but works in any LLM that respects prompt instructions.

## The bigger pattern

SBO commands ARE prompts. They follow the [Library OS portability convention](https://github.com/frankxai/library-os/blob/main/docs/cross-ai-guide.md). If a slash command isn't portable, it's a bug — file an issue.

Built on SIP.
