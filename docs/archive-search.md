# Cited archive search

The brain vault remains the canonical store. `sbo_ingestion.archive_search` builds a derived lexical cache at `_meta/kura-archive-index.json`. Deleting that file only forces a rebuild. The private root is never opened.

Pending notes (`needs-summary`, `pending`, `raw`) return title, citation, status, platform and date. Their bodies and summaries are not indexed or returned. Reviewed and other non-pending brain notes return a 160-character excerpt and an original conversation link only when that link is HTTPS on an allowlisted provider host.

The native host exposes this as `op: search`. Replies stay inside the existing 4,096-byte metadata budget. A cursor is bound to the index generation; a changed archive returns `index_changed` instead of skipping a page.

Synthetic measurement on this implementation, not the selected personal vault: 5,000 generated notes, cold rebuild 965 ms, warm reuse 120 ms, 5,000 files reused, no private path in the reply. That does not measure Frank's archive or production Chrome transport.
