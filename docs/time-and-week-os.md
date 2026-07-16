# Time & Week OS (SBO composition vertical)

> Personal time plane + weekly founder intelligence swarm, composed onto Second Brain OS + AgentOps Mission Control.
> Product docs are generic. Live personal runtime stays on the operator machine (vault + `.starlight/time-os`).

## Intent

Give multi-CLI agents (Hermes, Claude Code, Codex, OpenCode) one shared contract to:

1. Protect human calendar and routines
2. Log human + agent work blocks into a durable ledger
3. Infer soft day activity from sessions (never sole truth)
4. Run a **weekly planning + Pareto + intelligence swarm**
5. Write only to allowed second-brain zones
6. Use Obsidian MCP sparingly

## SSOT stack (order of truth)

| Rank | Plane | What it owns | Tool |
|---|---|---|---|
| 1 | **Ledger** | Time blocks, ROI labels, Pareto evidence | `~/.starlight/time-os/ledger/*.ndjson` |
| 2 | **Google Calendar** | Human schedule + free/busy + optional AgentOps calendar | Google Calendar API |
| 3 | **Second brain `_meta/time-os/`** | Weekly plans, Pareto notes, routine templates (agent write) | Obsidian vault (filesystem primary) |
| 4 | **Mission Control AgentOps** | Agent work blocks bus | `starlight-mission-control` |
| 5 | **Chat/session inference** | Soft reconstruction of the day | Hermes `session_search` / CLI session logs |
| 6 | **Notion / Notion Calendar** | Optional narrative UI / viewer of Google | Never write SSOT |

**Hard rule:** Chat is signal. Ledger is truth. Calendar is schedule. Vault is compound knowledge.

## Calendars (separate, always)

| Calendar | Writers | Purpose |
|---|---|---|
| Human Primary | Human + EA (Hermes after explicit approve) | Meetings, family, travel |
| Routines / Deep Work | EA with templates | Focus blocks, gym, creator batch |
| AgentOps | Agents via hooks / daily sweep | `[AgentOps] <agent> — <task>` only |
| Content / Publish | Content OS | Marketing calendar only |

Never dump agent noise onto Human Primary.

## Multi-CLI maintainability

All CLIs read the same three files first:

1. This doc: `docs/time-and-week-os.md`
2. Schema: `schemas/time-block.schema.json`
3. Live operator map: vault `_meta/time-os/README.md` (instance)

### Who may write what

| Writer | Ledger | Google Human | Google AgentOps | Vault `_meta/time-os` | Vault human zones |
|---|---|---|---|---|---|
| Hermes (EA) | yes | only after approve | yes (sweep) | yes | **no** |
| Claude Code | via hook | no default | via hook if MCP | yes (agents) | **no** |
| Codex | via hook | no | via hook | yes (agents) | **no** |
| OpenCode / others | via hook | no | no default | yes (agents) | **no** |
| Human | optional edit | yes | rare | yes | yes |

### Anti-thrash rules

1. One writer owns Google Human Primary per day (Hermes EA or Frank). Others propose.
2. Ledger append-only NDJSON. Never rewrite history; correct with `status: corrected` + `corrects: <id>`.
3. Weekly swarm runs **once** (Sunday local or Frank-chosen slot). Outputs go under a week id folder.
4. Draft PR / local files first for product changes; no dual-gateway spam of digests.
5. Obsidian MCP: use only for vault search/read/write when filesystem is awkward; default to filesystem tools.

## Daily loop

```
Morning (EA)
  → load week plan + free/busy (if Google live)
  → propose 1–3 deep-work blocks + top 3 outcomes
  → Frank confirms or edits

During day
  → agents end blocks ≥15m → AgentOps ledger + optional calendar
  → Hermes sessions tagged by brand lane when obvious

Evening close (soft auto)
  → infer day from sessions + agent ledger
  → propose day blocks with confidence
  → Frank confirm (2 min) OR accept defaults for high-confidence agent-only blocks
  → append human ledger rows
  → optional vault daily stub in _meta/time-os/days/ (non-private summary)
```

