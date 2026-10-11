# Idea capture format and ingestion

> Technical guide for capturing idea packets into Second Brain OS.

## Overview

The `idea-capture` format ingests single, structured JSON capture packets into the Second Brain OS two-vault architecture. The capture packet is stored privately with exact byte fidelity, while a generic, metadata-only stub lands in the brain vault for later distillation.

## Packet schema

An idea capture packet must be a single regular file of at most 8 MiB with UTF-8 encoding (plain or leading UTF-8 BOM). It must contain a JSON object with exactly five fields:

| Field | Type | Description |
| --- | --- | --- |
| `version` | integer `1` | Must be integer 1 (booleans rejected). |
| `rawText` | nonblank string | Raw captured text content. |
| `tags` | string | String tags (exact whitespace, newlines, and duplicates retained; lists rejected). |
| `source` | nonblank string | User-supplied, unverified source label. |
| `sourceRef` | string or null | Required key; nullable, unverified source locator. |

### Example fixture

```json
{
  "version": 1,
  "rawText": "  Synthetic café 漢字 🧠\r\n  ",
  "tags": "  first\r\nsecond, duplicate, duplicate  ",
  "source": "PRIVATE_SOURCE_SENTINEL",
  "sourceRef": "PRIVATE_LOCATOR_SENTINEL"
}
```

## Private and shared output

1. **Private raw content**: `rawText`, `tags`, `source` and `sourceRef` remain in the original JSON bytes under `private/chat-history/idea-capture/`. The original input filename is not used in shared notes. The importer does not change MCP configuration or create a kernel-enforced privacy boundary.
2. **Generic brain stubs**: Shared output in `brain/_inbox/idea-capture/` and corpus indexes (`_INDEX.md`) contain only generic, safe titles and status flags (`status: needs-summary`). Private source strings or locator sentinels are never interpolated into shared notes or error logs.
3. **Agent mode only**: Processing idea capture packets requires agent mode. Summaries are produced during human-initiated distillation sessions using `/distill-inbox`.

## Ingestion CLI and API

### CLI usage

```bash
sbo-ingest /path/to/capture.json \
  --brain-root /path/to/brain \
  --private-root /path/to/private \
  --format idea-capture \
  --mode agent
```

### Python API usage

```python
from pathlib import Path
from sbo_ingestion.ingest import ingest

results = ingest(
    Path("/path/to/capture.json"),
    brain_root=Path("/path/to/brain"),
    private_root=Path("/path/to/private"),
    format="idea-capture",
    mode="agent",
)
```

## Idempotency and variants

Idea capture ingests calculate namespaced semantic identity hashes from the normalized packet fields. Re-ingesting an identical packet or a byte variant (such as reordered JSON keys, whitespace adjustments, or BOM additions) maintains the existing brain note while preserving raw byte variants in `private/_distill/idea-capture/variants/`.

Each selected import rebuilds the complete idea-capture corpus index under a private index lock. Index rows use generic identities and imported dates; they do not copy a captured body or source locator. Captured message identity is `captured-unverified`, with no inferred human or assistant author.

## Recovery and limits

Original and variant JSON bytes are published with a create-only hard link from a flushed temporary file in the same directory. An interrupted retry can reuse identical bytes; different existing bytes cause a refusal and remain intact. Filesystems that do not support this publication method fail without an overwrite fallback. Keep the original input and any conflicting files for review.

Malformed receipt fields and invalid decoded Unicode refuse with controlled errors. The importer does not establish power-loss durability, multi-process or path-swap safety, native browser installation, private-vault activation or creator acceptance. These require separate receiving and runtime verification.


Saved-packet retries enforce the same 8 MiB bound on raw originals, variants and private receipts before opening them. Capture indexing also bounds each brain Markdown read and refuses symlink paths, duplicate capture identities and malformed notes. This can stop intake when unrelated existing brain notes are malformed or exceed 8 MiB; repair those notes explicitly and retry. Ordinary chat/Kura ingestion keeps its existing behavior. Metadata-only intake preserves source content privately and still requires deliberate distillation before useful semantic recall.


## Read and distill a selected capture

The local source-packet reader accepts the original capture JSON when the brain stub is marked `source: idea-capture`, its path is under `chat-history/idea-capture/`, and the filename, validated packet and stub agree on the semantic identity. Generic JSON references remain rejected. UTF-8/BOM bytes and string tags are preserved; source labels and locators remain unverified data.

Use the existing `sbo-distill packet`, `ack` and `complete` workflow with the source hash. Read and acknowledge every issued packet before completion, write a faithful draft synthesis deliberately, and keep human triage open. Acknowledgment proves delivered byte coverage, not comprehension or faithful meaning. Source changes refuse completion. Cited search can then retrieve the draft through the selected brain root without opening the private source. Select `platform="idea-capture"` to search capture notes under their actual source identity. Installed native-consumer acceptance remains open; the native ingestion protocol is unchanged.
