# Cross-AI Portability

> SBO commands work in Claude Code, Claude Desktop, ChatGPT, Cursor, Codex, Gemini CLI — anywhere that reads markdown prompts.

## The canonical command: `/distill-inbox`

This is the most-used SBO command because it replaces `sbo-ingest --mode api` with whatever coding-agent session you already have open. Same contract everywhere; the only difference is how you invoke it.

### Claude Code (canonical)

```
/distill-inbox
```

The full agent body lives at `.claude/commands/distill-inbox.md`. Claude Code loads it automatically.

### Claude Desktop

Open a chat. Paste:

> Read `~/second-brain-os/.claude/commands/distill-inbox.md` and execute it against my vault at `~/second-brain/`. Use the brain root `~/second-brain/brain` and the private root `~/second-brain/private`. Process at most 10 stubs.

### ChatGPT (web, with file upload)

1. Open the command file at `.claude/commands/distill-inbox.md`. Copy the body.
2. In ChatGPT, paste and prepend: *"I'll act as this command. My vault contents are below. Read each stub I paste, then read the linked raw, then produce the structured summary as instructed. Output as raw markdown so I can paste it back. Don't summarize unless I paste the raw conversation."*
3. Paste one stub at a time. Paste its linked raw. ChatGPT produces the new stub body. Copy back to your brain file. Append one line to `private/_distill/audit.jsonl`.

(Slower than Claude Code because there's no filesystem access, but the contract is the same.)

### Cursor

Cursor reads `.cursor/rules/`. Drop the command in:

```bash
mkdir -p .cursor/rules
cp .claude/commands/distill-inbox.md .cursor/rules/distill-inbox.md
```

Then open a Cursor chat in your vault directory and say: *"Run distill-inbox on this vault."*

### Codex (OpenAI)

Codex reads `AGENTS.md`. Either:

```bash
# Symlink so Codex loads the command list
ln -sf .claude/commands AGENTS-COMMANDS
# Or copy
cat .claude/commands/distill-inbox.md >> AGENTS.md
```

Then: *"Run the distill-inbox command from AGENTS.md against my vault."*

### Gemini CLI

```bash
ln -sf AGENTS.md GEMINI.md
gemini --include-file GEMINI.md "Run distill-inbox against $SBO_BRAIN_VAULT_ROOT and $SBO_PRIVATE_VAULT_ROOT. Process up to 10 stubs."
```

### Any other LLM

The command body is plain markdown. Paste it, set `$SBO_BRAIN_VAULT_ROOT` and `$SBO_PRIVATE_VAULT_ROOT` mentally (or in the prompt), and execute. If the LLM doesn't have filesystem access, you paste content in and copy responses out — slower, same contract.

---

## The other SBO commands

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
