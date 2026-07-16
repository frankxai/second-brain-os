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

## SSOT stack (order of truth) — council v1.1

| Rank | Plane | What it owns | Path / tool |
|---|---|---|---|
| 1a | **Agent runs** | Work receipts | `~/.starlight/runs/…/receipt.json` |
| 1b | **Founder events** | Run lifecycle bus | `~/.starlight/events/founder-events-*.jsonl` |
| 1c | **Time blocks** | Confirmed human+agent time | `~/.starlight/time-os/blocks/*.ndjson` |
| 1d | **Week machine** | Single-writer plan | `~/.starlight/time-os/week/YYYY-Www/plan.json` |
| 2 | **Google Human Primary** | Meetings / life schedule | Google Calendar API (human + EA gated) |
| 3 | **Views** | AgentOps cal, ICS, Obsidian `_meta/time-os`, digests | regenerable |
| 4 | **Proposed queue** | Soft chat inference | `~/.starlight/time-os/queue/proposed/` |
| 5 | **Notion Calendar** | Optional UI | Never SSOT |

**Hard rules:** Chat is signal. **Blocks + runs + events** are truth. Calendar/Obsidian/Notion are views.  
**Do not invent a third ledger.** Mission Control git `agent-log.ndjson` is non-authoritative (museum).  
**One append script:** `~/.starlight/time-os/time_os_append.py` (or product copy). No freehand NDJSON.  
**Streams stay separate:** agent-runs ≠ time-blocks ≠ week-plan — link by `run_id` / week_id.  
**Dual-machine:** Yogabook primary writer; C940 read/enqueue only.

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
2. Blocks append-only via **one script**. Never rewrite history; correct with `status: corrected` + `corrects: <id>`.
3. Soft inference → `queue/proposed/` only; confirmed rows require `confirmed_by` + `confirmed_at`.
4. Weekly swarm single-flight: `locks/week-YYYY-Www.lock`; rewrite `plan.json` once; vault MD is a **view**.
5. Draft PR / local files first for product changes; no dual-gateway spam of digests.
6. Obsidian MCP: scalpel only — see `docs/mcp-usage-policy.md` (0 MCP for time jobs if FS works).
7. Disk TIGHT: cap weekly research artifacts; no bulk clones for week review.

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

Composes topology report:  
`starlight/queen/reports/weekly-pareto-founder-intelligence-swarm-topology-2026-07-16.md`  
and protocol: `~/.starlight/weekly-pareto/protocol.v1.json`  
→ **machine SSOT** always lands in `~/.starlight/time-os/week/YYYY-Www/plan.json`.

| Wave | Agents | Mode |
|---|---|---|
| 0 | **A0** Conductor + gatekeeper (disk/token gates) | serial |
| 1 | Work ledger · Intel · Market/audience · Events · Phase/body-mind | parallel read-only |
| 2 | **Pareto scorer** + 3-lane week plan | serial |
| 3 | Compiler + verifier → brief + gate JSON | serial → human |

### Anti-busywork (measured)

- Caps: ≤30 work rows scored, ≤3 week lanes, ≤7 outcomes, ≤5 bets  
- **≥40% kill/park** of candidate work or gate fails  
- Agent work without durable residue max score 2  
- Soft token budget (~140k); disk &lt;40 GiB free → no research fanout  

### Weekly artifacts

**Machine (SSOT):** `~/.starlight/time-os/week/YYYY-Www/plan.json` + packet files  
**Vault (VIEW):** `brain/_meta/time-os/weeks/YYYY-Www/` (`00`…`05`, `99-weekly-brief.md`)

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
