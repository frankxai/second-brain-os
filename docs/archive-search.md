# Cited archive search

The brain vault remains the canonical store. `sbo_ingestion.archive_search` builds a derived lexical cache at `_meta/kura-archive-index.json`. Deleting that file only forces a rebuild. The private root is never opened.

Pending notes (`needs-summary`, `pending`, `raw`) return title, citation, status, platform and date. Their bodies and summaries are not indexed or returned. Reviewed and other non-pending brain notes return a 160-character excerpt and an original conversation link only when that link is HTTPS on an allowlisted provider host.

The native host exposes this as `op: search`. Replies stay inside the existing 4,096-byte metadata budget. A cursor is bound to the index generation; a changed archive returns `index_changed` instead of skipping a page.

The cache records the SHA-256 of the exact bytes parsed. Every eligible Markdown source is read to check its content identity, including warm searches; unchanged size and timestamp alone cannot establish unchanged content. Legacy or malformed records rebuild from source. Returned notes are read again for current metadata and a query-specific excerpt. A changed, deleted or unreadable result refuses the page with `index_changed`; retry against the updated archive.

The `idea-capture` platform filter selects deliberately distilled capture notes without labeling them as a chat provider. Pending capture notes remain metadata-only. This filter does not expand permitted source-link hosts or enable native capture ingestion.

Earlier stat-only synthetic timing measurements do not describe this content-verified implementation. Benchmark the selected archive before making latency or scale claims. Content hashes do not authenticate cached ranking, create a globally atomic archive snapshot, or establish protection against hostile path swaps. Native browser installation, whole-vault performance and creator acceptance require separate verification.
