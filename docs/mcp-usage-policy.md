# MCP Usage Policy — Second Brain OS

> Goal: compound knowledge **without token burn**. MCP is a scalpel, not a vacuum.  
> Live vaults: `C:/Users/frank/second-brain/brain` (MCP-eligible) · `.../private` (never MCP).  
> Time plane SSOT: `docs/time-and-week-os.md` + `~/.starlight/time-os/` (runtime ledger).

**Status:** v1.1 (2026-07-16) — aligned with Time & Week OS  
**Composes:** architecture, privacy-model, composition-guide, time-and-week-os, CLAUDE.md.

---

## 1. Zone map

| Path | Zone | MCP read | MCP write |
|------|------|----------|-----------|
| `_capture.md`, `notes/**`, `projects/**`, `_inbox/manual/` | Human-only | rare/targeted | ❌ |
| `_inbox/{claude-ai,chatgpt}/` | Ingest script | distill batch | ❌ |
| `people/**` | people-map | weekly | people-map only |
| `patterns/**` | pattern-detector | weekly | pattern-detector only |
| `_meta/time-os/**` | time-week-os | prefer FS | packet/day stubs |
| `_moc/**` | Mixed | **first hop** | link refresh only |
| `_agents/**` | Contracts | once/session | ❌ |
| `private/**` | 🚫 | never | never |
| `~/.starlight/time-os/**` | Runtime ledger | never (not vault) | never MCP |

**Hard rule:** MCP root = `brain/` only. Private path resolution → refuse + escalate.

**Truth rank:** Ledger > Calendar > vault time-os > AgentOps > chat inference.

---

## 2. Filesystem vs MCP

| Prefer FS | Prefer MCP |
|-----------|------------|
| Hermes/Codex local path access | Claude Desktop MCP-only |
| Weekly packets, people, patterns | Live Obsidian vault search |
| Ledger NDJSON / `time_os_append.py` | Append to open note via REST |
| Cron / token-sensitive jobs | REST warm + FS awkward |

**Never MCP:** private, ledger, human zones writes, bulk list every turn, auto promotion, secrets.

### Decision tree

```
private? → STOP
ledger/.starlight? → FS only
known brain path? → FS
weekly agents? → FS batch
need Obsidian search/live REST? → MCP scoped
MCP-only client? → MCP zone-bound
else → MOC via FS; no vault-wide list
```

---

## 3. Anti over-trigger matrix

| Tool | Budget |
|------|--------|
| `list_files_in_vault` | ≤1 / session |
| `search` | ≤3 / query session |
| people/patterns/time jobs | **0 MCP** if FS works |
| weekly swarm total | 0–3 MCP |
| Q&A session | 0–2 MCP |

**Pre-call checks (all yes):** need API not FS · agent-zone write · MOC insufficient · batched · under brain/.

Obsidian must be open for REST; if closed → FS, don’t thrash MCP. Prefer HTTP `:27123` over HTTPS `:27124`.

---

## 4. Folder trees (condensed)

**brain/_meta/time-os/** — `routines/`, `days/`, `weeks/YYYY-Www/{00..05,99-brief,evidence.json}`, `insights/`  
**private/** — journal, health, finances, relationships, chat-history, `_distill/pending`  
**runtime** — `~/.starlight/time-os/ledger/*.ndjson` (SSOT)

Full trees: see main copy of this doc on `main` / parent agent deliverable; weekly packet layout in `time-and-week-os.md`.

---

## 5. Weekly note graph

```
HOME → MOC-Time-OS → weeks/YYYY-Www/99-weekly-brief
         → 00-context, 01-pareto, 04-time-design → days/*
         → patterns/YYYY-Www
No edges to private/ or .starlight/
```

---

## 6. Promotion private → brain

**Only bridge:** `private/_distill/pending/*` → human copy-paste → `brain/patterns/` or `_meta/time-os/insights/`.

Rules: anonymized · pattern-level · no reverse links · human ratify · clear clipboard · SIP on agent-shaped files.  
Reject clinical/finance/intimate. Distill dual-root FS is not MCP and not default chat.

---

## 7. Token discipline

Enter via MOC · handoff paths+abstracts · weekly swarm once · Dataview local for related · no full-note dump into session memory · don’t bulk-load ledger into LLM.

---

## SIP

```
sip: true
artifact: docs/mcp-usage-policy.md
version: 1.1
date: 2026-07-16
```
