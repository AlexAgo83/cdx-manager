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
from ..tray_autostart import disable as autostart_disable
from ..tray_autostart import enable as autostart_enable
from ..tray_autostart import status as autostart_status
from ..tray_contract import (
    AUTH_LOCKED,
    FRESH,
    UNKNOWN,
    build_snapshot,
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

TRAY_ACTIONS = ("status", "install", "launch", "uninstall", "autostart", "doctor")

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
    return _tray_install(args, ctx)


def _tray_status(args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--refresh": {"key": "refresh", "type": "bool", "default": False},
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
                autostart_enable(executable, env=env)
            else:
                autostart_disable(env=env)
        except NotImplementedError as error:
            return _refuse(
                ctx, parsed["json"], "tray.autostart", AUTOSTART_UNSUPPORTED, str(error),
            )

    # Read the platform back rather than reporting what we just intended: a
    # recorded intention that drifted from the system is the confusion doctor
    # exists to end.
    state = autostart_status(env=env)
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
    autostart = autostart_status(env=env)
    instance = companion_instance()

    checks = [
        ("companion", "installed" if state else ("override" if executable else "absent"),
         executable or "run: cdx tray install"),
        ("executable", "present" if executable and os.path.exists(executable) else "missing",
         executable or "-"),
        ("cdx_version", ctx["version"], (state or {}).get("cdx_version") or "-"),
        ("target", (state or {}).get("target") or "-", (state or {}).get("sha256") or "-"),
        ("running", "yes" if instance.get("pid") else "no", str(instance.get("pid") or "-")),
        ("autostart", "on" if autostart["enabled"] else "off", autostart["artifact"] or "unsupported"),
        ("update", "interrupted" if interrupted_update(base_dir) else "clean",
         "a staged companion was never promoted; run: cdx tray install"
         if interrupted_update(base_dir) else "-"),
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
