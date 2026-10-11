# Independent Report-Only Review: Content-Verified Recall and Capture Source Identity

## Context and Scope

This review evaluates pull request 18 (issue 10) for repository `frankxai/second-brain-os` at head commit `16cea4d4bec0b10f6b591d6141641ed9698ab9f1` relative to base commit `7c7d3333bff3f48b3c5e353e93d2aa8c760f1b29`.

This evaluation is an isolated report-only review. The evaluation inspects 35 target repository paths across core ingestion code, archive search, native host drivers, documentation, and unit tests.

---

## Broken vs. Correct Behavior

### Broken Behavior (Prior State)
1. **Stat-Only Caching Stale Content**: Archive search previously relied solely on file size (`size`) and modification timestamp (`mtime_ns`) to check cache validity. Edits that preserved file size and modification time ("same-stat edits") bypassed re-parsing and re-indexing, resulting in stale cached content and incorrect search recall.
2. **Unsupported Idea Capture Filter**: Queries specifying `platform="idea-capture"` were not properly handled or filtered, failing to recognize capture identity and risking exposure of pending private notes in search replies.

### Correct Behavior (Head 16cea4d)
1. **Exact Parsed Byte Hashing**: Archive search in `src/sbo_ingestion/archive_search.py` computes SHA-256 digests (`sha256`) of exact parsed file bytes during indexing (`_hash_file` at line 78).
2. **Legacy Cache Rebuild**: Legacy index format (`version: 1`) lacking SHA-256 digests is detected during `load_index` (line 90) and automatically rebuilt to `version: 2` with complete file hashes.
3. **Dynamic Metadata and Excerpt Re-Read**: Search queries re-read active file content from disk to extract current title, status, review level, and query excerpts rather than returning outdated cached text.
4. **Refusal of Mutated/Corrupted Files**: If a file is edited, converted to pending status, deleted, or corrupted with invalid UTF-8 between index load and result packaging, search refuses stale payload delivery and returns `{"ok": False, "code": "index_changed"}` (lines 201-205).
5. **Idea Capture Identity and Privacy**: `src/sbo_ingestion/handlers/idea_capture.py` recognizes captures from platform `idea-capture`. Pending captures (`status: needs-summary` or `status: pending`) return `excerpt: null` and suppress private body text in response payloads.
6. **Bounded Native Host Messaging**: `src/sbo_ingestion/native_host.py` frames response stdout frames with a 4-byte length prefix and bounds response frames under 4096 bytes without expanding the native host allowlist or protocol.

---

## Root Evidence vs. Executed Tests

### Root Evidence (PR Author / CI Records)
- **Baseline Test Results**: 38 failed, 24 passed, 1 skipped (Windows privilege skip).
- **Candidate Test Results**: 62 passed, 1 skipped.
- **Combined Candidate and Product Test Suite**: 257 passed, 5 skipped, Ruff clean.
- **Conftest Restoration**: Fixed initial test setup by restoring the pinned fixture setup.

*Note: The root evidence numbers listed above represent recorded PR metrics and are kept separate from sandbox execution.*

### Sandbox Executed Tests
- **Pytest Test Execution**: 173 passed, 1 skipped in 10.17 seconds using `.venv/bin/pytest -v`.
- **Ruff Formatter Verification**: `docs/reviews/content-verified-recall-20261011.json` and `docs/reviews/content-verified-recall-20261011.md` formatted cleanly with `ruff format`.

---

## Verification of Prior Review (b070 / ID 7838999235505530183)

The prior review evaluated commit `b0706e085de76d29f57305dde62e17c7bd72a710` and verified 35 rows across two report files.

### Qualified Acceptance Analysis
1. **Resolved Historical Line Number Discrepancy**: The prior review noted a wrong line pointer in `tests/test_security.py`. In head `16cea4d`, security test lines and imports are correctly aligned.
2. **Atomic Writes and fsync**: Prior claims of "no fsync" were contradicted by `src/sbo_ingestion/ingest.py:148`, where `os.fsync(f.fileno())` explicitly flushes written content to disk before atomic rename.
3. **Stale Remote CI Run**: Prior run `38139003213` (9 jobs, 223 passed, 1 skipped) belonged to an earlier commit and cannot certify head `16cea4d`.

---

## Detailed Technical Inspection

### 1. Same-Stat Edits
`tests/test_archive_search.py` tests `test_same_stat_edit_uses_current_content` using `os.utime` to match `st_mtime_ns` and matching byte lengths. Because `archive_search.py` compares SHA-256 hashes of parsed file bytes, same-stat modifications are detected and trigger current content re-reads or index rebuilds.

### 2. Malformed and Poisoned Caches
In `test_shape_valid_cached_output_is_replaced_by_canonical_metadata`, forging `title` or `excerpt` fields in `_meta/kura-archive-index.json` does not corrupt search output. The search process re-reads canonical frontmatter and text from disk, overriding forged index fields.

