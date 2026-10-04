# Capture, import and distill

Kura captures visible browser threads. Official account exports backfill chats
that were never opened. SBO keeps raw sources in `private/` and creates summary
stubs in `brain/_inbox/`. A stub is pending work, not a distilled memory.

## Supported inputs

| Input | Coverage | Intake |
|---|---|---|
| ChatGPT official JSON or sharded ZIP | Conversations supplied by the export | Existing ChatGPT handler |
| Claude JSON / JSONL | Conversations supplied by the export | Existing Claude handler |
| Kura v0.2.0 `conversation.md` | Visible captured thread; six Kura platforms | Kura handler |
| Gemini Takeout | Provider account archive | Retain privately; no verified Takeout parser yet |

Select the `Kura/` capture root, not your home directory. Discovery examines only
`<platform>/<folder>/conversation.md`, with a maximum of 10,000 captures per pass
and 64 MiB per file. Unknown schemas, source-host mismatches, ambiguous message
counts and unclosed fences stop that input. No link or media URL is fetched.

```powershell
./scripts/process-captures.ps1 -CaptureRoot 'D:/private-captures/Kura' `
  -BrainRoot 'D:/second-brain/brain' -PrivateRoot 'D:/second-brain/private' `
  -PythonExe './.venv/Scripts/python.exe'
```

Or use `sbo-ingest /selected/Kura --brain-root /brain --private-root /private
--mode agent`. The roots must not overlap. Keep the capture root outside the MCP
vault too: Kura captures are raw private material, even though they are Markdown.

## Repeat processing and recovery

Kura receipts live in `private/_distill/kura/`. Unchanged content is skipped.
Changed captures retain the previous private source revision before refreshing
the active copy. A curated brain note is preserved byte for byte; the receipt
marks `refresh_pending` for deliberate review. Source creation dates are left
unknown when the browser capture does not supply them.

A source ID joins an official export only when its platform, source URL and
Kura-prefixed ID agree exactly. Otherwise it stays in a Kura namespace. Capture
does not prove complete account coverage. Matching IDs also do not prove equal
branch coverage. Browser views are saved separately under private `kura-views/`
when the existing brain note refers to an official export; the official source
and the brain note's reference are preserved.

If a pass stops, fix the reported file and repeat the command. Completed Kura
items are skipped on retry. Receipts use atomic writes and cooperating-process
locks. Interrupted writes do not mark a capture complete. Do not delete locks
based on age. Restore malformed receipts from a private backup before retrying.

## Daily and weekly operation

Daily: use Kura's connected folder on supported open chats; run one processing
pass; distill a bounded batch of pending work relevant to active projects. Verify
the source, write a useful summary, then use `sbo-distill complete` to record it.
Agent mode does not call a model. `--mode api` explicitly enables paid summarization.

Weekly: backfill official exports when available, review changed-source receipts,
resolve duplicate identities, and review draft decisions before promotion. Check
that a real retrieval question finds the right approved note with its source.
Keep originals and unfinished work. Do not move all raw history into shared memory.

## Automation choice

The extension handles capture events; the local CLI handles ingestion. This needs
no always-on server. No new watcher, scheduled task or n8n workflow is installed by
this change. Existing paused jobs stay paused.

n8n can coordinate reminders or aggregate receipt counts after an explicit
deployment decision. Avoid sending transcript bodies, private paths or personal
titles into cloud execution logs. It adds no account-history access: the provider
export or a capture still has to exist. Use the existing estate tool plane and
one orchestrator for a workflow rather than adding another scheduler.

Provider export instructions: [ChatGPT](https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data),
[Claude](https://support.claude.com/en/articles/9450526-export-your-claude-data),
[Gemini](https://support.google.com/gemini/answer/16920332?hl=en).
