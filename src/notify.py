import json
import os
import shlex
import subprocess
import time
from datetime import datetime, timedelta

from .errors import CdxError
from .status_view import (
    PRIORITY_EMPTY_AVAILABLE_THRESHOLD,
    _parse_reset_timestamp,
    _priority_reset_timestamp,
    _recommend_priority_sessions,
)


NOTIFY_USAGE = "Usage: cdx notify <name> --at-reset [--poll seconds] [--once] [--schedule] [--refresh] | cdx notify --next-ready [--poll seconds] [--once] [--schedule] [--refresh]"


def parse_notify_args(args):
    json_flag = "--json" in args
    once = "--once" in args
    at_reset = "--at-reset" in args
    next_ready = "--next-ready" in args
    refresh = "--refresh" in args
    schedule = "--schedule" in args
    poll = 60
    cleaned = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--json", "--once", "--at-reset", "--next-ready", "--refresh", "--schedule"):
            i += 1
            continue
        if arg == "--poll":
            if i + 1 >= len(args):
                raise CdxError(NOTIFY_USAGE)
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
            raise CdxError(NOTIFY_USAGE)
        cleaned.append(arg)
        i += 1
    if at_reset == next_ready:
        raise CdxError(NOTIFY_USAGE)
    if at_reset and len(cleaned) != 1:
        raise CdxError("Usage: cdx notify <name> --at-reset [--poll seconds] [--once] [--schedule] [--refresh]")
    if next_ready and cleaned:
        raise CdxError("Usage: cdx notify --next-ready [--poll seconds] [--once] [--schedule] [--refresh]")
    return {
        "name": cleaned[0] if cleaned else None,
        "mode": "at-reset" if at_reset else "next-ready",
        "poll": poll,
        "once": once,
        "json": json_flag,
        "refresh": refresh,
        "schedule": schedule,
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
        priority = _recommend_priority_sessions([
            row for row in active_rows
            if not _is_usable_now(row) and _priority_reset_timestamp(row) is not None
        ])
        if not priority:
            return _event(False, "cdx", "No upcoming session reset available", None)
        first = priority[0]
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


def schedule_notification_event(base_dir, parsed, event, spawn_sync=None, env=None, now_fn=None):
    import sys
    spawn_sync = spawn_sync or subprocess.run
    env = env or os.environ
    now_fn = now_fn or time.time
    target_timestamp = event.get("target_timestamp")
    if target_timestamp is None:
        raise CdxError(f"Cannot schedule notification: {event['message']}")
    if target_timestamp <= now_fn():
        return {
            "scheduled": False,
            "backend": "immediate",
            "message": event["message"],
            "target_timestamp": target_timestamp,
        }

    argv = _scheduled_notify_argv(parsed, env)
    if sys.platform == "darwin":
        result = _schedule_macos_launchd(base_dir, parsed, event, argv, spawn_sync, env)
    elif sys.platform == "win32":
        result = _schedule_windows_task(parsed, event, argv, spawn_sync, env)
    else:
        result = _schedule_linux(parsed, event, argv, spawn_sync, env)
    result["target_timestamp"] = target_timestamp
    result["target_iso"] = _timestamp_to_local_iso(target_timestamp)
    return result


def _scheduled_notify_argv(parsed, env):
    executable = env.get("CDX_BIN") or shutil_which("cdx", env) or "cdx"
    argv = [executable, "notify"]
    if parsed["mode"] == "at-reset":
        argv.append(parsed["name"])
        argv.append("--at-reset")
    else:
        argv.append("--next-ready")
    argv.append("--once")
    argv.append("--refresh")
    return argv


def _schedule_macos_launchd(base_dir, parsed, event, argv, spawn_sync, env):
    label = _schedule_id("com.cdx-manager.notify", parsed, event)
    schedule_dir = os.path.join(base_dir, "state", "notifications")
    os.makedirs(schedule_dir, mode=0o700, exist_ok=True)
    script_path = os.path.join(schedule_dir, f"{label}.sh")
    launch_agents = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents")
    os.makedirs(launch_agents, exist_ok=True)
    plist_path = os.path.join(launch_agents, f"{label}.plist")
    target = _round_up_to_next_minute(datetime.fromtimestamp(event["target_timestamp"]).astimezone())
    script = _macos_schedule_script(argv, env, label, plist_path, script_path)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    try:
        os.chmod(script_path, 0o700)
    except OSError:
        pass
    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(_launchd_plist(label, script_path, target))
    result = _run_scheduler_command(["launchctl", "bootstrap", f"gui/{os.getuid()}", plist_path], spawn_sync, env)
    if not result["ok"]:
        if _scheduler_error_means_exists(result["error"]):
            return {"scheduled": True, "existing": True, "backend": "launchd", "id": label, "path": plist_path}
        result = _run_scheduler_command(["launchctl", "load", plist_path], spawn_sync, env)
    if not result["ok"]:
        if _scheduler_error_means_exists(result["error"]):
            return {"scheduled": True, "existing": True, "backend": "launchd", "id": label, "path": plist_path}
        raise CdxError(f"Failed to schedule notification with launchd: {result['error']}")
    return {"scheduled": True, "existing": False, "backend": "launchd", "id": label, "path": plist_path}


def _macos_schedule_script(argv, env, label, plist_path, script_path):
    lines = ["#!/bin/sh", f"export PATH={shlex.quote(env.get('PATH', '/usr/local/bin:/usr/bin:/bin'))}"]
    if env.get("CDX_HOME"):
        lines.append(f"export CDX_HOME={shlex.quote(env['CDX_HOME'])}")
    lines.extend([
        f"{' '.join(shlex.quote(str(part)) for part in argv)}",
        "status=$?",
        f"launchctl bootout {shlex.quote('gui/' + str(os.getuid()) + '/' + label)} >/dev/null 2>&1 || launchctl unload {shlex.quote(plist_path)} >/dev/null 2>&1 || true",
        f"rm -f {shlex.quote(plist_path)} {shlex.quote(script_path)}",
        "exit $status",
        "",
    ])
    return "\n".join(lines)


def _launchd_plist(label, script_path, target):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{_escape_xml(label)}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>{_escape_xml(script_path)}</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Month</key><integer>{target.month}</integer>
    <key>Day</key><integer>{target.day}</integer>
    <key>Hour</key><integer>{target.hour}</integer>
    <key>Minute</key><integer>{target.minute}</integer>
  </dict>
</dict>
</plist>
"""


def _schedule_linux(parsed, event, argv, spawn_sync, env):
    unit = _schedule_id("cdx-manager-notify", parsed, event)
    target = _round_up_to_next_minute(datetime.fromtimestamp(event["target_timestamp"]).astimezone())
    if shutil_which("systemd-run", env):
        calendar = target.strftime("%Y-%m-%d %H:%M:%S")
        result = _run_scheduler_command(
            ["systemd-run", "--user", f"--unit={unit}", f"--on-calendar={calendar}", *argv],
            spawn_sync,
            env,
        )
        if result["ok"]:
            return {"scheduled": True, "existing": False, "backend": "systemd", "id": unit}
        if _scheduler_error_means_exists(result["error"]):
            return {"scheduled": True, "existing": True, "backend": "systemd", "id": unit}
        raise CdxError(f"Failed to schedule notification with systemd-run: {result['error']}")
    if shutil_which("at", env):
        at_time = target.strftime("%Y%m%d%H%M.%S")
        command = " ".join(shlex.quote(str(part)) for part in argv)
        result = _run_scheduler_command(["at", "-t", at_time], spawn_sync, env, input_text=f"{command}\n")
        if result["ok"]:
            return {"scheduled": True, "existing": False, "backend": "at", "id": unit}
        raise CdxError(f"Failed to schedule notification with at: {result['error']}")
    raise CdxError("Cannot schedule notification: install systemd-run or at, or run cdx notify without --schedule")


def _schedule_windows_task(parsed, event, argv, spawn_sync, env):
    name = _schedule_id("cdx-manager-notify", parsed, event)
    target = datetime.fromtimestamp(event["target_timestamp"]).astimezone()
    command = subprocess.list2cmdline([str(part) for part in argv])
    result = _run_scheduler_command([
        "schtasks",
        "/Create",
        "/SC",
        "ONCE",
        "/TN",
        name,
        "/TR",
        command,
        "/ST",
        target.strftime("%H:%M"),
        "/SD",
        target.strftime("%m/%d/%Y"),
        "/F",
        "/Z",
    ], spawn_sync, env)
    if not result["ok"]:
        raise CdxError(f"Failed to schedule notification with Task Scheduler: {result['error']}")
    return {"scheduled": True, "existing": False, "backend": "schtasks", "id": name}


def _run_scheduler_command(argv, spawn_sync, env, input_text=None):
    try:
        completed = spawn_sync(
            argv,
            env=env,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, OSError) as error:
        return {"ok": False, "error": str(error)}
    return {
        "ok": getattr(completed, "returncode", 0) == 0,
        "error": (getattr(completed, "stderr", "") or getattr(completed, "stdout", "") or "").strip(),
    }


def _schedule_id(prefix, parsed, event):
    session = parsed.get("name") or event.get("session") or "next-ready"
    safe_session = "".join(ch if ch.isalnum() else "-" for ch in str(session).lower()).strip("-") or "session"
    return f"{prefix}.{parsed['mode']}.{safe_session}.{int(event['target_timestamp'])}"


def _scheduler_error_means_exists(error):
    normalized = str(error or "").lower()
    return any(fragment in normalized for fragment in (
        "already exists",
        "file exists",
        "unit exists",
        "unit already",
        "service already",
        "bootstrap failed: 5",
    ))


def _timestamp_to_local_iso(timestamp):
    return datetime.fromtimestamp(timestamp).astimezone().isoformat()


def _round_up_to_next_minute(value):
    if value.second == 0 and value.microsecond == 0:
        return value
    return (value + timedelta(minutes=1)).replace(second=0, microsecond=0)


def _escape_xml(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def format_notify_event(event):
    return event["message"]


def format_scheduled_notification(schedule):
    if schedule.get("scheduled"):
        return f"Scheduled notification via {schedule['backend']} for {schedule['target_iso']}"
    return schedule["message"]


def notify_json(event):
    return json.dumps(event, indent=2)
