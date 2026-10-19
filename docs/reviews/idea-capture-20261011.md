# Independent source review: idea capture ingestion (PR18, issue 10)

> Source review of frankxai/second-brain-os idea capture intake implementation.

## Overview

- **Repository**: `frankxai/second-brain-os`
- **Head commit**: `43deb101c740680c4618c0114171d57883ddca23`
- **PR16 base commit**: `7c7d3333bff3f48b3c5e353e93d2aa8c760f1b29`
- **Adapter parent commit**: `a9757eb600c2d2b8e62635211b7ef3f5a6389cbe`
- **Inventory SHA256**: `893187ef33e4cebf43088b03f50d752ac71cb332592128d75e754678ca0021fa`
- **Overall verdict**: `FAIL`

The implementation satisfies strict schema validation, private vault isolation, idempotent dual-write receipt management, bounded reads, and archive search integration. However, the overall verdict is `FAIL` due to an automated test failure in `tests/test_idea_capture.py` (`test_capture_refuses_link_before_read_or_lock[brain-note]`), where a symlink boundary check raises a path escape exception before reaching the explicit symlink validation check.

---

## Source inventory and bindings

30 files were evaluated at frozen head `43deb101c740680c4618c0114171d57883ddca23`. The combined sorted sources JSON hash matches `893187ef33e4cebf43088b03f50d752ac71cb332592128d75e754678ca0021fa`.

Six files changed relative to PR16 base `7c7d3333bff3f48b3c5e353e93d2aa8c760f1b29`:
1. `docs/idea-capture.md` (new documentation)
2. `src/sbo_ingestion/archive_search.py`
3. `src/sbo_ingestion/handlers/idea_capture.py` (new module)
4. `src/sbo_ingestion/ingest.py`
5. `tests/test_archive_search.py`
6. `tests/test_idea_capture.py` (new test suite)

---

## Category assessment

| Category | Status | Summary |
| --- | --- | --- |
| Fidelity | PASS | Strict five-field schema validation, <=8 MiB size bounds, string tags with duplicate/whitespace retention, integer version enforcement, and plain UTF-8/BOM byte retention. |
| Privacy and provenance | PASS | Private fields (`rawText`, `tags`, `source`, `sourceRef`) remain strictly in the private vault. Shared brain notes contain generic safe titles, `status: needs-summary`, `trust: untrusted-data`, and actor `captured-unverified`. |
| Corruption and idempotency | PASS | Namespaced semantic identity hashing, byte variant retention under `private/_distill/idea-capture/variants/`, receipt integrity validation, and refusal to overwrite conflicting bytes. |
| Atomic, locks, and path safety | FAIL | Symlink and traversal guards exist in `_assert_capture_path`, but `test_capture_refuses_link_before_read_or_lock[brain-note]` fails due to an exception message mismatch when `_assert_descendant` resolves symlinks pointing outside the vault root. |
| Indexing and promotion | PASS | `_capture_brain_paths` bounds reads on brain notes, locates promoted notes outside the inbox using `conversation_id`, and builds metadata-only `_INDEX.md`. |
| Ordinary exports | PASS | All existing ingestion formats (`claude.ai`, `chatgpt`, `kura`) pass all unit and integration tests without regressions. |
| Retrieval | PASS | Archive search indexes brain notes, suppresses content excerpts for pending notes (`review: metadata-only`), and enforces generation-bound cursor markers. |
| Claim limits | PASS | Documentation in `docs/idea-capture.md` explicitly qualifies kernel/airgap boundaries, multi-process safety, power-loss durability, and path-convention limits. |

---

## Evaluation details

### 1. Fidelity (PASS)
- Schema validation in `src/sbo_ingestion/handlers/idea_capture.py` enforces exact five expected fields (`version`, `rawText`, `tags`, `source`, `sourceRef`).
- `version` must be integer `1` (booleans and strings rejected).
- `rawText` and `source` must be nonblank strings.
- `tags` must be a string; lists or objects are rejected before writes.
- `sourceRef` is required and must be `null` or a nonblank string.
- Input size is bounded to <= 8 MiB (8,388,608 bytes) via `stat().st_size` and bounded read limits.
- Exact raw input bytes (plain UTF-8 or leading BOM) are retained in private storage without modification.

### 2. Privacy and provenance (PASS)
- Private content (`rawText`, `tags`, `source`, `sourceRef`) is written exclusively to `private/chat-history/idea-capture/`.
- Shared brain inbox notes in `brain/_inbox/idea-capture/` contain generic titles ("Captured Idea"), `status: needs-summary`, and `trust: untrusted-data`.
- Captured message sender is attributed as `captured-unverified`.
- No network requests, source URL fetching, auto-resume attempts, or browser protocol expansions are initiated.

