"""What rtk saved, for the period `cdx stats` reports on.

Launches share the operator's rtk history (RTK_DB_PATH), but profiles used before
that kept their own `history.db` under their home; both are read so older
savings are not lost. rtk itself does the reading (`rtk gain --daily --format
json`), so this never depends on its database schema.
"""

import glob
import json
import os
import shutil
import subprocess
from datetime import datetime

from .provider_runtime import operator_rtk_history_path

_PROFILE_DBS = (
    ("*", "Library", "Application Support", "rtk", "history.db"),
    ("*", "*-home", "Library", "Application Support", "rtk", "history.db"),
    ("*", ".local", "share", "rtk", "history.db"),
    ("*", "*-home", ".local", "share", "rtk", "history.db"),
)


def history_databases(base_dir, env=None):
    """Every rtk history this operator's sessions wrote to, the shared one first."""
    found = []
    for path in [operator_rtk_history_path(env)] + [
        match for pattern in _PROFILE_DBS
        for match in sorted(glob.glob(os.path.join(glob.escape(os.path.join(base_dir, "profiles")), *pattern)))
    ]:
        if path and os.path.isfile(path) and os.path.realpath(path) not in {os.path.realpath(p) for p in found}:
            found.append(path)
    return found


def _in_period(day, period):
    for key, keep in (("from", lambda d, edge: d >= edge), ("to", lambda d, edge: d <= edge)):
        edge = (period or {}).get(key)
        if edge and not keep(day, datetime.fromisoformat(edge).date().isoformat()):
            return False
    return True


def rtk_saved(base_dir, period=None, env=None, run=subprocess.run):
    """{commands, input_tokens, saved_tokens, databases} over the period, or None without rtk."""
    env = {**os.environ, **(env or {})}
    rtk = shutil.which("rtk", path=env.get("PATH"))
    databases = history_databases(base_dir, env)
    if not rtk or not databases:
        return None
    totals = {"commands": 0, "input_tokens": 0, "saved_tokens": 0, "databases": 0}
    for database in databases:
        try:
            result = run([rtk, "gain", "--daily", "--format", "json"], env={**env, "RTK_DB_PATH": database},
                         capture_output=True, text=True, timeout=15, check=False)
            days = json.loads(result.stdout).get("daily") or []
        except (OSError, ValueError, AttributeError, subprocess.TimeoutExpired):
            continue
        totals["databases"] += 1
        for day in days:
            if isinstance(day, dict) and _in_period(str(day.get("date")), period):
                totals["commands"] += int(day.get("commands") or 0)
                totals["input_tokens"] += int(day.get("input_tokens") or 0)
                totals["saved_tokens"] += int(day.get("saved_tokens") or 0)
    return totals if totals["databases"] else None
