# MCP Usage Policy — Second Brain OS

> Goal: compound knowledge **without token burn**. MCP is a scalpel, not a vacuum.  
> Live vaults: `C:/Users/frank/second-brain/brain` (MCP-eligible) · `.../private` (never MCP).  
> Time plane SSOT: `docs/time-and-week-os.md` (product) + `~/.starlight/time-os/` (runtime ledger).

**Status:** v1.1 (2026-07-16) — aligned with Time & Week OS  
**Composes:** architecture, privacy-model, composition-guide, time-and-week-os, CLAUDE.md zone contract.

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
| `projects/**` | H | ❌ | targeted | ❌ | Human links weeks → projects |
| `people/**` | A people-map | ✅ | batch weekly | ✅ people-map only | |
| `patterns/**` | A pattern-detector | ✅ | batch weekly | ✅ pattern-detector only | Multi-week promote only |
| `_meta/psychometrics/**` | A paid | paid | paid | paid | |
| `_meta/time-os/**` | A time-week-os | ✅ | prefer FS | weekly / day stubs | Sanitized work Time OS |
| `_moc/**` | M | link lists | **first hop** | refresh only | Entry graph hubs |
| `_agents/**` | H contracts | ❌ | once / session | ❌ | Load via FS |
| `_archive/**` | H move / R agent | ❌ | ❌ default | ❌ | Cold |
| `CLAUDE.md`, `README.md` | H | ❌ | once | ❌ | |

### Runtime (not in vault, **never MCP**)

| Path | Role | Access |
|------|------|--------|
| `C:/Users/frank/.starlight/time-os/ledger/*.ndjson` | **SSOT time blocks** | FS / `time_os_append.py` only |
| `.../time-os/weekly/` | Weekly packet mirrors | FS |
| `.../time-os/research-cache/` | Ephemeral swarm pulls | FS |

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

**Hard rule:** If any tool path resolves under `.../second-brain/private`, **refuse and escalate**. Boundary is filesystem, not config honesty.

**Truth rank (Time OS):** Ledger > Calendar free/busy > vault `_meta/time-os` > AgentOps > chat inference. Chat is signal; ledger is truth.

---

## 2. When to use filesystem vs MCP

### Decision tree (Hermes / coding agents with local disk)

```
Need content?
├─ Path under private/? → STOP (except explicit /distill-inbox dual-root session)
├─ Ledger / NDJSON / .starlight/time-os? → filesystem only (never MCP)
├─ Know exact path or small glob under brain/? → filesystem
├─ Weekly agents (people / patterns / time-week-os packet)? → filesystem batch
├─ Need Obsidian vault search index / live REST while app open? → MCP (scoped)
├─ Remote client MCP-only? → MCP, still zone-bound to brain/
└─ Unsure → load _moc/HOME.md via FS; never list whole vault
```

### Prefer **filesystem** when

1. Hermes/Claude Code/Codex already have `C:/Users/frank/second-brain/brain` on disk.
2. Writing structured weekly packets under `_meta/time-os/weeks/YYYY-Www/`.
3. Appending ledgers (`time_os_append.py` / NDJSON).
4. Known path: MOC, agent contract, one note.
5. Token-sensitive cron / overnight — avoid MCP tool schemas in context.
6. People-map / pattern-detector weekly jobs.

### Prefer **MCP** when

1. Client is Obsidian-MCP-only (Claude Desktop without vault FS).
2. Cross-note **vault search** via Local REST API while Obsidian is open.
3. Human wants append to a live open note without path guessing.
4. Obsidian is the only warm index and FS glob would be wider/noisier.

### Never use MCP for

| Action | Why |
|--------|-----|
| `private/**` | Privacy contract |
| `~/.starlight/time-os/**` ledger | Not in vault; append-only FS |
| Bulk `list_files_in_vault` every turn | Token + latency burn |
| Writing `notes/`, `projects/`, `_capture.md` | Human-only |
| Human Primary Google Calendar | Not MCP; separate approve gate |
| Secrets / env material | Out of vault |
| Auto private→brain promotion | Manual copy-paste only |
| “Helpful” full reindex per query | MOC → targeted path |

---

## 3. MCP policy matrix (anti over-trigger)

### Allowed MCP tools (from `mcp.json` / Local REST)

| Tool | Max cadence | Scope | Default |
|------|-------------|-------|---------|
| `get_file_contents` | as needed | single path under `brain/` | Prefer FS if available |
| `search` | ≤3 per query session | keywords → then FS deep-read | After MOC fail |
| `append_content` | agent zones only | people / patterns / `_meta/time-os` | Prefer FS patch |
| `patch_content` | agent zones only | same | Prefer FS |
| `list_files_in_vault` | **≤1 per session** | prefer folder-scoped | Prefer `search_files` FS |

