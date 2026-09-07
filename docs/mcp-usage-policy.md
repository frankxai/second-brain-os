# MCP Usage Policy — Second Brain OS

> Goal: compound knowledge **without token burn**. MCP is a scalpel, not a vacuum.
> Vault roots: `~/second-brain/brain` (MCP-eligible) · `~/second-brain/private` (never MCP).

**Composes:** `docs/architecture.md`, `docs/privacy-model.md`, `docs/composition-guide.md`.

---

## 1. Zone map (ownership + access)

### Legend

| Code | Meaning |
|------|---------|
| H | Human-only write |
| I | Ingestion-script-only write |
| A | Agent-only write (named agent) |
| M | Mixed (human structure, agent link-refresh) |
| R | Read-only for agents |
| 🚫 | Never reachable by MCP / default LLM tools |

### `brain/` (MCP root = this folder only)

| Path | Zone | Agent write | MCP read | MCP write | Notes |
|------|------|-------------|----------|-----------|-------|
| `_capture.md` | H | ❌ | optional rare | ❌ | Human dump |
| `_inbox/manual/` | H | ❌ | rare triage | ❌ | |
| `_inbox/claude-ai/`, `_inbox/chatgpt/` | I | ❌ | batch on distill | ❌ | Prefer script + session FS |
| `notes/**` | H | ❌ | **targeted** only | ❌ | Never bulk-walk via MCP |
| `projects/**` | H | ❌ | targeted | ❌ | |
| `people/**` | A people-map | ✅ | batch weekly | ✅ people-map only | |
| `patterns/**` | A pattern-detector | ✅ | batch weekly | ✅ pattern-detector only | Multi-week promote only |
| `_meta/psychometrics/**` | A paid | paid | paid | paid | See `docs/paid-tier.md` |
| `_moc/**` | M | link lists | **first hop** | refresh only | Entry graph hubs |
| `_agents/**` | H contracts | ❌ | once / session | ❌ | Load via FS |
| `_archive/**` | H move / R agent | ❌ | ❌ default | ❌ | Cold |
| `CLAUDE.md`, `README.md` | H | ❌ | once | ❌ | |

### `private/` (separate vault — **no MCP server root**)

| Path | Zone | MCP | Notes |
|------|------|-----|-------|
| `journal/**` | H 🚫 | never | Morning pages, raw day |
| `health/**` | H 🚫 | never | Medical, sleep raw, mental health |
| `finances/**` | H 🚫 | never | |
| `relationships/**` | H 🚫 | never | |
| `chat-history/**` | I 🚫 | never | Full exports |
| `_distill/pending/**` | H 🚫 | never | **Only promotion bridge** |
| `_distill/audit.jsonl` | I 🚫 | never | |

**Hard rule:** if any tool path resolves under `~/second-brain/private`, **refuse and escalate**. The boundary is the filesystem, not config honesty.

---

## 2. When to use filesystem vs MCP

### Decision tree (coding agents with local disk)

```
Need content?
├─ Path under private/? → STOP (except an explicit /distill-inbox dual-root session)
├─ Know exact path or small glob under brain/? → filesystem
├─ Weekly agents (people-map / pattern-detector)? → filesystem batch
├─ Need Obsidian vault search index / live REST while the app is open? → MCP (scoped)
├─ Remote client, MCP-only? → MCP, still zone-bound to brain/
└─ Unsure → load _moc/HOME.md via FS; never list the whole vault
```

### Prefer **filesystem** when

1. Your agent already has `~/second-brain/brain` on disk (Claude Code, Cursor, any local CLI).
2. You know the path: a MOC, an agent contract, one note.
3. The run is token-sensitive (cron, overnight) — avoid loading MCP tool schemas into context.
4. Running the people-map or pattern-detector weekly jobs.

### Prefer **MCP** when

1. The client is Obsidian-MCP-only (Claude Desktop without vault filesystem access).
2. You need cross-note **vault search** via the Local REST API while Obsidian is open.
3. You want to append to a live open note without path guessing.
4. Obsidian is the only warm index and a filesystem glob would be wider and noisier.

### Never use MCP for

| Action | Why |
|--------|-----|
| `private/**` | Privacy contract |
| Bulk `list_files_in_vault` every turn | Token + latency burn |
| Writing `notes/`, `projects/`, `_capture.md` | Human-only zones |
| Secrets / env material | Out of vault |
| Automatic private→brain promotion | Manual copy-paste only |
| "Helpful" full reindex per query | MOC → targeted path instead |

---

## 3. MCP policy matrix (anti over-trigger)

### Allowed MCP tools (from `mcp.json` / Local REST)

| Tool | Max cadence | Scope | Default |
|------|-------------|-------|---------|
| `get_file_contents` | as needed | single path under `brain/` | Prefer FS if available |
| `search` | ≤3 per query session | keywords → then FS deep-read | After MOC fail |
| `append_content` | agent zones only | `people/`, `patterns/` | Prefer FS patch |
| `patch_content` | agent zones only | same | Prefer FS |
| `list_files_in_vault` | **≤1 per session** | prefer folder-scoped | Prefer FS glob |

### Session budgets

