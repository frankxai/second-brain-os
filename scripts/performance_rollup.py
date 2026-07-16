#!/usr/bin/env python3
"""Roll up Time OS blocks into founder performance analytics (local, no network)."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RUNTIME = Path.home() / ".starlight" / "time-os"
BLOCKS = RUNTIME / "blocks"


def parse_dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def hours(row: dict) -> float:
    a, b = parse_dt(row.get("start", "")), parse_dt(row.get("end", ""))
    if not a or not b:
        return 0.0
    return max(0.0, (b - a).total_seconds() / 3600.0)


def load_days(n_days: int = 14) -> list[dict]:
    rows: list[dict] = []
    if not BLOCKS.exists():
        return rows
    files = sorted(BLOCKS.glob("*.ndjson"))[-max(n_days, 1) :]
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def bucket(rows: list[dict], key: str) -> dict:
    h = defaultdict(float)
    impact = defaultdict(float)
    quality = defaultdict(list)
    focus = defaultdict(list)
    for r in rows:
        if r.get("status") == "proposed":
            continue
        k = r.get(key) or "unknown"
        if isinstance(k, list):
            keys = k or ["unknown"]
        else:
            keys = [k]
        hrs = hours(r)
        oc = r.get("outcome_score") or 0
        oq = r.get("output_quality")
        fs = r.get("focus_score")
        for kk in keys:
            h[kk] += hrs
            impact[kk] += hrs * float(oc)
            if oq is not None:
                quality[kk].append(float(oq))
            if fs is not None:
                focus[kk].append(float(fs))
    out = {}
    for kk in sorted(h.keys(), key=lambda x: impact[x], reverse=True):
        out[kk] = {
            "hours": round(h[kk], 2),
            "impact_mass": round(impact[kk], 2),
            "avg_output_quality": round(sum(quality[kk]) / len(quality[kk]), 2) if quality[kk] else None,
            "avg_focus": round(sum(focus[kk]) / len(focus[kk]), 2) if focus[kk] else None,
        }
    return out


def main() -> int:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    rows = load_days(days)
    report = {
        "v": 1,
        "window_days": days,
        "blocks": len(rows),
        "by_lane": bucket(rows, "lane"),
        "by_class": bucket(rows, "class"),
        "by_place_mode": bucket(rows, "place_mode"),
        "by_actor": bucket(rows, "actor"),
        "notes": [
            "impact_mass = hours * outcome_score",
            "place_mode compares wfh vs cowork vs event etc.",
            "output_quality / focus only average when logged",
        ],
    }
    # people need multi-key
    people_rows = []
    for r in rows:
        for person in r.get("people") or []:
            rr = dict(r)
            rr["_person"] = person
            people_rows.append(rr)
    # fake key
    if people_rows:
        h = defaultdict(float)
        impact = defaultdict(float)
        for r in people_rows:
            if r.get("status") == "proposed":
                continue
            k = r["_person"]
            hrs = hours(r)
            h[k] += hrs
            impact[k] += hrs * float(r.get("outcome_score") or 0)
        report["by_people"] = {
            k: {"hours": round(h[k], 2), "impact_mass": round(impact[k], 2)}
            for k in sorted(h, key=lambda x: impact[x], reverse=True)
        }
    else:
        report["by_people"] = {}

    out_dir = RUNTIME / "views"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"performance-last-{days}d.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "path": str(out_path), "blocks": len(rows)}, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
