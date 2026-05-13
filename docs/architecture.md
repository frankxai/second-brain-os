# Architecture

> The three edges, two vaults, and agent zones.

## Three edges

| Edge | Direction | Who writes | One rule |
|---|---|---|---|
| **Input edge** | World → `brain/_inbox/` + `_capture.md` | Human (you) + ingestion script | No decisions required. Drop anything. |
| **Distillation** | `_inbox/` → atomic notes; `private/` → `brain/patterns/` | Human, Claude Code assists | Triggered by Sunday Palace Review. You ratify every move. |
| **Output edge** | `brain/notes/` → `brain/people/`, `brain/patterns/`, `brain/_meta/` | Agents (MCP-wired, never editing input edge) | Agents only write to their assigned folders. Never edit human notes. |

## Two vaults

```
~/second-brain/
├── brain/                     # MCP-wired vault — LLM-accessible, publishable
│   ├── _capture.md            #   Karpathy append surface
│   ├── _inbox/                #   imported chats + drops awaiting triage
│   ├── notes/                 #   atomic evergreen notes
│   ├── projects/              #   active outcomes
│   ├── people/                #   AGENT WRITE ZONE (people-map)
│   ├── patterns/              #   AGENT WRITE ZONE (pattern-detector)
│   ├── _meta/                 #   AGENT WRITE ZONE (paid tier)
│   ├── _moc/                  #   Maps of Content
│   ├── _agents/               #   agent prompt contracts
│   └── _archive/              #   cold notes
└── private/                   # air-gapped vault — NO MCP, NO LLM
    ├── chat-history/          #   full raw imports from AI exports
    ├── journal/               #   daily journals
    ├── relationships/         #   sensitive notes
    ├── health/
    ├── finances/
    └── _distill/pending/      #   drafts of anonymized patterns to promote
```

The MCP server's vault root is `~/second-brain/brain/`, NOT `~/second-brain/`. The server cannot resolve any `private/` path.

## Folder ownership

| Zone | Type | Write permission |
|---|---|---|
| `_capture.md`, `_inbox/manual/`, `notes/`, `projects/` | Human-only | You |
| `_inbox/claude-ai/`, `_inbox/chatgpt/` | Ingestion-script-only | `sbo-ingest` |
| `people/`, `patterns/`, `_meta/` | Agent-only | OSS + paid agents via MCP |
| `_moc/` | Mixed | Humans write structure, agents refresh link lists |
| `_archive/` | Mixed | You move, agents read-only |

## Privacy contract

> MCP never has a path to `private/`. The boundary is filesystem, not config.

If a path resolves into `private/` from inside any MCP operation, that's a misconfiguration — escalate. SBO never bridges `private/` ↔ `brain/` automatically. Pattern promotion happens via manual copy-paste only.

## Composition

SBO is a vertical that composes SIP (Starlight Intelligence Protocol). It declines canon. The personal instance can compose live links to:
- SIS (Starlight Intelligence System) — substrate memory + canonical agents
- Library OS — book intelligence pattern + slash commands
- Starlight Chronicle — weekly Palace Review as distillation cadence
- Family Tree — kinship data source for `_meta/family.md`
- ACOS — trajectory data source for pattern-detector

See `composition-guide.md` for the wiring.

## Phase 2 seam

When Anthropic / OpenAI ship MCP-to-MCP memory bridges, SBO will add `handlers/claude_memory_mcp.py` etc. without changing the public `ingest()` API. The JSON-dump path stays as a bridge. See `MEMORY.md` "Open forks".

Built on SIP.
