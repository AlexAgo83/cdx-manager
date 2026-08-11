"""Tray domain commands: the `cdx tray` surface a companion talks to.

`status` is what the native companion reads. `install`, `launch`, `uninstall`
and `autostart` act on recorded state and say plainly when there is none, and
`doctor` reads all of it without changing any of it.
"""
import os
import subprocess
from datetime import datetime, timezone

from ..cli_args import TRAY_USAGE, _parse_flag_args
from ..cli_helpers import _json_success, _write_json
from ..cli_render import _dim, _pad_table, _style, _warn
from ..errors import CdxError
from ..tray_alerts import alerts_enabled, set_alerts
from ..tray_autostart import disable as autostart_disable
from ..tray_autostart import enable as autostart_enable
from ..tray_autostart import status as autostart_status
from ..tray_capability import desktop_capability, toast_capability
from ..tray_contract import (
    AUTH_LOCKED,
    FRESH,
    UNKNOWN,
    build_snapshot,
)
from ..tray_events import (
    acknowledge as ack_events,
)
from ..tray_events import (
    read_events,
    write_heartbeat,
)
from ..tray_install import (
    TrayInstallError,
    companion_path,
    current_target,
    install,
    interrupted_update,
    launch_command,
    read_state,
    uninstall,
)
from ..tray_instance import companion_instance

TRAY_ACTIONS = (
    "status", "install", "launch", "uninstall", "autostart", "doctor",
    "events", "ack", "heartbeat", "alerts",
)

# Codes rather than prose, so a caller can branch on them.
COMPANION_UNAVAILABLE = "tray_companion_not_available"
COMPANION_NOT_INSTALLED = "tray_companion_not_installed"
COMPANION_MISSING_FILE = "tray_companion_missing"
AUTOSTART_UNSUPPORTED = "tray_autostart_unsupported"

_FRESHNESS_TEXT = {
    FRESH: "fresh",
    AUTH_LOCKED: "cannot refresh while the session runs",
    UNKNOWN: "never reported",
}


def handle_tray(rest, ctx):
    if not rest or rest[0] in ("help", "--help", "-h"):
        ctx["out"](f"{TRAY_USAGE}\n")
        return 0
    action, *args = rest
    if action not in TRAY_ACTIONS:
        raise CdxError(TRAY_USAGE)
    if action == "status":
        return _tray_status(args, ctx)
    if action == "launch":
        return _tray_launch(args, ctx)
    if action == "uninstall":
        return _tray_uninstall(args, ctx)
    if action == "autostart":
        return _tray_autostart(args, ctx)
    if action == "doctor":
        return _tray_doctor(args, ctx)
    if action == "events":
        return _tray_events(args, ctx)
    if action == "ack":
        return _tray_ack(args, ctx)
    if action == "heartbeat":
        return _tray_heartbeat(args, ctx)
    if action == "alerts":
        return _tray_alerts(args, ctx)
    return _tray_install(args, ctx)


