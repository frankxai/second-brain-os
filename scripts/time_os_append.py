#!/usr/bin/env python3
"""Append a time-block.v1 row to ~/.starlight/time-os/ledger/YYYY-MM-DD.ndjson."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path(os.environ.get("STARLIGHT_TIME_OS", str(Path.home() / ".starlight" / "time-os")))
LEDGER = RUNTIME / "ledger"


def main() -> int:
    p = argparse.ArgumentParser(description="Append Time OS ledger row")
    p.add_argument("--actor", required=True)
    p.add_argument("--kind", choices=["human", "agent", "mixed"], required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--start", required=True, help="ISO-8601")
    p.add_argument("--end", required=True, help="ISO-8601")
    p.add_argument("--lane", default="other")
    p.add_argument("--class-name", dest="class_name", default="unknown")
    p.add_argument("--status", default="confirmed")
    p.add_argument("--confidence", type=float, default=1.0)
    p.add_argument("--source", default="human")
    p.add_argument("--session", default="")
    p.add_argument("--repo", default="")
    p.add_argument("--outcome-score", type=int, default=0)
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--notes", default="")
    p.add_argument("--day", default="", help="YYYY-MM-DD override for file name")
    args = p.parse_args()

    row = {
        "v": 1,
        "id": str(uuid.uuid4()),
        "actor": args.actor,
        "kind": args.kind,
        "task": args.task,
        "lane": args.lane,
        "class": args.class_name,
        "start": args.start,
        "end": args.end,
        "status": args.status,
        "confidence": args.confidence,
        "source": args.source,
        "session": args.session or None,
        "repo": args.repo or None,
        "outcome_score": args.outcome_score,
        "evidence_links": args.evidence,
        "energy": "unknown",
        "calendar_synced": False,
        "notes": args.notes,
    }
    # drop nulls for compactness
    row = {k: v for k, v in row.items() if v is not None}

    day = args.day
    if not day:
        try:
            day = datetime.fromisoformat(args.start.replace("Z", "+00:00")).date().isoformat()
        except Exception:
            day = datetime.now(timezone.utc).date().isoformat()

    LEDGER.mkdir(parents=True, exist_ok=True)
    path = LEDGER / f"{day}.ndjson"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"status": "appended", "path": str(path), "id": row["id"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