### Session budgets

| Session type | MCP budget | FS ops | Must load first (FS) |
|--------------|------------|--------|----------------------|
| Chat Q&A one topic | 0–2 | 1–5 targeted | `_moc/HOME.md` or MOC |
| `/people-update` | **0** preferred | batch notes 90d | `_agents/people-map.md` |
| `/patterns-detect` | **0** preferred | notes+inbox 30d | `_agents/pattern-detector.md` |
| Time OS day close | **0** | ledger + optional day stub | week plan + ledger path |
| Weekly swarm W0–W6 | **0–3** total | packet folder writes | `_agents/time-week-os.md` + ledger |
| `/palace` weekly | 0–5 optional | full ritual | HOME + time-os + patterns |
| Exploratory vault map | **0 list MCP** | MOC only | HOME |

### Pre-MCP self-check (all must be yes)

1. FS unavailable **or** true Obsidian API feature required?
2. Writes only in agent zones?
3. MOC/index already loaded and insufficient?
4. Batched (not N chatty calls)?
5. Path under `brain/` only (not private, not `.starlight`)?

### Obsidian process dependency

MCP Local REST only works while Obsidian is open on `brain/`. If closed → **do not thrash MCP**; fall back to filesystem. Prefer HTTP `127.0.0.1:27123` over self-signed HTTPS 27124 (see `docs/obsidian-mcp.md` when present).

### Hermes-specific routing

| Surface | Method |
|---------|--------|
| Hermes local Windows | **Filesystem primary** on brain + `.starlight/time-os` |
| Claude Desktop + REST | MCP only on brain root |
| Ingest / distill | Scripts + dual-root FS session; MCP not required |
| Multi-agent | Share **paths + abstracts**, not full note bodies |

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
│   ├── pattern-detector.md
│   ├── time-week-os.md          # primary Time OS contract
│   └── time-os.md               # alias → time-week-os (compat)
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
│   ├── psychometrics/
│   └── time-os/
│       ├── README.md
│       ├── routines/            # standing blocks (deep work, leverage, recovery label)
│       ├── days/                # optional thin day stubs (work summary only)
│       │   └── {YYYY}-{MM}-{DD}.md
│       ├── weeks/
│       │   └── {YYYY}-W{ww}/    # weekly swarm packet
│       │       ├── 00-context.md
│       │       ├── 01-pareto.md
│       │       ├── 02-market-events.md
│       │       ├── 03-research-books.md
│       │       ├── 04-time-design.md
│       │       ├── 05-psych-cycles.md   # non-clinical cautions only
│       │       ├── 99-weekly-brief.md
│       │       └── evidence.json
│       ├── pareto/              # optional flat index of 01-pareto copies
│       └── insights/            # human-promoted durable learnings
├── _moc/
│   ├── HOME.md
│   ├── MOC-People.md
│   ├── MOC-Projects.md
│   ├── MOC-Patterns.md
│   └── MOC-Time-OS.md
└── _archive/
```

### Runtime (FS only)

```
C:/Users/frank/.starlight/time-os/
├── README.md
├── time_os_append.py
├── ledger/{YYYY}-{MM}-{DD}.ndjson
├── daily/
├── weekly/{YYYY}-W{ww}/
└── research-cache/
```

### `private/` (no MCP)

```
private/
├── README.md
├── .obsidian-no-sync
├── .metadata_never_index
├── journal/daily/{YYYY}-{MM}-{DD}.md
├── health/{metrics,protocols,clinical}/
├── finances/
├── relationships/
├── chat-history/{claude-ai,chatgpt}/
└── _distill/
    ├── pending/                 # promotion staging only
    ├── rejected/                # optional
    └── audit.jsonl
