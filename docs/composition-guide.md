# Composition Guide

> Optional. How to wire SBO to existing substrates (SIS, Library OS, Starlight Chronicle, ACOS) for the full Frank-style integration. OSS users can skip this — SBO works standalone.

## What "composition" means

SBO is a vertical that composes the SIP substrate. The OSS template ships standalone — it implements the patterns without depending on any other repo. Your personal instance can wire live links to your other substrates and become the integration demonstration.

This guide explains how to do that.

## Pattern: live symlinks

Inside your personal `second-brain/brain/` vault:

```
brain/
└── .claude/
    ├── commands/
    │   ├── library-add.md       → symlink to ~/FrankX/.claude/commands/library-add.md
    │   ├── library-deepen.md    → symlink to ~/FrankX/.claude/commands/library-deepen.md
    │   ├── library-research.md  → symlink to ~/FrankX/.claude/commands/library-research.md
    │   ├── palace.md            → symlink to ~/FrankX/.claude/commands/palace.md
    │   ├── chronicle.md         → symlink to ~/FrankX/.claude/commands/chronicle.md
    │   └── bless.md             → symlink to ~/FrankX/.claude/commands/bless.md
    └── skills/
        ├── library-os/          → symlink to ~/.claude/skills/library-os/
        ├── starlight-chronicle/ → symlink to ~/.claude/skills/starlight-chronicle/
        └── family-tree/         → symlink to ~/.claude/skills/family-tree/
```

### Windows (PowerShell)

```powershell
$brain = "$HOME/second-brain/brain"

# Library OS commands
New-Item -ItemType SymbolicLink -Path "$brain/.claude/commands/library-add.md" -Target "$HOME/FrankX/.claude/commands/library-add.md"
# (repeat for library-deepen, library-research, palace, chronicle, bless)

# Skills
New-Item -ItemType SymbolicLink -Path "$brain/.claude/skills/library-os" -Target "$HOME/.claude/skills/library-os"
# (repeat for starlight-chronicle, family-tree)
```

### macOS / Linux

```bash
brain=~/second-brain/brain

# Library OS commands
ln -s ~/FrankX/.claude/commands/library-add.md "$brain/.claude/commands/library-add.md"
# (etc.)

# Skills
ln -s ~/.claude/skills/library-os "$brain/.claude/skills/library-os"
# (etc.)
```

## Pattern: MCP server federation

Your Claude Desktop config can hold multiple MCP servers. The personal SBO instance composes:

```json
{
  "mcpServers": {
    "sbo-obsidian": {
      "command": "uvx",
      "args": ["mcp-obsidian"],
      "env": { "OBSIDIAN_API_KEY": "...", "OBSIDIAN_HOST": "https://localhost:27124" }
    },
    "memory-bus": {
      "command": "python",
      "args": ["C:/Users/frank/Starlight-Intelligence-System/private/memory-bus/server.py"]
    },
    "starlight-substrate": {
      "command": "node",
      "args": ["C:/Users/frank/Starlight-Intelligence-System/dist/starlight-mcp.js"]
    }
  }
}
```

Now when you operate in your brain vault, Claude has SBO Obsidian access + SIS substrate context + memory bus.

## Pattern: family data source

If you have the Family Tree skill installed, your `brain/_meta/family.md` can source from your canonical kinship data:

```yaml
---
source: ~/FrankX/.frankx/family/
agent: family-tree
---

# Family

(Auto-generated. Sources from .frankx/family/*.md.)
```

The `family-tree` skill keeps this file in sync. See `~/.claude/skills/family-tree/SKILL.md`.

## Pattern: Chronicle as distillation cadence

Starlight Chronicle's weekly Palace Review (`/palace`) is the canonical distillation moment for SBO:

```markdown
## /palace (weekly)

1. Triage `brain/_inbox/` — promote, archive, or delete each item.
2. Run `/people-update` — refresh `brain/people/`.
3. Run `/patterns-detect` — write this week's `brain/patterns/{YYYY}-W{ww}.md`.
4. Run `/sbo-verify` — health check the installation.
5. Manually move private patterns: `private/_distill/pending/` → `brain/patterns/` (copy-paste only).
6. `/bless` any work that reached coherence this week.
```

See `~/.claude/skills/starlight-chronicle/SKILL.md` for the four-cadence practice (weekly, monthly, quarterly, annual).

## Pattern: ACOS hook integration

If you use ACOS (Agentic Creator OS) with ReasoningBank trajectory tracking, the pattern-detector agent can read trajectory data:

```yaml
# brain/_agents/pattern-detector.md (composition-mode)
reads_additional:
  - ~/.claude/projects/*/trajectories/*.jsonl  # ACOS trajectory log
```

The agent then surfaces patterns across your actual Claude Code sessions, not just your notes. See `agentic-jujutsu` skill for the trajectory schema.

## Refresh ritual (weekly)

Live symlinks can break when a target moves. Add to your Sunday Palace Review checklist:

```bash
# Verify all symlinks resolve
find ~/second-brain/brain/.claude -type l -! -exec test -e {} \; -print
```

Any output = a broken symlink. Repair before continuing.

## When to compose vs not

- **Compose:** if you already use SIS / Library OS / Chronicle daily. The integration is meaningful.
- **Don't compose:** if you're trying SBO standalone first. Don't add complexity until SBO alone is delivering value.

Built on SIP.
