# Cited Archive Search

Second Brain OS provides cited lexical search over the selected brain root (`_meta/kura-archive-index.json`).

The brain vault remains the canonical store. `sbo_ingestion.archive_search` builds a derived lexical cache at `_meta/kura-archive-index.json`. Deleting that file only forces a rebuild. The private root is never opened.

## Key Guarantees

- **Brain Scope Only**: Search scans only the public brain vault (`brain_root`). Private history in `private_root` is never opened or indexed.
- **Cited Results**: Every search result returns a relative path citation (`notes/decisions/...`), platform source, date, and relevance score.
- **Metadata Protection for Pending Notes**: Unreviewed or pending notes (`needs-summary`, `pending`, `raw`, or `distill_pending: true`) return title, citation, status, platform and date. Their bodies and summaries are not indexed or returned. Reviewed and other non-pending brain notes return a 160-character excerpt and an original conversation link only when that link is HTTPS on an allowlisted provider host.
- **Cursor Generation Binding**: Search pagination cursors include an index generation hash. If the archive changes between requests, the cursor fails closed with `{"ok": false, "code": "index_changed"}` to avoid duplicated or skipped results.
- **Native Host Protocol Integration**: The native messaging host exposes this as `op: search` with strict response size limits inside the existing 4,096-byte metadata budget.
- **Content-Verified Cache**: The cache records the SHA-256 of the exact bytes parsed. Every eligible Markdown source is read to check its content identity, including warm searches; unchanged size and timestamp alone cannot establish unchanged content. Legacy or malformed records rebuild from source. Returned notes are read again for current metadata and a query-specific excerpt. A changed, deleted or unreadable result refuses the page with `index_changed`; retry against the updated archive.
- **Idea-Capture Support**: The `idea-capture` platform filter selects deliberately distilled capture notes without labeling them as a chat provider. Pending capture notes remain metadata-only. This filter does not expand permitted source-link hosts or enable native capture ingestion.

Earlier stat-only synthetic timing measurements do not describe this content-verified implementation. Benchmark the selected archive before making latency or scale claims. Content hashes do not authenticate cached ranking, create a globally atomic archive snapshot, or establish protection against hostile path swaps. Native browser installation, whole-vault performance and creator acceptance require separate verification.
