# Second Brain OS — Durable Memory

> Per SIP Layer 1. Durable state, commitments, open forks.

## Version

`v0.1.0` (planned first public release; not yet tagged).

## Commitments

- **Privacy contract:** MCP server vault root cannot resolve `private/` path. Filesystem-level boundary, not config. Non-waivable.
- **OSS license:** MIT. Permanent. Future paid tier additions go in a separate `@frankx/second-brain-pro` package; OSS template stays free.
- **Validity disclosures:** Psychometric agents (Big 5, 16P, STP, Enneagram) MUST ship with non-removable validity disclosures explaining the limits of LLM-inferred personality assessment.
- **Honest claims:** "30 min to wire, up to 24h to first insight." The Claude.ai export delivery window is the floor.

## Open forks

- **Phase 2 seam:** When Anthropic / OpenAI ship MCP-to-MCP memory bridges, `src/sbo_ingestion/handlers/` adds `claude_memory_mcp.py` + `chatgpt_memory_mcp.py` without touching the rest. The public API is `ingest(source) → (raw_files, brain_files)`.
- **arcanea-vault Chrome extension:** Deferred to Phase 4. The extension could ingest live (rather than waiting 24h for JSON dumps). Resurrection decision pending.
- **`MarkusPfundstein/mcp-obsidian`** unmaintained-risk: Phase 2 defensive fork into `frankxai/mcp-obsidian` if upstream stalls.

## Composes from

- SIS (Starlight Intelligence System) — substrate canon source. Personal instance live-symlinks SIS memory-bus MCP.
- Library OS — command/skill/subagent triple pattern reused.
- Starlight Chronicle — weekly Palace Review is the canonical distillation cadence.
- ACOS — agent registry pattern.
- Family Tree — kinship-data pattern generalized to all-people for people-map agent.

## Built on SIP

This memory file is the durable layer for SBO. Updated on every significant decision. Per SIP Layer 1.
