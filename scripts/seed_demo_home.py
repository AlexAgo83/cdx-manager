#!/usr/bin/env python3
"""Build a synthetic CDX_HOME for README screenshots.

Real cdx rendering, fabricated data: no account names, no labels, no hostname.
The LABEL column only renders when some session carries a label, so leaving
every label unset removes the column entirely.

Usage:
    python3 seed_demo_home.py /tmp/cdx-demo
    CDX_HOME=/tmp/cdx-demo cdx status --cached
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOW = datetime.now(timezone.utc).astimezone()


def iso(minutes_ago=0, days_ago=0):
    return (NOW - timedelta(minutes=minutes_ago, days=days_ago)).isoformat()


# name, provider, enabled, 5h remaining, week remaining, usage, resets, reset_5h, reset_week, launched days ago
ROWS = [
    ("work1",    "codex",        True,  None, 100, 0,    1,    None,        "in 6d 23h", 4),
    ("oss",      "claude",       True,  95,   99,  None, None, "in 2h 15m", "in 6d 20h", 1),
    ("work2",    "codex",        True,  None, 92,  8,    1,    None,        "in 6d 16h", 2),
    ("writing",  "claude",       True,  82,   96,  None, None, "in 1h 5m",  "in 6d 16h", 1),
    ("review",   "claude",       True,  100,  82,  None, None, "in 1h 55m", "in 2d 18h", 1),
    ("work3",    "codex",        True,  None, 75,  25,   None, None,        "in 6d 22h", 2),
    ("main",     "codex",        True,  None, 67,  33,   0,    None,        "in 3d 15h", 0),
    ("personal", "claude",       True,  99,   57,  None, None, "in 3h 25m", "in 1d 23h", 0),
    ("research", "claude",       True,  70,   54,  None, None, "in 3h 25m", "in 4h 45m", 0),
    ("scratch",  "claude",       True,  100,  46,  None, None, "in 3h 25m", "in 2d 13h", 1),
    ("work4",    "codex",        True,  None, 16,  84,   1,    None,        "in 19h 9m", 3),
    ("work5",    "codex",        True,  None, 0,   100,  1,    None,        "in 9h 12m", 5),
    ("gemini",   "antigravity",  False, None, None, None, None, None,       None,        9),
    ("local",    "ollama",       False, None, None, None, None, None,       None,        9),
    ("work6",    "codex",        False, None, None, None, None, None,       None,        4),
]


def build(home: Path):
    sessions = []
    for index, (name, provider, enabled, r5h, rweek, usage, resets, reset5, resetw, launched) in enumerate(ROWS):
        probed = 1 + (index % 7)
        root = home / "profiles" / name
        auth_home = root / "claude-home" if provider == "claude" else root
        record = {
            "name": name,
            "provider": provider,
            "enabled": enabled,
            "sessionRoot": str(root),
            "authHome": str(auth_home),
            "createdAt": iso(days_ago=60),
            "updatedAt": iso(days_ago=launched, minutes_ago=probed),
            "lastLaunchedAt": iso(days_ago=launched),
            "launch": {"power": "medium", "permission": "full", "fast": False, "rtk": True},
            "auth": {
                "status": "authenticated" if enabled else "unknown",
                "lastCheckedAt": iso(minutes_ago=probed),
                "lastAuthenticatedAt": iso(minutes_ago=probed),
            },
        }
        if enabled:
            record["lastStatusAt"] = iso(minutes_ago=probed)
            record["lastStatus"] = {
                "usage_pct": usage,
                "remaining_5h_pct": r5h,
                "remaining_week_pct": rweek,
                "credits": None,
                "reset_credits_available": resets,
                "reset_credits": resets,
                "reset_5h_at": reset5,
                "reset_week_at": resetw,
                "reset_at": resetw,
                "updated_at": iso(minutes_ago=probed),
                "raw_status_text": "",
                "source_ref": "demo",
                "structured": False,
            }
        sessions.append(record)
        auth_home.mkdir(parents=True, exist_ok=True)

    (home / "state").mkdir(parents=True, exist_ok=True)
    (home / "sessions.json").write_text(
        json.dumps({"version": 1, "sessions": sessions}, indent=2), encoding="utf-8"
    )
    return len(sessions)


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/cdx-demo").expanduser()
    count = build(target)
    print(f"Seeded {count} sessions in {target}")
    print(f"Try:  CDX_HOME={target} cdx status --cached")
