import json
import os
import shlex
import shutil
import subprocess
import time
from datetime import datetime, timedelta

from .errors import CdxError
from .session_ranking import rank_sessions
from .status_view import (
    PRIORITY_EMPTY_AVAILABLE_THRESHOLD,
    _priority_reset_timestamp,
)

READY_USAGE = "Usage: cdx ready [--refresh] [--json]"


def parse_ready_args(args):
    """`cdx ready [--refresh] [--json]`.

    This used to parse a much wider surface — --at-reset, --once, --poll and a
    blocking wait loop — reachable through a `cdx notify` that no longer exists.
    `cdx ready` always schedules the next-ready event, so none of it could run.
    """
    unknown = [arg for arg in args if arg not in ("--refresh", "--json")]
    if unknown:
        raise CdxError(READY_USAGE)
    return {
        "name": None,
        "mode": "next-ready",
        "json": "--json" in args,
        "refresh": "--refresh" in args,
        "schedule": True,
    }


def resolve_notify_event(rows, parsed, now_ts=None):
    now_ts = time.time() if now_ts is None else now_ts
    active_rows = [row for row in rows if row.get("enabled", True) is not False]
    # Same ranking every other selector uses; the pre-filter is what makes
    # this "next to come back" rather than "best right now".
    priority, _decision = rank_sessions(
        [
            row for row in active_rows
            if not _is_usable_now(row) and _priority_reset_timestamp(row) is not None
        ],
        now_ts,
        _priority_reset_timestamp,
    )
    if not priority:
        return _event(False, "cdx", "No upcoming session reset available", None)
    first = priority[0]
    timestamp = _priority_reset_timestamp(first)
    if _needs_refresh(first, timestamp, now_ts):
        return _event(True, "cdx", f"{first['session_name']} reset is due; refresh status", first["session_name"])
    return _event(False, "cdx", f"Waiting for {first['session_name']}", first["session_name"], timestamp)


def _is_usable_now(row):
    value = row.get("available_pct")
    return value is not None and value > PRIORITY_EMPTY_AVAILABLE_THRESHOLD


def _needs_refresh(row, reset_timestamp, now_ts):
    value = row.get("available_pct")
    if value is None or value > PRIORITY_EMPTY_AVAILABLE_THRESHOLD:
        return False
    return reset_timestamp is not None and reset_timestamp < now_ts


def _event(ready, title, message, session_name, target_timestamp=None):
    return {
        "ready": ready,
        "title": title,
        "message": message,
        "session": session_name,
        "target_timestamp": target_timestamp,
    }


def notification_channel(env=None):
    """Name the delivery mechanism usable on this host, or None if there is none.

    Two callers depend on this answer: `cdx notify` decides whether to bother
    delivering, and launch provisioning decides whether to install hooks at all.
    A host with no channel gets no hooks, so the user is never asked to approve
    a hook that could not have shown them anything.
    """
    import sys
    env = env or os.environ
    path = env.get("PATH")
    if sys.platform == "win32":
        return "powershell" if shutil.which("powershell", path=path) else None
    if _is_wsl(env):
        # WSL has no notification daemon of its own; delivery crosses to Windows
        # through interop, which /etc/wsl.conf can disable.
        return "wsl" if shutil.which("powershell.exe", path=path) else None
    if shutil.which("osascript", path=path):
        return "osascript" if _has_desktop_session(env) else None
    if shutil.which("notify-send", path=path):
        return "notify-send" if _has_desktop_session(env) else None
    return None


def _is_wsl(env):
    if env.get("WSL_DISTRO_NAME") or env.get("WSL_INTEROP"):
        return True
    try:
        with open("/proc/version", encoding="utf-8") as handle:
            return "microsoft" in handle.read().lower()
    except OSError:
        return False


def _has_desktop_session(env):
    """Whether anything is around to render a notification.

    Over SSH or in a container there is no session bus and no display, so
    notify-send is delivered nowhere and osascript has no session to talk to.
    """
    import sys
    if sys.platform == "darwin":
        return not env.get("SSH_CONNECTION")
    return bool(env.get("DISPLAY") or env.get("WAYLAND_DISPLAY") or env.get("DBUS_SESSION_BUS_ADDRESS"))


