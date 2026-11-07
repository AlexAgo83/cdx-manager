"""Fast, cache-only Claude status line; executable without importing the CLI."""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKER = "--cdx-claude-status"
CACHE_TTL_SECONDS = 10 * 60  # Same freshness window as Claude's cached status.


def _read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _pct(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 100 and math.isfinite(value) else None


def gauge(value):
    # The tray menu embeds this same eight-cell glyph strip at build time.
    full, empty = Path(__file__).with_name("quota_gauge.txt").read_text(encoding="utf-8").splitlines()
    filled = int(math.floor((value or 0) / 100 * len(full) + 0.5))
    return full[:filled] + empty[filled:]


def _clean(value):
    return "".join(c for c in str(value) if c.isprintable())


def render(base_dir, env=None, now=None):
    env = os.environ if env is None else env
    data = _read(os.path.join(base_dir, "sessions.json"))
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
        return "quota ?"
    home = env.get("HOME") or env.get("USERPROFILE")
    name = env.get("CDX_SESSION_NAME")
    matches = [s for s in data["sessions"] if isinstance(s, dict) and s.get("provider") == "claude" and (
        os.path.realpath(s.get("authHome") or "") == os.path.realpath(home) if home else s.get("name") == name
    )]
    if len(matches) != 1:
        return "quota ?"
    session = matches[0]
    status = session.get("lastStatus")
    if not isinstance(status, dict):
        return "quota ?"
    values = [_pct(status.get(f"remaining_{window}_pct")) for window in ("5h", "week")]
    known = [v for v in values if v is not None]
    if not known:
        return "quota ?"
    now = now or datetime.now(timezone.utc)
    evidence = status.get("quota_windows") or {}
    stale = False
    for window, value in zip(("5h", "weekly"), values):
        if value is None:
            continue
        reading = evidence.get(window, {}) if isinstance(evidence, dict) else {}
        if not isinstance(reading, dict):
            reading = {}
        timestamp = reading.get("observed_at", status.get("updated_at") or session.get("lastStatusAt"))
        try:
            observed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            stale |= observed.tzinfo is None or not 0 <= (now - observed).total_seconds() < CACHE_TTL_SECONDS
        except (ValueError, TypeError):
            stale = True
        stale |= reading.get("availability") in ("stale", "unavailable")
    parts = []
    for window, label, value in zip(("5h", "week"), ("5h", "wk"), values):
        text = f"{label} {value:g}%" if value is not None else f"{label} ?"
        reset = status.get(f"reset_{window}_at")
        if value is not None and value < 20 and reset:
            text += f" (reset {_clean(reset)})"
        parts.append(text)
    parts.append(_clean(session.get("name", "?")))
    if stale:
        parts.append("stale")
    return f"{gauge(min(known))}  " + " · ".join(parts)


def provision(session, base_dir):
    """Return a report on conflicts; never replace an operator's status line."""
    if session.get("provider") != "claude":
        return None
    import shlex
    import subprocess

    from .agent_notify import _read_json, _write_json

    path = os.path.join(session["authHome"], ".claude", "settings.json")
    settings = _read_json(path)
    if settings is None:
        return f"{session['name']}: statusLine skipped (unreadable settings.json)"
    current = settings.get("statusLine")
    own = False
    if isinstance(current, dict) and isinstance(current.get("command"), str):
        try:
            parts = shlex.split(current["command"], posix=os.name != "nt")
            own = len(parts) == 4 and os.path.basename(parts[1].strip('"')) == "claude_status_line.py" and parts[2] == MARKER
        except ValueError:
            pass
    if "statusLine" in settings and not own:
        return f"{session['name']}: operator-defined statusLine preserved"
    if (session.get("launch") or {}).get("status_line") is False:
        if not own:
            return None
        del settings["statusLine"]
    else:
        args = [sys.executable, os.path.abspath(__file__), MARKER, os.path.abspath(base_dir)]
        command = subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)
        desired = {**(current or {}), "type": "command", "command": command}
        if current == desired:
            return None
        settings["statusLine"] = desired
    if not _write_json(path, settings):
        return f"{session['name']}: statusLine skipped (settings.json is not writable)"
    return None


def main(argv=None, stdout=None, env=None):
    argv = sys.argv[1:] if argv is None else argv
    stdout = sys.stdout if stdout is None else stdout
    try:
        text = render(argv[1], env=env) if len(argv) == 2 and argv[0] == MARKER else "quota ?"
    except (OSError, ValueError, TypeError, AttributeError):
        text = "quota ?"
    stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    # Claude reads UTF-8 from a pipe; Windows otherwise uses its ANSI code page.
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