Sensitive mood/health detail stays out of MCP vault unless Frank promotes an anonymized pattern.

## Weekly swarm (founder intelligence)

Run as a bounded pipeline (not infinite chat):

| Phase | Agent role | Output |
|---|---|---|
| W0 | **Context packer** | week facts: ledger hours, shipped links, open priorities |
| W1 | **Pareto auditor** | 20% activities → 80% outcomes; kill list |
| W2 | **Market & events scout** | macro + domain events next 7–14d |
| W3 | **Research & books scout** | 3–7 high-signal insights (papers/books/operators) |
| W4 | **Time design synthesizer** | next-week block design + energy phases |
| W5 | **Psychology / cycle note** | mood/energy/attention cautions (non-clinical) |
| W6 | **Chief of Staff merger** | single weekly brief + calendar proposals |

### Weekly artifacts (live instance)

```
brain/_meta/time-os/weeks/YYYY-Www/
  00-context.md
  01-pareto.md
  02-market-events.md
  03-research-books.md
  04-time-design.md
  05-psych-cycles.md
  99-weekly-brief.md
  evidence.json
```

Runtime copies may also live under `~/.starlight/time-os/weekly/YYYY-Www/`.

## Pareto measurement

Pareto is **outcome-weighted**, not hour-weighted.

Each closed block carries:

- `lane`: arcanea | frankx | gencreator | starlight-ops | health | life | admin
- `class`: leverage | ship | maintenance | recovery | waste
- `outcome_score`: 0–5 (evidence-backed)
- `evidence_links[]`: PR, deploy, revenue, post, decision note

Weekly Pareto formula (simple v1):

1. Group by activity cluster (lane+class+theme)
2. Sum `outcome_score * duration_hours`
3. Rank clusters; top cumulative 80% = **vital few**
4. Bottom quartile maintenance with low score = **kill or automate candidates**

## Second brain interconnection

| Zone | Time OS use |
|---|---|
| `_meta/time-os/` | Agent operating surface (plans, Pareto, routines) |
| `_moc/MOC-Time-OS.md` | Map of content hub |
| `patterns/` | Promoted multi-week patterns only |
| `people/` | Mentors / collaborators mentioned in week intel (optional) |
| `projects/` | **Human only** — Frank links projects to weeks |
| `private/journal` | Human mood/energy (no MCP, no agent default) |
| `_capture.md` | Human drops; agents never edit |

### Obsidian MCP policy

**Use MCP when:**

- Cross-note graph search is needed and REST API is already warm
- Another CLI is MCP-only for vault

**Prefer filesystem when:**

- Hermes/Codex already have path access
- Writing structured weekly packet files
- Appending NDJSON ledgers (never via MCP)

**Never use MCP for:**

- `private/` vault
- Secret/env material
- Bulk rewrite of human notes

## Skills map (Hermes)

| Job | Skills |
|---|---|
| Bootstrap / paths | `agent-workspace-bootstrap`, `windows-phone-link-search-safety` |
| Vault writes | `obsidian`, `obsidian-second-brain` |
| Knowledge architecture | `starlight-second-brain-os`, `starlight-knowledge-architecture` |
| Calendar (after auth) | `google-workspace` |
| Weekly research | `arxiv`, `web_search`, `x_search` |
| Events | `events-attendance-os` |
| Task discipline | `todo-discipline` |
| Swarm ops | `agentic-orchestration`, `cron-orchestration` |
| Portfolio evidence | `multi-repo-portfolio-swarm`, `github-pr-workflow` |

## Activation checklist

1. Google OAuth Hermes (`calendar` scope minimum)
2. Create calendars: Routines, AgentOps (if missing)
3. Confirm vault `_meta/time-os/` exists
4. Install Hermes skill `time-and-week-os`
5. Enable evening close cron (local deliver first)
6. Enable Sunday weekly swarm cron
7. Wire AgentOps hooks in coding CLIs

## Non-goals

- Replacing therapy/clinical tools
- Auto-sending calendar invites to external humans without approve
- Making Notion the ledger
- Full dual-laptop rebroadcast of every digest