def send_desktop_notification(title, message, spawn_sync=None, env=None):
    spawn_sync = spawn_sync or subprocess.run
    env = env or os.environ
    channel = notification_channel(env)
    if channel == "powershell":
        _send_windows_notification(title, message, spawn_sync, env, ["powershell"])
    elif channel == "wsl":
        _send_windows_notification(title, message, spawn_sync, env, ["powershell.exe"])
    elif channel == "osascript":
        script = f'display notification "{_escape_applescript(message)}" with title "{_escape_applescript(title)}"'
        _run_notification_command(
            ["osascript", "-e", script],
            spawn_sync,
            env,
        )
    elif channel == "notify-send":
        _run_notification_command(
            ["notify-send", "-a", "cdx", str(title), str(message)],
            spawn_sync,
            env,
        )


def _run_notification_command(argv, spawn_sync, env):
    try:
        spawn_sync(argv, env=env, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass


# Windows shows a toast only on behalf of an application it knows, and it knows
# an application by a Start Menu shortcut carrying its AppUserModelID. An
# unknown identifier is dropped in silence — no error, no toast.
#
# PowerShell's own identifier is the fallback, and it is a real compromise: the
# toast then says "Windows PowerShell", and turning CDX alerts off in Settings
# means turning PowerShell off. It is used only while CDX has no shortcut of its
# own, which `cdx tray install` now writes.
_POWERSHELL_AUMID = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe"

_TOAST_SCRIPT = """
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$nodes = $template.GetElementsByTagName('text')
$nodes.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null
$nodes.Item(1).AppendChild($template.CreateTextNode('{message}')) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{aumid}').Show($toast)
"""


def _send_windows_notification(title, message, spawn_sync, env, launcher):
    """Raise a toast rather than a dialog.

    The dialog this replaced blocked with no timeout, which was survivable for a
    once-a-day quota alert and not for a hook that fires on every agent turn: an
    undismissed window holds the turn open, and one that steals focus every turn
    is worse than no notification at all.
    """
    script = _TOAST_SCRIPT.format(
        title=_escape_powershell(title),
        message=_escape_powershell(message),
        aumid=_escape_powershell(windows_aumid(env)),
    )
    _run_notification_command(
        [*launcher, "-NoProfile", "-NonInteractive", "-Command", script],
        spawn_sync,
        env,
    )


def windows_aumid(env=None):
    """CDX's own identifier when Windows can resolve it, PowerShell's otherwise.

    The shortcut has to exist before the identifier means anything: Windows
    resolves an AppUserModelID through the Start Menu, so claiming ours without
    one would drop every toast in silence — strictly worse than a toast
    attributed to PowerShell.
    """
    from .tray_shortcut import APP_USER_MODEL_ID, shortcut_path
    path = shortcut_path(env)
    if path and os.path.isfile(path):
        return APP_USER_MODEL_ID
    return _POWERSHELL_AUMID


def _escape_powershell(value):
    return str(value).replace("'", "''")


def _escape_applescript(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def schedule_notification_event(base_dir, parsed, event, spawn_sync=None, env=None, now_fn=None):
    import sys
    spawn_sync = spawn_sync or subprocess.run
    env = env or os.environ
    now_fn = now_fn or time.time
    target_timestamp = event.get("target_timestamp")
    if target_timestamp is None:
        if parsed["mode"] == "next-ready":
            return {
                "scheduled": False,
                "backend": "none",
                "message": event["message"],
                "target_timestamp": None,
            }
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
    executable = env.get("CDX_BIN") or shutil.which("cdx", path=env.get("PATH")) or "cdx"
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
    if shutil.which("systemd-run", path=env.get("PATH")):
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
    if shutil.which("at", path=env.get("PATH")):
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


def format_scheduled_notification(schedule):
    if schedule.get("scheduled"):
        return f"Scheduled notification via {schedule['backend']} for {schedule['target_iso']}"
    return schedule["message"]


def notify_json(event):
    return json.dumps(event, indent=2)
