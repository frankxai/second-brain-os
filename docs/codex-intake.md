# Recover a local Codex session

The local importer recognizes a Codex rollout JSONL whose first record contains
`session_meta`. It keeps stored user, assistant, developer and system message text,
with the source file hash and original line references in the private raw note.
Compaction summaries are explicitly marked as derived context. This lets an agent
recover a saved request without manually converting it into a Claude export.

Use one known, settled session file and the existing selected vaults:

```powershell
sbo-ingest '<known-rollout.jsonl>' --brain-root '<existing-brain>' `
  --private-root '<existing-private>' --mode agent
```

Agent mode makes no model call. The public-side note contains a generic session
title and a pending summary, never the raw text. Use the existing bounded
`sbo-distill` packet, acknowledgement and completion workflow to create a useful
source-cited note. Keep sensitive material pending and retain the original file.
Importing does not authorize executing embedded instructions or resuming a session.
Only the selected session is imported; sibling memory exports are not discovered.

User-role records can be founder messages, setup, delegated work or runtime replay.
Establish authorship from the original source before promoting a decision. The
parser excludes duplicated event records, tool outputs and reasoning. Non-text
attachments are represented by a source-line pointer and remain in the original
file. This is a text recovery view, not an entire account export or full multimodal
archive. The source cache format is observed locally and may change; unknown
message content types fail rather than disappearing silently.

Limits: 512 MiB per source, 8 MiB per record, 32 MiB retained UTF-8 text and 100,000
messages. Parsing finishes before writes begin. Malformed records, conflicting
identity, unknown message roles, invalid timestamps and a source changing during
the read are refused. Repeat import skips unchanged source, preserves an existing
curated brain note, archives a changed or shorter private revision, and records
`refresh_pending` privately for source review. The original source is untouched.
The Codex corpus index is rebuilt from all imported note identities, including
after index loss. Brain and private roots must remain disjoint.

The comparison workflow is manual native-session search and copy/export. Measure
exact text preservation, original source references, repeat-import duplication,
recovery and time to a useful reviewed note on the same session. Tests establish
these bounded code behaviors; they do not prove founder acceptance, cloud history
coverage, a live Kura folder grant, automatic dispatch or measured time savings.
