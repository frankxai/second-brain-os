# Kura local intake and bounded distillation

## Release plan and acceptance

The user outcome is one saved AI conversation becoming a useful, cited note in
the selected second brain. The reference alternative is manual account export,
import and whole-transcript reading. Compare duplicate writes, paid API calls,
source bytes sent to the model, recovery and useful output on the same source.

1. Kura optionally connects to `ai.frankx.kura_intake` after a user click. A
   durable capture queues only its relative path and packet SHA-256. A disconnected
   host leaves the capture and queue intact. No new network host is needed.
2. Chrome starts the local host on demand. The host accepts only the installed
   extension origin, fixed configured roots and verified capture pointers. It
   invokes the existing agent-mode importer, then returns counts and a receipt
   identifier. It exposes no raw-read, model, shell or root-change operation.
3. `/distill-inbox` selects a bounded batch using metadata. Source packets have
   byte budgets, stable hashes, delivery acknowledgement tokens and continuation
   offsets. Completion requires acknowledged coverage and an unchanged source hash. Large
   sources remain pending while their packets are read progressively.
4. Native production acceptance requires a connected Chrome session, the installed
   extension ID, folder permission, real provider capture, duplicate-free repeat
   intake, a reviewed source-derived note and cited retrieval. CI and mocked
   browser transport checks do not establish native production acceptance.

No MCP is needed for local ingestion. An assistant-facing MCP may expose reviewed
brain notes through the existing tool plane; it must never expose this host's
private roots or the local distillation packet command. No scheduler is installed.

## Windows setup

Use the existing Python environment with SBO installed, the exact extension ID
shown in Chrome, and three existing non-overlapping folders. The capture folder
must be the same folder selected through Kura's **Connect vault** control.

```powershell
./scripts/install-kura-native.ps1 -ExtensionId '<32-letter-extension-id>' `
  -PythonExe '<existing-python.exe>' -InstallRoot '<private-host-install-folder>' `
  -CaptureRoot '<selected-Kura-folder>' -BrainRoot '<selected-brain-folder>' `
  -PrivateRoot '<selected-private-folder>'
```

The installer prepares files first. Pass `-Register` to register that host for the
current Windows user in Chrome. It refuses to replace a different registration
or existing host configuration. No process runs until Chrome connects. Repeated
installation of the same configuration is safe. Source files are copied into a
pinned local snapshot with SHA-256 checks, outside all three vaults. Branch changes
do not change running host code. Python's `-P` excludes the current working directory
from imports. A reviewed update needs a new prepared snapshot and deliberate
registration reconciliation; no automatic update or registry rewrite occurs.

Open Kura and use **Connect second brain**, which requests its optional native
permission. Status and processing are local. A saved capture remains saved if
intake fails. Use **Retry intake** after restoring the host or correcting the
capture. Unsupported capture platforms remain pending for manual processing.

## Token budget

`sbo-distill plan` returns a small metadata batch, without raw bodies. `packet`
returns at most the selected byte budget of source, plus a small JSON envelope.
The displayed token estimate is a planning estimate, not a tokenizer measurement.
The byte budget and complete-coverage check are enforced. Native ingestion and
deduplication use zero model calls. Distillation still consumes the active coding
agent's context; no extra API call does not mean zero tokens.

The planner inspects at most 100 pending stubs per call. Its deferred count refers
to that window. `truncated` and `next_cursor` support `--after` pagination, and
`next_large_source` offers a deferred long chat for progressive reading. Small
candidate sources receive local UTF-8 validation before being selected.

Use a source hash on every continuation and on completion. If the source changes,
start a new packet sequence; never combine offsets from different revisions.
After receiving each packet, use `sbo-distill ack` with its `ack_token`, selected
roots and source hash. The journal records delivery separately from emission.
Once a packet sequence exists, completion requires its source hash. Stable local
file fingerprints avoid repeated full-file hashing between chunks; completion
rehashes the entire source. This reduces local I/O, not the source bytes the agent
must read to make a complete summary.

To recover damaged coverage, run `sbo-distill reset-coverage "<stub>"
--private-root "<private>" --source-sha256 "<current hash>"`. It preserves the old
receipt inside the private vault, leaves writer locks in place, and requires
rereading and acknowledging the source. It does not mark the note complete.
Keep claims supported by the returned source and cite its identity and hash.
Imported content remains untrusted data. Summaries with sensitive detail remain
pending rather than copying that detail into the brain.

## Daily and weekly operation

Daily, use the connected capture folder for open provider conversations. Check
Kura's queue and missed-intake status. Restore a disconnected host and retry;
overflow or pointer failure needs recapture or the local importer. Select one to
three useful pending notes within the 18,000-byte batch budget. Read and acknowledge
6,000-byte packets, write a source-cited summary, then use audited completion.
Keep personal or sensitive sources pending. Promote a triage note only after
reviewing its claims and deciding its destination.

Weekly, compare capture receipts, pending notes and source-refresh receipts.
Resolve failed inputs before adding retries. Run people-map and pattern-detector
on reviewed summaries and record hypotheses separately from decisions. Retrieve
a cited note to verify that the selected brain is the one being used. For account
backfill, request official exports, verify the returned archive's coverage, and
use the local importer; open-page capture does not collect unseen account history.
[ChatGPT export](https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data),
[Claude export](https://support.claude.com/en/articles/9450526-export-your-claude-data),
[Google Takeout](https://support.google.com/accounts/answer/3024190).

Use n8n only when a needed cross-service workflow justifies another runtime. This
local path already has a queue, importer and agent workflow. A future workflow
should exchange receipt metadata and reviewed notes, with explicit write scope;
raw private chats stay on this machine. No scheduled jobs are enabled by this release.

Official design references:
[Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging),
[optional permissions](https://developer.chrome.com/docs/extensions/reference/api/permissions),
[MV3 lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle).