### 3. Corruption and idempotency (PASS)
- Hashing computes a namespaced semantic identity using normalized canonical JSON keys.
- Idempotent re-ingestion reuses existing receipts without duplicating brain notes or spending model tokens.
- Byte variants (such as key reordering, whitespace adjustments, or BOM additions) are preserved under `private/_distill/idea-capture/variants/<uuid>/<hash>.json`.
- `_atomic_write_bytes` verifies existing bytes and raises `FileExistsError` if conflicting bytes exist for the same target path.

### 4. Atomic, locks, and path safety (FAIL)
- Path traversal (`..`) and symlink detection are enforced in `_assert_capture_path`.
- Exclusive lock files (`.lock`) wrap receipt updates.
- **Defect**: `tests/test_idea_capture.py::test_capture_refuses_link_before_read_or_lock[brain-note]` fails during automated test execution. When `_assert_capture_path` processes a symlink pointing outside `brain_root`, `_assert_descendant` calls `path.resolve().is_relative_to(root.resolve())`, which detects that the resolved path escapes `brain_root` and raises `ValueError("Idea capture path escapes its boundary")`. The test expects an exception matching regex `"symlink"`.

### 5. Indexing and promotion (PASS)
- `_capture_brain_paths` scans `brain_root` for `.md` files, bounding each file read to <= 8 MiB.
- Notes moved out of the inbox (promoted) are matched by `conversation_id`, preventing duplicate creation upon re-ingestion.
- A metadata-only corpus index (`_INDEX.md`) is maintained in `brain/_inbox/idea-capture/`.

### 6. Ordinary exports (PASS)
- All existing formats (`claude.ai`, `chatgpt`, `kura`) maintain existing behavior and test coverage.
- Full test suite execution across 173 test cases in other test modules passed without errors.

### 7. Retrieval (PASS)
- `src/sbo_ingestion/archive_search.py` indexes brain notes and stores cache in `_meta/kura-archive-index.json`.
- Unsummarized/pending notes (`status: needs-summary`) return `review: "metadata-only"` with empty excerpts, preventing unreviewed private content from leaking.
- Search cursors are bound to index generation hashes.

### 8. Claim limits (PASS)
- `docs/idea-capture.md` accurately documents system boundaries.
- The documentation explicitly notes that intake does not establish kernel-enforced sandboxing, power-loss durability, multi-process safety, or native browser protocol installation.

---

## Concrete defects and reproduction

### Defect 1: Exception message mismatch on symlink boundary check
- **File**: `tests/test_idea_capture.py`
- **Line**: 547
- **Reproduction**:
  ```bash
  pytest tests/test_idea_capture.py -k test_capture_refuses_link_before_read_or_lock
  ```
- **Error output**:
  ```text
  E AssertionError: Regex pattern did not match.
  E   Expected regex: 'symlink'
  E   Actual message: 'Idea capture path escapes its boundary'
  ```
- **Impact**: Fails the repository automated test suite.
- **Root cause**: In `src/sbo_ingestion/ingest.py`, `_assert_capture_path` calls `_assert_descendant(path, root)` before checking `candidate.is_symlink()`. `_assert_descendant` calls `path.resolve()`, which resolves the symlink target. If the symlink points outside `root`, `_assert_descendant` fails with `"Idea capture path escapes its boundary"` before the loop checking `is_symlink()` is reached.

---

## Executed checks versus source assertions

1. **Executed checks**:
   - `pytest`: 217 passed, 1 failed (`test_capture_refuses_link_before_read_or_lock[brain-note]`), 1 skipped (Windows symlinks).
   - `inventorySha256`: Computed SHA256 of sorted 30 paths JSON matches `893187ef33e4cebf43088b03f50d752ac71cb332592128d75e754678ca0021fa`.

2. **Source assertions**:
   - Model network calls are guarded; agent mode bypasses API token spending.
   - Filesystem atomicity relies on POSIX `os.link` hardlinks and exclusive file lock files.

---

## Remaining gaps and recommendations

1. **Fix exception order or test regex**: Either update `_assert_capture_path` to check `path.is_symlink()` prior to resolving descendant boundaries, or align the test expectation regex in `tests/test_idea_capture.py` to accept boundary escape errors for symlinks targeting external locations.
2. **Malformed brain note handling during indexing**: `_capture_brain_paths` fails closed when encountering any malformed `.md` file in `brain_root`. Ensure users are aware that damaged brain notes must be repaired before new captures can be indexed.
