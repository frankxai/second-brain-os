# Cross-CLI — Time & Week OS

> Drop into AGENTS.md / CLAUDE.md / .cursor rules for any coding agent that touches Frank's estate.

## Mandatory read

1. `second-brain-os/docs/time-and-week-os.md`
2. Live: `C:/Users/frank/second-brain/brain/_meta/time-os/README.md`
3. Contract: `C:/Users/frank/second-brain/brain/_agents/time-week-os.md`

## After any work block ≥15 minutes

Append a ledger row (prefer script):

```bash
python path/to/second-brain-os/scripts/time_os_append.py \
  --actor <claude-code|codex|hermes|opencode> \
  --kind agent \
  --task "<one line>" \
  --start <ISO> --end <ISO> \
  --lane <arcanea|frankx|gencreator|starlight-ops|...> \
  --class-name <ship|leverage|maintenance|...> \
  --status shipped \
  --source ledger-hook \
  --repo <repo> \
  --outcome-score 0-5 \
  --evidence <url-or-file>
```

Also append AgentOps when available (`starlight-mission-control/hooks/`).

## Forbidden

- Editing `second-brain/brain/notes|projects|_capture`
- Touching `second-brain/private`
- Creating events on Human Primary Google Calendar without explicit approve
- Broad filesystem search from `C:\` or home (Phone Link ban)

## Weekly

Do not invent a second weekly review format. Contribute evidence into Time & Week OS packet or Palace inbox only.
