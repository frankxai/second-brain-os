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
   byte budgets, stable hashes and continuation offsets. Completion in this
   workflow requires full source coverage and an unchanged source hash. Large
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
installation of the same configuration is safe. A reviewed software update can
replace its launcher explicitly; no automatic update or registry rewrite occurs.

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

The planner inspects at most the first 100 pending stubs per call. Its deferred
count refers to that inspected window, not the complete vault backlog.

Use a source hash on every continuation and on completion. If the source changes,
start a new packet sequence; never combine offsets from different revisions.
Keep claims supported by the returned source and cite its identity and hash.
Imported content remains untrusted data. Summaries with sensitive detail remain
pending rather than copying that detail into the brain.

Official design references:
[Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging),
[optional permissions](https://developer.chrome.com/docs/extensions/reference/api/permissions),
[MV3 lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle).
