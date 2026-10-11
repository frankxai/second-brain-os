# Cited Archive Search

Second Brain OS provides cited lexical search over the selected brain root (`_meta/kura-archive-index.json`).

## Key Guarantees

- **Brain Scope Only**: Search scans only the public brain vault (`brain_root`). Private history in `private_root` is never opened or indexed.
- **Cited Results**: Every search result returns a relative path citation (`notes/decisions/...`), platform source, date, and relevance score.
- **Metadata Protection for Pending Notes**: Unreviewed or pending notes (`status: needs-summary` or `distill_pending: true`) return metadata-only records; their full text content is hidden from search excerpts.
- **Cursor Generation Binding**: Search pagination cursors include an index generation hash. If the archive changes between requests, the cursor fails closed with `{"ok": false, "code": "index_changed"}` to avoid duplicated or skipped results.
- **Native Host Protocol Integration**: Chrome extension native messaging host supports `op="search"` with strict response size limits (<= 4096 bytes).
