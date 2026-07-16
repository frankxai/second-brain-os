#!/usr/bin/env python3
"""Product copy of Time OS sole append writer. Prefer runtime:
C:/Users/frank/.starlight/time-os/time_os_append.py
"""
from __future__ import annotations

import runpy
from pathlib import Path

RUNTIME = Path.home() / ".starlight" / "time-os" / "time_os_append.py"
if RUNTIME.is_file():
    runpy.run_path(str(RUNTIME), run_name="__main__")
else:
    # inline fallback mirrors runtime v1.1
    import argparse, json, os, sys, uuid
    from datetime import datetime, timezone

    BLOCKS = Path(os.environ.get("STARLIGHT_TIME_OS", str(Path.home() / ".starlight" / "time-os"))) / "blocks"

    def main() -> int:
        p = argparse.ArgumentParser()
        p.add_argument("--actor", required=True)
        p.add_argument("--kind", required=True)
        p.add_argument("--task", required=True)
        p.add_argument("--start", required=True)
        p.add_argument("--end", required=True)
        p.add_argument("--lane", default="other")
        p.add_argument("--class-name", dest="class_name", default="unknown")
        p.add_argument("--status", default="confirmed")
        p.add_argument("--confidence", type=float, default=1.0)
        p.add_argument("--source", default="human")
        p.add_argument("--session", default="")
        p.add_argument("--repo", default="")
        p.add_argument("--run-id", default="")
        p.add_argument("--outcome-score", type=int, default=0)
        p.add_argument("--evidence", action="append", default=[])
        p.add_argument("--notes", default="")
        p.add_argument("--confirmed-by", default="")
        p.add_argument("--day", default="")
        a = p.parse_args()
        now = datetime.now(timezone.utc).isoformat()
        confirmed = a.status in ("confirmed", "shipped") and a.confidence >= 0.85 and a.status != "proposed"
        row = {k: v for k, v in {
            "v": 1, "id": str(uuid.uuid4()), "actor": a.actor, "kind": a.kind, "task": a.task,
            "lane": a.lane, "class": a.class_name, "start": a.start, "end": a.end, "status": a.status,
            "confidence": a.confidence, "source": a.source, "session": a.session or None,
            "repo": a.repo or None, "run_id": a.run_id or None,
            "outcome_score": a.outcome_score or None, "evidence_links": a.evidence,
            "calendar_synced": False, "confirmed": confirmed,
            "confirmed_by": a.confirmed_by or (a.actor if confirmed else None),
            "confirmed_at": now if confirmed else None, "notes": a.notes,
        }.items() if v is not None}
        day = a.day or datetime.fromisoformat(a.start.replace("Z", "+00:00")).date().isoformat()
        BLOCKS.mkdir(parents=True, exist_ok=True)
        path = BLOCKS / f"{day}.ndjson"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps({"status": "appended", "path": str(path), "id": row["id"]}))
        return 0

    raise SystemExit(main())
