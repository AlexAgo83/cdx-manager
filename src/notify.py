import json
import os
import subprocess
import time

from .errors import CdxError
from .status_view import (
    PRIORITY_EMPTY_AVAILABLE_THRESHOLD,
    _parse_reset_timestamp,
    _priority_reset_timestamp,
    _recommend_priority_sessions,
)


def parse_notify_args(args):
    json_flag = "--json" in args
    once = "--once" in args
    at_reset = "--at-reset" in args
    next_ready = "--next-ready" in args
    refresh = "--refresh" in args
    poll = 60
    cleaned = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--json", "--once", "--at-reset", "--next-ready", "--refresh"):
            i += 1
            continue
        if arg == "--poll":
            if i + 1 >= len(args):
                raise CdxError("Usage: cdx notify <name> --at-reset [--poll seconds] [--once] [--refresh] | cdx notify --next-ready [--poll seconds] [--once] [--refresh]")
            try:
                poll = max(1, int(args[i + 1]))
            except ValueError as error:
                raise CdxError("--poll must be a number of seconds") from error
            i += 2
            continue
        if arg.startswith("--poll="):
            try:
                poll = max(1, int(arg.split("=", 1)[1]))
            except ValueError as error:
                raise CdxError("--poll must be a number of seconds") from error
            i += 1
            continue
        if arg.startswith("-"):
            raise CdxError("Usage: cdx notify <name> --at-reset [--poll seconds] [--once] [--refresh] | cdx notify --next-ready [--poll seconds] [--once] [--refresh]")
        cleaned.append(arg)
        i += 1
    if at_reset == next_ready:
        raise CdxError("Usage: cdx notify <name> --at-reset [--poll seconds] [--once] [--refresh] | cdx notify --next-ready [--poll seconds] [--once] [--refresh]")
    if at_reset and len(cleaned) != 1:
        raise CdxError("Usage: cdx notify <name> --at-reset [--poll seconds] [--once] [--refresh]")
    if next_ready and cleaned:
        raise CdxError("Usage: cdx notify --next-ready [--poll seconds] [--once] [--refresh]")
    return {
        "name": cleaned[0] if cleaned else None,
        "mode": "at-reset" if at_reset else "next-ready",
        "poll": poll,
        "once": once,
        "json": json_flag,
        "refresh": refresh,
    }


def wait_for_notification_event(service, parsed, notifier=None, sleep_fn=None, now_fn=None, progress_callback=None):
    notifier = notifier or send_desktop_notification
    sleep_fn = sleep_fn or time.sleep
    now_fn = now_fn or time.time
    while True:
        if progress_callback:
            progress_callback({"event": "notify_check_started", "mode": parsed["mode"], "session_name": parsed["name"]})
        event = resolve_notify_event(
            service["get_status_rows"](
                progress_callback=progress_callback,
                force_refresh=parsed.get("refresh", False),
            ),
            parsed,
            now_fn(),
        )
        if event["ready"] or parsed["once"]:
            if event["ready"]:
                notifier(event["title"], event["message"])
            return event
        if progress_callback:
            progress_callback({
                "event": "notify_waiting",
                "message": event["message"],
                "poll": parsed["poll"],
                "session_name": event.get("session"),
                "target_timestamp": event.get("target_timestamp"),
            })
        sleep_fn(parsed["poll"])


def resolve_notify_event(rows, parsed, now_ts=None):
    now_ts = time.time() if now_ts is None else now_ts
    if parsed["mode"] == "next-ready":
        active_rows = [row for row in rows if row.get("enabled", True) is not False]
        priority = _recommend_priority_sessions(active_rows)
        if not priority:
            return _event(False, "cdx", "No session status available", None)
        first = priority[0]
        if _is_usable_now(first):
            return _event(True, "cdx", f"{first['session_name']} is ready", first["session_name"])
        timestamp = _priority_reset_timestamp(first)
        if _needs_refresh(first, timestamp, now_ts):
            return _event(True, "cdx", f"{first['session_name']} reset is due; refresh status", first["session_name"])
        return _event(False, "cdx", f"Waiting for {first['session_name']}", first["session_name"], timestamp)

    row = next((item for item in rows if item["session_name"] == parsed["name"]), None)
    if not row:
        raise CdxError(f"Unknown session: {parsed['name']}")
    timestamp = _next_reset_timestamp(row)
    if timestamp is None:
        return _event(False, "cdx", f"No reset time known for {row['session_name']}", row["session_name"])
    if timestamp <= now_ts:
        return _event(True, "cdx", f"{row['session_name']} reset is due", row["session_name"], timestamp)
    return _event(False, "cdx", f"Waiting for {row['session_name']} reset", row["session_name"], timestamp)


def _is_usable_now(row):
    value = row.get("available_pct")
    return value is not None and value > PRIORITY_EMPTY_AVAILABLE_THRESHOLD


def _needs_refresh(row, reset_timestamp, now_ts):
    value = row.get("available_pct")
    if value is None or value > PRIORITY_EMPTY_AVAILABLE_THRESHOLD:
        return False
    return reset_timestamp is not None and reset_timestamp < now_ts


def _next_reset_timestamp(row):
    values = [row.get("reset_5h_at"), row.get("reset_week_at"), row.get("reset_at")]
    timestamps = [
        timestamp
        for timestamp in (_parse_reset_timestamp(value) for value in values)
        if timestamp is not None
    ]
    if not timestamps:
        return None
    return min(timestamps)


def _event(ready, title, message, session_name, target_timestamp=None):
    return {
        "ready": ready,
        "title": title,
        "message": message,
        "session": session_name,
        "target_timestamp": target_timestamp,
    }


def send_desktop_notification(title, message, spawn_sync=None, env=None):
    import sys
    spawn_sync = spawn_sync or subprocess.run
    env = env or os.environ
    if sys.platform == "win32":
        _send_windows_notification(title, message, spawn_sync, env)
    elif shutil_which("osascript", env):
        script = f'display notification "{_escape_applescript(message)}" with title "{_escape_applescript(title)}"'
        _run_notification_command(
            ["osascript", "-e", script],
            spawn_sync,
            env,
        )
    elif shutil_which("notify-send", env):
        _run_notification_command(
            ["notify-send", str(title), str(message)],
            spawn_sync,
            env,
        )


def _run_notification_command(argv, spawn_sync, env):
    try:
        spawn_sync(argv, env=env, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, OSError):
        pass


def _send_windows_notification(title, message, spawn_sync, env):
    title_escaped = _escape_powershell(title)
    message_escaped = _escape_powershell(message)
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.MessageBox]::Show('{message_escaped}', '{title_escaped}')"
    )
    try:
        spawn_sync(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            env=env,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        pass


def _escape_powershell(value):
    return str(value).replace("'", "''")


def shutil_which(command, env):
    import shutil
    return shutil.which(command, path=env.get("PATH"))


def _escape_applescript(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def format_notify_event(event):
    return event["message"]


def notify_json(event):
    return json.dumps(event, indent=2)