### 3. Pending Privacy
Notes with `status: pending` or `status: needs-summary` return `review: "metadata-only"` and `excerpt: null`. Tests confirm that private body strings do not appear in search JSON responses.

### 4. Hidden and Outside Paths
Files located in hidden directories (e.g., `.hidden/forged.md`) or outside the designated brain root are excluded prior to search result packaging.

### 5. Query Excerpts and Unicode Offsets
`test_unicode_before_named_subject_does_not_shift_source_offsets` validates string handling when multibyte Unicode sequences (e.g., `chr(304)`) precede search matches. Character-based slicing in `_excerpt` prevents offset drift and keeps excerpts bounded within `MAX_EXCERPT` (400 characters).

### 6. Result Mutations and Race Safety
If a file is edited, deleted, marked pending, or replaced with non-UTF-8 bytes between index loading and response generation, `archive.search` rejects the stale candidate and returns `{"ok": False, "code": "index_changed"}`.

### 7. Cursor and Retry Behavior
Pagination cursors encode index state hashes. If any underlying file is updated before a cursor retry, search rejects the stale cursor with `code: "index_changed"`.

### 8. Native Response Bounds
`src/sbo_ingestion/native_host.py` frames output frames with a 4-byte big-endian length prefix. Message responses remain bounded under 4096 bytes per message.

### 9. Capture Filter and Capture -> ACK -> Completion -> Citation Flow
Captures originating from `idea-capture` retain their platform identity, issue acknowledgment receipts, complete distillation into `brain/`, and cite relative vault paths.

### 10. Ordinary Ingestion and Retrieval
Standard file ingestion and archive searches operate cleanly across `chatgpt`, `claude.ai`, `kura`, and `idea-capture` formats.

### 11. Chrome Native Host Registration Scope
Unit tests in `tests/test_native_host.py` invoke `process_request` via standard I/O pipes. They do not run inside an active Chrome browser process or install current-user Native Messaging host manifests in the operating system registry or file system paths.

---

## Source-Bound Limitations and Open Acceptance Gaps

### Performance and Scale Limitations
1. **Sequential File Scan Cost**: Archive search reads all eligible Markdown files during full index scans. On large brain vaults containing thousands of files, sequential file I/O introduces O(N) memory and runtime costs.
2. **Cached Ranking Not Authenticated**: SHA-256 hashes authenticate individual file bytes but do not verify cached relevance scores or ranking order.
3. **Non-Atomic OS Snapshot Window**: File index loading and content re-read occur in separate steps. Simultaneous mass file writes during a search query can trigger `index_changed` status retries.

### Findings Grouped by Status

#### PASS
- **exact_parsed_bytes_hashing**: `src/sbo_ingestion/archive_search.py:78` computes exact parsed byte SHA-256 digests.
- **legacy_cache_invalidation**: `src/sbo_ingestion/archive_search.py:90` automatically upgrades version 1 caches to version 2.
- **dynamic_result_metadata_reread**: `src/sbo_ingestion/archive_search.py:150` re-reads current file content from disk during search.
- **mutation_refusal**: `src/sbo_ingestion/archive_search.py:201` returns `code: "index_changed"` on file modifications during search.
- **idea_capture_identity_and_privacy**: `src/sbo_ingestion/handlers/idea_capture.py` retains source identity and protects pending notes.
- **unicode_and_excerpt_offsets**: `src/sbo_ingestion/archive_search.py:24` uses character-based slicing for Unicode offsets.
- **bounded_native_messaging**: `src/sbo_ingestion/native_host.py:30` frames messages under 4096 bytes.

#### WARN
- **markdown_scan_budget**: `src/sbo_ingestion/archive_search.py` performs sequential Markdown file reads, creating I/O overhead on large vaults.
- **cached_ranking_not_authenticated**: `src/sbo_ingestion/archive_search.py` verifies raw content bytes but does not authenticate score ranking ordering.
- **concurrent_os_snapshot_race**: Non-atomic multi-file reads can produce `index_changed` retries during active concurrent writes.

#### FAIL (Current Acceptance Gaps)
- **pending_live_ci_certification**: Live CI workflow execution for head commit `16cea4d4bec0b10f6b591d6141641ed9698ab9f1` remains pending on remote host.
- **chrome_native_host_registration_absent**: Native Messaging host registration in browser environment is not performed or verified by unit test fixtures.
- **power_loss_crash_consistency_unverified**: While `ingest.py:148` calls `os.fsync`, hard system power loss resilience is not simulated in automated test suites.

---

## 35 Inventory Rows Summary

All 35 specified repository paths have been hashed and verified against head `16cea4d4bec0b10f6b591d6141641ed9698ab9f1` and base `7c7d3333bff3f48b3c5e353e93d2aa8c760f1b29`.
Canonical JSON representation of these 35 rows yields `inventorySha256: 1fa36c192d8da240f448e37b2e7c393b0cccc9822a9e0585c3bda93b2e783cf8`.
