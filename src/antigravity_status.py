"""Local Antigravity statusLine capture; no credential or network access."""

import argparse
import base64
import json
import math
import os
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

STATE_NAME = "cdx-quota.json"
MARKER = "--cdx-antigravity-status"


def _directory(home):
    return os.path.join(home, ".gemini", "antigravity-cli")


def _date(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def _quota(value):
    result = {}
    if not isinstance(value, dict):
        return result
    for name, bucket in value.items():
        if not isinstance(bucket, dict):
            continue
        clean = {}
        fraction = bucket.get("remaining_fraction")
        if isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and math.isfinite(fraction) and 0 <= fraction <= 1:
            clean["remaining_fraction"] = fraction
        reset = _date(bucket.get("reset_time"))
        if reset:
            clean["reset_time"] = reset.isoformat()
        seconds = bucket.get("reset_in_seconds")
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and math.isfinite(seconds) and seconds >= 0:
            clean["reset_in_seconds"] = seconds
        result[name] = clean
    return result


def capture(payload, state_path, now=None):
    """Persist only an allowlist, atomically with private permissions."""
    if not isinstance(payload, dict):
        return
    now = now or datetime.now(timezone.utc)
    state = {"time": now.isoformat(),
             "plan_tier": payload.get("plan_tier") if isinstance(payload.get("plan_tier"), str) else None,
             "quota": _quota(payload.get("quota"))}
    directory = os.path.dirname(state_path)
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cdx-quota-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
            handle.write("\n")
        os.replace(temporary, state_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(home):
    """Merge the hook without replacing unrelated settings or user output."""
    from .agent_notify import _read_json, _write_json

    path = os.path.join(_directory(home), "settings.json")
    settings = _read_json(path)
    if settings is None:
        return False
    status = settings.get("statusLine") or {}
    if not isinstance(status, dict) or (status and status.get("type") != "command"):
        return False
    previous = status.get("command") or ""
    if not isinstance(previous, str):
        return False
    try:
        parts = shlex.split(previous, posix=os.name != "nt")
    except ValueError:
        parts = []
    own_command = (len(parts) >= 3 and os.path.basename(parts[1].strip('"')) == "antigravity_status.py"
                   and parts[2] == MARKER)
    if own_command:
        index = parts.index("--previous") + 1 if "--previous" in parts else len(parts)
        encoded = parts[index] if index < len(parts) else ""
    else:
        encoded = base64.urlsafe_b64encode(previous.encode()).decode()
    args = [sys.executable, os.path.abspath(__file__), MARKER,
            "--state", os.path.join(_directory(home), STATE_NAME)]
    if encoded:
        args += ["--previous", encoded]
    command = subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)
    merged = {**status, "type": "command", "command": command}
    if settings.get("statusLine") == merged:
        return True
    return _write_json(path, {**settings, "statusLine": merged})


def read_status(home, now=None):
    """Expose every bucket; use only fresh Gemini windows for availability."""
    now = now or datetime.now(timezone.utc)
    try:
        with open(os.path.join(_directory(home), STATE_NAME), encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    at = _date(state.get("time"))
    age = max(0, (now - at).total_seconds()) if at else None
    stale = age is not None and age > 24 * 60 * 60
    quota = _quota(state.get("quota"))
    for bucket in quota.values():
        reset = _date(bucket.get("reset_time"))
        valid = at is not None and not stale and reset is not None and reset > now
        bucket["status"] = "stale" if stale else "current" if valid else "unknown"
        if not valid:
            bucket["remaining_fraction"] = None
    result = {"updated_at": at.isoformat() if at else None, "reading_age_seconds": age,
              "quota_stale": stale, "quota_status": "stale" if stale else "current" if at else "unknown",
              "plan_tier": state.get("plan_tier"), "quota": quota}
    for window, name in (("5h", "gemini-5h"), ("week", "gemini-weekly")):
        bucket = quota.get(name, {})
        reset = _date(bucket.get("reset_time"))
        valid = at is not None and not stale and reset is not None and reset > now
        fraction = bucket.get("remaining_fraction") if valid else None
        result[f"remaining_{window}_pct"] = fraction * 100 if fraction is not None else None
        result[f"reset_{window}_at"] = reset.astimezone().strftime("%b %d %H:%M") if valid else None
        result[f"reset_{window}_at_iso"] = reset.isoformat() if valid else None
    return result


def main(stdin=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(MARKER, action="store_true")
    parser.add_argument("--state", required=True)
    parser.add_argument("--previous", default="")
    args = parser.parse_args()
    raw = (stdin or sys.stdin).read()
    try:
        capture(json.loads(raw), args.state)
    except (ValueError, OSError, TypeError):
        # A failed capture must not suppress the user's existing status line.
        pass
    if args.previous:
        command = base64.urlsafe_b64decode(args.previous).decode()
        return subprocess.run(command, shell=True, input=raw, text=True, check=False).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