| Session type | MCP budget | FS ops | Load first (FS) |
|--------------|------------|--------|-----------------|
| Chat Q&A, one topic | 0–2 | 1–5 targeted | `_moc/HOME.md` or a MOC |
| `/people-update` | **0** preferred | batch notes, 90d | `_agents/people-map.md` |
| `/patterns-detect` | **0** preferred | notes + inbox, 30d | `_agents/pattern-detector.md` |
| `/distill-inbox` | **0** | dual-root FS session | `_inbox/` listing |
| Exploratory vault map | **0 list MCP** | MOC only | `_moc/HOME.md` |

### Pre-MCP self-check (all must be yes)

1. Is the filesystem unavailable, **or** is a true Obsidian API feature required?
2. Are writes confined to agent zones?
3. Is the MOC / index already loaded and insufficient?
4. Is the call batched rather than N chatty calls?
5. Is the path under `brain/` only?

### Obsidian process dependency

MCP Local REST only works while Obsidian is open on `brain/`. If it is closed, **do not thrash MCP** — fall back to the filesystem. Prefer HTTP on `127.0.0.1:27123` over self-signed HTTPS on `27124`.

---

## 4. Concrete folder trees

### `brain/` (MCP-eligible)

```
brain/
├── CLAUDE.md
├── README.md
├── _capture.md
├── _agents/
│   ├── people-map.md
│   └── pattern-detector.md
├── _inbox/
│   ├── manual/
│   ├── claude-ai/
│   └── chatgpt/
├── notes/                       # H
│   ├── decisions/
│   ├── ideas/
│   └── learnings/
├── projects/                    # H
├── people/                      # A → {slug}.md
├── patterns/                    # A → {YYYY}-W{ww}.md
├── _meta/
│   └── psychometrics/
├── _moc/
│   ├── HOME.md
│   ├── MOC-People.md
│   ├── MOC-Projects.md
│   └── MOC-Patterns.md
└── _archive/
```

### `private/` (no MCP)

```
private/
├── README.md
├── .obsidian-no-sync
├── .metadata_never_index
├── journal/
├── health/
├── finances/
├── relationships/
├── chat-history/{claude-ai,chatgpt}/
└── _distill/
    ├── pending/                 # promotion staging only
    └── audit.jsonl
```

---

## 5. Note graph

```text
_moc/HOME.md
  ├─ [[MOC-Patterns]] → patterns/*
  ├─ [[MOC-People]]   → people/*
  └─ [[MOC-Projects]] → projects/* (human)

No edges into private/**.
```

### Graph hygiene

1. Frontmatter `type`: `pattern-week`, `person`, `project`, `moc`.
2. Color by `type` or folder in the Obsidian graph view.
3. Never wikilink a private-vault path.

---

## 6. Promotion rules: `private` → `brain`

### Single bridge (non-automated)

```
private/_distill/pending/{draft}.md  --[human copy-paste]-->  brain/patterns/
```

No script, no MCP, no agent write into private for promotion.

### Checklist (all required)

1. **Anonymized** — no intimate names, accounts, diagnoses, sensitive locations.
2. **Pattern-level** — themes and behaviors, not diary excerpts.
3. **Counts without quotes** — "N private journal days" is fine; raw lines only if fully sanitized.
4. **No reverse pointer** into `private/`.
5. **Human ratification** — you move the content; agents may propose draft text in chat for you to paste into `pending/`.
6. **Clipboard cleared** after the paste (see `docs/privacy-model.md`).

### Destinations

| Draft kind | Destination |
|------------|-------------|
| Recurring topic / anti-pattern | `brain/patterns/{YYYY}-W{ww}.md`, or merge into an existing one |
| Collaborator work context | people-map, from **brain** sources only |
| Clinical / financial / intimate | **reject** — stays private |

### Distill vs promotion

| Flow | private access | MCP |
|------|----------------|-----|
| Dual-write ingest | script writes raw private + stub brain | never |
| `/distill-inbox` | coding-agent dual-root **FS** session only | never mounts private |
| Default chat client | treat private as air-gapped | N/A |
| Pattern promotion | human paste only | never |

---

## 7. Interconnection (compound without burn)

```
Capture (H) → Inbox stubs (I) → Distill (FS session) → notes/projects (H)
     │
     └─ people-map / pattern-detector (A, FS-primary)
              ↓
         _moc hubs
              ↓
         durable compound memory
```

**Token rules**

1. Enter via a MOC, not a vault listing.
2. Handoffs carry **paths plus three-line abstracts**, not full note bodies.
3. Use local Dataview / Smart Connections for "related"; use the LLM for synthesis only.
4. Don't duplicate whole notes into session memory — the vault is the store.

---

## 8. Acceptance tests

- [ ] MCP vault root is `~/second-brain/brain` only.
- [ ] No MCP config references `private/`.
- [ ] The agent refuses a private path.
- [ ] Local FS people / patterns jobs run with **0 MCP calls**.
- [ ] Graph: HOME → MOC → notes; no private edges.
- [ ] Promotion happens only via `_distill/pending/` plus a human paste.
- [ ] `list_files_in_vault` is called at most once per exploratory session.

---

## Related

- `docs/privacy-model.md` — threat model
- `docs/architecture.md` — three edges, two vaults
- `docs/composition-guide.md` — optional wiring to other substrates

Built on SIP.