def _tray_status(args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--refresh": {"key": "refresh", "type": "bool", "default": False},
        "--beat": {"key": "beat", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)

    # Cached by default: a tray polls, and a live probe would contend on the
    # Codex auth lock and can invalidate a rotating refresh token. Only an
    # explicit refresh, which is a user gesture from the menu, may probe.
    rows = ctx["service"]["get_status_rows"](
        force_refresh=parsed["refresh"],
        cache_only=not parsed["refresh"],
    )
    snapshot = build_snapshot(
        rows,
        datetime.now(timezone.utc),
        ctx["version"],
        refreshable=not any(row.get("active") for row in rows),
    )
    # Pending alerts ride along with the snapshot rather than costing their own
    # call. Across WSL every invocation is a `wsl.exe` crossing measured at
    # 371-401 ms, so a companion asking three times per poll would triple the
    # idle cost adr_005 fixed a budget for. One crossing, everything the tray
    # needs.
    base_dir = ctx["service"]["base_dir"]
    snapshot["events"] = read_events(base_dir)
    snapshot["alerts_enabled"] = alerts_enabled(base_dir)
    # `--beat` is what claims ownership of alerts, so it is opt-in: a caller
    # that merely looks at the status must not make `cdx notify` believe a tray
    # is listening.
    if parsed["beat"]:
        write_heartbeat(base_dir)
    if parsed["json"]:
        _write_json(ctx, _json_success("tray.status", "Built tray snapshot", snapshot=snapshot))
        return 0
    ctx["out"](f"{_format_snapshot(snapshot, use_color=ctx['use_color'])}\n")
    return 0


def _tray_launch(args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)
    base_dir = ctx["service"]["base_dir"]
    executable, source = companion_path(base_dir, env=ctx.get("env"))

    if not executable:
        return _refuse(
            ctx, parsed["json"], "tray.launch", COMPANION_NOT_INSTALLED,
            "No tray companion is installed. Run: cdx tray install",
        )
    if not os.path.exists(executable):
        # A recorded path that no longer exists is worth naming: the companion
        # was removed behind CDX's back, and reinstalling is the fix.
        return _refuse(
            ctx, parsed["json"], "tray.launch", COMPANION_MISSING_FILE,
            f"The recorded tray companion is gone: {executable}. Run: cdx tray install",
        )

    command = launch_command(executable)
    try:
        # Detached on purpose: the tray outlives the command that started it,
        # and cdx must not wait on a process that only exits when the user quits.
        spawn = ctx.get("spawn_detached") or _spawn_detached
        spawn(command)
    except OSError as error:
        raise CdxError(f"Could not start the tray companion: {error}") from error

    message = f"Started the tray companion from {executable}"
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "tray.launch", message, executable=executable, source=source, command=command,
        ))
        return 0
    ctx["out"](f"{message}\n")
    return 0


def _spawn_detached(command):
    subprocess.Popen(  # noqa: S603  (command is CDX-controlled, never user text)
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _tray_uninstall(args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)
    result = uninstall(ctx["service"]["base_dir"])
    if not result:
        # Nothing recorded means nothing to remove. Deleting on a guess is how
        # an uninstaller takes a file it did not put there.
        return _refuse(
            ctx, parsed["json"], "tray.uninstall", COMPANION_NOT_INSTALLED,
            "No tray companion install is recorded, so nothing was removed.",
        )
    message = f"Removed the tray companion ({len(result['removed'])} path(s))"
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "tray.uninstall", message, removed=result["removed"], applied=True,
        ))
        return 0
    ctx["out"](f"{message}\n")
    return 0


def _tray_install(args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)
    target = current_target()
    if not target:
        return _refuse(
            ctx, parsed["json"], "tray.install", COMPANION_UNAVAILABLE,
            "No tray companion is published for this operating system and architecture.",
        )
    try:
        state = install(
            ctx["service"]["base_dir"],
            ctx["version"],
            download=ctx.get("download_asset"),
            env=ctx.get("env"),
        )
    except TrayInstallError as error:
        # A refusal, not a crash: nothing was written, and the reason is the
        # useful part. Raising keeps the non-zero exit a caller expects.
        raise CdxError(str(error)) from error

    message = f"Installed the {state['target']} tray companion for CDX {state['cdx_version']}"
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "tray.install", message,
            target=state["target"], executable=state["executable"],
            sha256=state["sha256"], applied=True,
        ))
        return 0
    ctx["out"](f"{message}\n{_dim(state['executable'], ctx['use_color'])}\n")
    return 0