```

---

## 5. Weekly note graph

```text
_moc/HOME.md
  └─ [[MOC-Time-OS]]
       ├─ weeks/{YYYY}-W{ww}/99-weekly-brief   ← graph hub for the week
       │    ├─ 00-context ← ledger evidence (paths, not private quotes)
       │    ├─ 01-pareto
       │    ├─ 04-time-design → optional days/*
       │    └─ patterns/{YYYY}-W{ww} (if run)
       ├─ routines/*
       └─ insights/* (human-ratified only)

_moc/MOC-Patterns.md → patterns/*
_moc/MOC-People.md   → people/* touched
_moc/MOC-Projects.md → projects/* (human)

NO edges into private/** or .starlight/** (runtime is not wiki-linked).
```

### Cadence

| Cadence | Private | Brain | Runtime | Who |
|---------|---------|-------|---------|-----|
| Daily raw | journal/daily | — | — | Human |
| Daily work | — | optional days/ stub | ledger NDJSON | time-week-os + human confirm |
| Weekly swarm | pending distill | weeks/YYYY-Www/* | weekly mirror | W0–W6 once |
| Patterns | optional pending | patterns/YYYY-Www | — | pattern-detector |
| Insights | — | time-os/insights | — | human promote |

### Graph hygiene

1. Frontmatter `type`: `time-os-week-part`, `time-os-day`, `pattern-week`, `person`, `project`, `moc`.
2. Week **brief** is the hub; packet parts link to brief, not full mesh.
3. Dailies link to week brief + ≤3 projects.
4. Color by `type` / folder in Obsidian Graph.
5. Never wikilink private vault paths.

---

## 6. Promotion rules: `private` → `brain`

### Single bridge (non-automated)

```
private/_distill/pending/{draft}.md  --[human copy-paste]-->
  brain/patterns/  OR  brain/_meta/time-os/insights/
```

No script, no MCP, no agent write into private for promotion.

### Checklist (all required)

1. **Anonymized** — no intimate names, accounts, diagnoses, sensitive locations.
2. **Pattern-level** — themes / behaviors, not diary excerpts.
3. **Counts without quotes** — “N private journal days” ok; raw lines only if fully sanitized.
4. **No reverse pointer** into `private/`.
5. **Human ratification** — Frank moves content; agents may propose draft text in chat for human to paste into `pending/`.
6. **Clipboard clear** after paste (privacy-model §6).
7. **SIP attestation** on agent-shaped brain pattern/insight files.

### Destinations

| Draft kind | Destination |
|------------|-------------|
| Recurring topic / anti-pattern | `brain/patterns/{YYYY}-W{ww}.md` or merge |
| Work/time leverage learning | `brain/_meta/time-os/insights/{slug}.md` |
| Collaborator work context | people-map from **brain** sources only |
| Clinical / finance / intimate | **reject** — stay private |

### Distill vs promotion

| Flow | private access | MCP |
|------|----------------|-----|
| Dual-write ingest | script writes raw private + stub brain | never |
| `/distill-inbox` | coding-agent dual-root **FS** session only | never mount private |
| Default Hermes chat | treat private as air-gapped | N/A |
| Pattern promotion | human paste only | never |

---

## 7. Interconnection (compound without burn)

```
Capture (H) → Inbox stubs (I) → Distill (FS session) → notes/projects (H)
     │
     ├─ ledger append (FS) ← agent work blocks ≥15m
     │
     └─ people-map / pattern-detector / time-week-os (A, FS-primary)
              ↓
         _moc hubs + weekly packet edges
              ↓
         insights (human promote) → long-term compound memory
```

**Token rules**

1. Enter via MOC, not vault list.
2. Handoffs: **paths + ≤3-line abstracts**, not full bodies.
3. Weekly swarm **once**; write packet files, don’t rewrite history ledger lines.
4. Local Dataview/Smart Connections for “related”; LLM for synthesis only.
5. Hermes memory stores durable facts; vault stores structured notes — no full-note duplication into session memory.
6. Runtime ledger never round-trips through MCP or LLM context in bulk — query by day file.

---

## 8. `/palace` + Time OS weekly ritual

1. `scripts/verify-privacy.*` on private vault.
2. Triage `brain/_inbox/` (H).
3. FS: `/people-update`, `/patterns-detect` (0 MCP if local FS).
4. Time & Week OS swarm once → `weeks/YYYY-Www/` + runtime mirror.
5. Human: `private/_distill/pending/` → promote or reject.
6. Refresh `_moc/*` link lists.
7. `/sbo-verify`.
8. Clear clipboard if private paste occurred.

---

## 9. Acceptance tests

- [ ] MCP vault root = `.../second-brain/brain` only.
- [ ] No MCP config references `private` or `.starlight/time-os`.
- [ ] Agent refuses private path.
- [ ] Local FS people/patterns/time jobs run with **0 MCP**.
- [ ] Ledger append never uses MCP.
- [ ] Week graph: HOME → MOC-Time-OS → week brief → parts; no private edges.
- [ ] Promotion only via pending + human paste.
- [ ] `list_files_in_vault` ≤1 per exploratory session.

---

## Related

- `docs/time-and-week-os.md` — Time plane product contract (sibling worktree / main after merge)
- `docs/privacy-model.md` — threat model
- `docs/architecture.md` — three edges, two vaults
- `docs/obsidian-mcp.md` — Local REST wiring gotchas
- Live: `brain/_agents/time-week-os.md`, `brain/_meta/time-os/README.md`

## SIP attestation

```
sip: true
artifact: docs/mcp-usage-policy.md
version: 1.1
date: 2026-07-16
composes: second-brain-os + time-and-week-os
```
