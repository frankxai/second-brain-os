# Capture to recall review — PR18 / issue10

Independent review report for second-brain-os draft PR18 (issue10).
Frozen head: `b0706e085de76d29f57305dde62e17c7bd72a710`
Base commit: `7c7d3333bff3f48b3c5e353e93d2aa8c760f1b29` (PR16 base)
Inventory SHA-256: `6cc40144e39c0cd1b4271bb6c8d88d4646141c1c1554c2331e4f9a9ddf2cc125`

## Executive summary

This report provides an independent review of the idea-capture ingestion and packet distillation workflow in second-brain-os. The review evaluates the resolution at commit `b070` for the source-coverage packet reader gap identified at `8f`. The changes enable packet-based source coverage distillation and completion for raw idea-capture JSON files without opening generic JSON files or leaking unverified private source locators into shared notes.

## Prior review context and regression status

Prior review 6512755636455621062 at commit `43deb101` recorded a FAIL due to exact symlink error message wording expectations when boundary refusal prevented file reads. At commit `8f8e44d`, the test assertion was updated to accept either refusal message while continuing to forbid opening symlink targets and verifying unchanged destinations. The underlying runtime remains unchanged.

Prior matrix 38137411709 recorded 218 passed and 1 skipped job across nine matrix configurations. The existing FAIL status is preserved in the inventory to maintain strict historical continuity and avoid over-certifying head before hosted matrix execution finishes.

## Gap reproduction at 8f and resolution at b070

At commit `8f`, capture JSON files referenced by brain stubs were refused by `source_for_stub` in `src/sbo_ingestion/distill_packet.py` because the function strictly required file paths ending in `.md`. This broke source-hashed packet distillation and stub completion for idea-capture inputs.

Commit `b070` introduces scoped JSON compatibility within `source_for_stub`. The reader permits JSON source references only when all of the following conditions are satisfied:
1. Path location: `len(parts) == 3` and `parts[:2] == ["chat-history", "idea-capture"]`.
2. Stub metadata: frontmatter contains `source: idea-capture`.
3. Identity formatting: `conversation_id` matches `idea-[0-9a-f]{16}`.
4. Filename format: filename matches `YYYY-MM-DD-idea-{id}.json`.
5. Path integrity: zero symlink components along the resolved path within `private/`.
6. Schema and semantic verification: `idea_capture.read_and_validate_packet` validates schema version 1, and the computed semantic identity `idea-{hash[:16]}` matches the stub `conversation_id`.

Generic JSON files outside this path pattern remain rejected. Original UTF-8 BOM and raw bytes are preserved. Ordinary Markdown references operate without modification.

## Root evidence and test suite execution

Root test suite execution in this environment yielded 223 passed tests and 1 skipped test (Windows-only Chrome installer test on Linux). The 16 focused tests in `tests/test_distill_packet.py` and `tests/test_idea_capture_distillation.py` passed:

1. Packet streaming reconstructs exact original raw bytes across chunk boundaries.
2. Premature stub completion without full acknowledged byte coverage is refused.
3. Forged capture references fail closed across four distinct mutation vectors:
   - `wrong-source`: frontmatter source set to non-capture value.
   - `wrong-identity`: mismatched conversation_id hash.
   - `wrong-folder`: private_file path changed outside `chat-history/idea-capture/`.
   - `changed-body`: mutated capture JSON body after stub generation.
4. Citation search returns the safe brain stub relative path without locator leaks.

An AST inspection confirms that 12 other function signatures in `distill_packet.py` remain structurally unchanged, receiving code formatting updates only.

## Detailed finding analysis

### 1. Fidelity, privacy, and provenance
Raw captured JSON content and BOM bytes are stored without modification under `private/chat-history/idea-capture/`. User-supplied `source` strings and `sourceRef` locators remain unverified data. Shared stubs in `brain/_inbox/idea-capture/` and corpus indexes (`_INDEX.md`) contain safe titles and `status: needs-summary` flags without private locator interpolation.

### 2. Variant handling and idempotency
Key reordering, whitespace variations, and BOM additions map to identical semantic identities (`idea-{hash[:16]}`). Re-ingesting byte variants preserves existing brain notes while storing raw variants under `private/_distill/idea-capture/variants/`.

### 3. Bounded paths, locks, and atomicity
Private index operations acquire exclusive locks (`private/_distill/idea-capture/index.lock`). Publication uses temporary files and create-only hard links. Bounded file size limits are enforced: 8 MiB for capture packets, 64 MiB for source files, 128 KiB for receipts, and 4 MiB for brain stubs.

### 4. Packet coverage, completion, and recall
Distillation packets track delivered byte intervals using version 2 receipts. `require_complete_coverage` verifies interval coverage matches `[[0, size]]` and validates source SHA-256 before `complete_stub` permits promotion. Byte delivery acknowledgment verifies chunk transport only and does not measure summary quality or semantic comprehension.

## System limits and retained gaps

1. **OS race and power-loss durability**: Atomic file writes flush to OS disk buffers without explicit `fsync` system calls. Sudden power loss during file publication can leave incomplete files.
2. **Unverified identity**: `source` and `sourceRef` values are untrusted inputs. Message identity is marked `captured-unverified` with no inferred speaker role.
3. **Native browser consumer and hosted matrix**: Installed native host launcher scripts and hook files remain untouched in this PR. Hosted CI matrix certification is pending for this head.

## Source inventory and findings index

The companion file `docs/reviews/capture-to-recall-20261011.json` provides the complete machine-readable source inventory of 35 files (inventory SHA-256 `6cc40144e39c0cd1b4271bb6c8d88d4646141c1c1554c2331e4f9a9ddf2cc125`) alongside structured PASS, WARN, and FAIL findings.