def _tray_autostart(args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=1)
    mode = (parsed["args"] or ["status"])[0]
    if mode not in ("on", "off", "status"):
        raise CdxError(TRAY_USAGE)
    env = ctx.get("env")

    if mode != "status":
        executable, _source = companion_path(ctx["service"]["base_dir"], env=env)
        if mode == "on" and not executable:
            return _refuse(
                ctx, parsed["json"], "tray.autostart", COMPANION_NOT_INSTALLED,
                "No tray companion is installed, so there is nothing to start at login.",
            )
        try:
            if mode == "on":
                autostart_enable(executable, env=env, run=ctx.get("spawn_sync"))
            else:
                autostart_disable(env=env, run=ctx.get("spawn_sync"))
        except NotImplementedError as error:
            return _refuse(
                ctx, parsed["json"], "tray.autostart", AUTOSTART_UNSUPPORTED, str(error),
            )

    # Read the platform back rather than reporting what we just intended: a
    # recorded intention that drifted from the system is the confusion doctor
    # exists to end.
    state = autostart_status(env=env, run=ctx.get("spawn_sync"))
    if not state["supported"]:
        return _refuse(
            ctx, parsed["json"], "tray.autostart", AUTOSTART_UNSUPPORTED,
            "This platform has no autostart mechanism CDX knows how to manage.",
        )
    message = f"Tray autostart is {'on' if state['enabled'] else 'off'}"
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "tray.autostart", message,
            enabled=state["enabled"], artifact=state["artifact"], applied=mode != "status",
        ))
        return 0
    ctx["out"](f"{message}\n{_dim(state['artifact'], ctx['use_color'])}\n")
    return 0


# `None` is a real answer here: the bus could not be asked. Reporting it as
# "no tray" would be a claim the probe did not make.
_DESKTOP_STATE = {True: "ready", False: "no tray", None: "unknown"}


def _tray_doctor(args, ctx):
    """Every state I had to diagnose by hand, in one bounded report.

    No background service and no repair: it reads, it never fixes. A doctor that
    also acted would have to be trusted with the machine, and this one only has
    to be trusted to tell the truth.
    """
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)
    base_dir = ctx["service"]["base_dir"]
    env = ctx.get("env")
    executable, source = companion_path(base_dir, env=env)
    state = read_state(base_dir)
    autostart = autostart_status(env=env, run=ctx.get("spawn_sync"))
    instance = companion_instance(env=env)
    desktop = desktop_capability(env=env)
    toasts = toast_capability(env=env)

    checks = [
        ("companion", "installed" if state else ("override" if executable else "absent"),
         executable or "run: cdx tray install"),
        ("executable", "present" if executable and os.path.exists(executable) else "missing",
         executable or "-"),
        ("cdx_version", ctx["version"], (state or {}).get("cdx_version") or "-"),
        ("target", (state or {}).get("target") or "-", (state or {}).get("sha256") or "-"),
        ("running", "yes" if instance.get("pid") else "no", str(instance.get("pid") or "-")),
        ("autostart", "on" if autostart["enabled"] else "off", autostart["artifact"] or "unsupported"),
        ("alerts", "on" if alerts_enabled(base_dir) else "muted",
         "cdx tray alerts on|off"),
        ("update", "interrupted" if interrupted_update(base_dir) else "clean",
         "a staged companion was never promoted; run: cdx tray install"
         if interrupted_update(base_dir) else "-"),
        # Both fail silently when absent, which is the only reason they are
        # worth a line: nothing else would ever tell the user.
        ("desktop", _DESKTOP_STATE.get(desktop.get("available")), desktop["detail"]),
        ("toasts", "ready" if toasts["present"] else ("blocked" if toasts["gated"] else "n/a"),
         toasts["detail"]),
    ]
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "tray.doctor", "Collected tray diagnostics",
            checks=[{"check": c, "state": s, "detail": d} for c, s, d in checks],
        ))
        return 0
    rows = [["CHECK", "STATE", "DETAIL"], *[[c, s, d] for c, s, d in checks]]
    ctx["out"](f"{_pad_table(rows)}\n")
    return 0


def _refuse(ctx, as_json, action, code, message):
    """Report that nothing happened, and why, without failing the command.

    Not an error: asking to launch a tray that is not installed is a reasonable
    thing to do, and the answer is a state rather than a fault.
    """
    if as_json:
        _write_json(ctx, _json_success(
            action, message, warnings=[{"code": code, "message": message}], applied=False,
        ))
        return 0
    ctx["out"](f"{_warn(message, ctx['use_color'])}\n")
    return 0


def _companion_action(action, args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)
    message = (
        f"cdx tray {action} is defined but no tray companion ships with CDX {ctx['version']}. "
        "Nothing was installed, started, or changed."
    )
    if parsed["json"]:
        _write_json(ctx, _json_success(
            f"tray.{action}",
            message,
            warnings=[{"code": COMPANION_UNAVAILABLE, "message": message}],
            applied=False,
        ))
        return 0
    ctx["out"](f"{_warn(message, ctx['use_color'])}\n")
    return 0


