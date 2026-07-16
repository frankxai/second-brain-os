#!/usr/bin/env python3
"""Sole append writer for Time OS blocks (v1.2 founder performance fields)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

RUNTIME = Path(os.environ.get("STARLIGHT_TIME_OS", str(Path.home() / ".starlight" / "time-os")))
BLOCKS = RUNTIME / "blocks"


def main() -> int:
    p = argparse.ArgumentParser(description="Append Time OS block row (sole writer path)")
    p.add_argument("--actor", required=True)
    p.add_argument("--kind", choices=["human", "agent", "mixed"], required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--lane", default="other")
    p.add_argument("--class-name", dest="class_name", default="unknown")
    p.add_argument(
        "--status",
        default="confirmed",
        choices=["proposed", "confirmed", "shipped", "in-progress", "blocked", "abandoned", "corrected"],
    )
    p.add_argument("--confidence", type=float, default=1.0)
    p.add_argument(
        "--source",
        default="human",
        choices=["calendar", "ledger-hook", "session-infer", "human", "weekly-swarm", "other"],
    )
    p.add_argument("--session", default="")
    p.add_argument("--repo", default="")
    p.add_argument("--run-id", default="")
    p.add_argument("--outcome-score", type=int, default=0)
    p.add_argument("--output-quality", type=int, default=0)
    p.add_argument("--focus-score", type=int, default=0)
    p.add_argument("--deep-work", action="store_true")
    p.add_argument(
        "--place-mode",
        default="unknown",
        choices=["wfh", "cowork", "office", "cafe", "travel", "event", "home_life", "gym", "unknown"],
    )
    p.add_argument("--environment", action="append", default=[], help="repeatable tag")
    p.add_argument("--people", action="append", default=[], help="repeatable person id/name")
    p.add_argument("--energy", default="unknown", choices=["H", "M", "L", "unknown"])
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--notes", default="")
    p.add_argument("--confirmed-by", default="")
    p.add_argument("--day", default="")
    args = p.parse_args()

    now = datetime.now(timezone.utc).isoformat()
    confirmed = args.status in ("confirmed", "shipped") and args.confidence >= 0.85
    if args.status == "proposed":
        confirmed = False

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
        "run_id": args.run_id or None,
        "outcome_score": args.outcome_score or None,
        "output_quality": args.output_quality or None,
        "focus_score": args.focus_score or None,
        "deep_work": bool(args.deep_work),
        "place_mode": args.place_mode,
        "environment": args.environment or None,
        "people": args.people or None,
        "evidence_links": args.evidence,
        "energy": args.energy,
        "calendar_synced": False,
        "confirmed": confirmed,
        "confirmed_by": args.confirmed_by
        or (args.actor if confirmed and args.source != "session-infer" else None),
        "confirmed_at": now if confirmed else None,
        "notes": args.notes or None,
    }
    row = {k: v for k, v in row.items() if v is not None}

    day = args.day
    if not day:
        try:
            day = datetime.fromisoformat(args.start.replace("Z", "+00:00")).date().isoformat()
        except Exception:
            day = datetime.now(timezone.utc).date().isoformat()

    BLOCKS.mkdir(parents=True, exist_ok=True)
    path = BLOCKS / f"{day}.ndjson"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"status": "appended", "path": str(path), "id": row["id"], "confirmed": confirmed}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