def _pct(value):
    return "?" if value is None else f"{int(value)}%"


def _format_snapshot(snapshot, use_color=False):
    icon = snapshot["icon"]
    header = _style(f"tray: {icon['state']}", "1", use_color)
    if not snapshot["sessions"]:
        return f"{header}\n{_dim('No enabled sessions.', use_color)}"
    rows = [["SESSION", "PROVIDER", "LEFT", "STATE", "DATA"]]
    for session in snapshot["sessions"]:
        rows.append([
            session["name"] or "?",
            session["provider"] or "-",
            _pct(session["available_pct"]),
            session["state"],
            _FRESHNESS_TEXT.get(session["freshness"], session["freshness"]),
        ])
    lines = [header, _pad_table(rows)]
    if not snapshot["refreshable"]:
        lines.append(_dim("A running session holds the provider lock; refresh will not update it.", use_color))
    return "\n".join(lines)


# The companion reads and acknowledges events through these three commands
# rather than through the filesystem, and that is the whole point of them: on a
# Windows host serving CDX from WSL, the spool lives in the Linux filesystem
# while the tray runs on Windows. Going through `cdx` means the existing
# `wsl.exe` transport carries events too — no path translation, no share, no
# socket, and no assumption that either side can see the other's disk.
def _tray_events(args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)
    events = read_events(ctx["service"]["base_dir"])
    if parsed["json"]:
        _write_json(ctx, _json_success("tray.events", f"Read {len(events)} pending event(s)", events=events))
        return 0
    if not events:
        ctx["out"]("No pending tray events.\n")
        return 0
    rows = [["WHEN", "KIND", "TITLE", "MESSAGE"]]
    for event in events:
        rows.append([
            datetime.fromtimestamp(event.get("at", 0), timezone.utc).strftime("%H:%M:%S"),
            event.get("kind", "-"), event.get("title", "-"), event.get("message", "-"),
        ])
    ctx["out"](f"{_pad_table(rows)}\n")
    return 0


def _tray_ack(args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=64)
    ids = parsed["args"]
    if not ids:
        raise CdxError(TRAY_USAGE)
    result = ack_events(ctx["service"]["base_dir"], ids)
    message = f"Acknowledged {result['acknowledged']} event(s)"
    if parsed["json"]:
        _write_json(ctx, _json_success("tray.ack", message, **result))
        return 0
    ctx["out"](f"{message}\n")
    return 0


def _tray_heartbeat(args, ctx):
    """The companion saying it is alive, so `cdx notify` stops delivering directly.

    Written by the tray once per poll. `cdx notify` publishes only while this is
    fresh, so a companion that stops beating hands alerts straight back to the
    direct path rather than swallowing them.
    """
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)
    write_heartbeat(ctx["service"]["base_dir"])
    if parsed["json"]:
        _write_json(ctx, _json_success("tray.heartbeat", "Recorded the tray heartbeat"))
        return 0
    ctx["out"]("Recorded the tray heartbeat.\n")
    return 0


def _tray_alerts(args, ctx):
    """Silence agent alerts, or let them through again.

    Separate from the per-session `--notify` preference on purpose: that says
    which sessions may alert at all, and spending it to go quiet for a meeting
    would be a poor trade. This is the temporary switch, and it is reported
    rather than remembered — `cdx tray doctor` reads it back.
    """
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=1)
    mode = (parsed["args"] or ["status"])[0]
    if mode not in ("on", "off", "status"):
        raise CdxError(TRAY_USAGE)
    base_dir = ctx["service"]["base_dir"]
    if mode != "status":
        set_alerts(base_dir, mode == "on")
    enabled = alerts_enabled(base_dir)
    message = f"Agent alerts are {'on' if enabled else 'muted'}"
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "tray.alerts", message, enabled=enabled, applied=mode != "status",
        ))
        return 0
    ctx["out"](f"{message}\n")
    return 0
