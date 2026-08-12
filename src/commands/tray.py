"""Tray domain commands: the `cdx tray` surface a companion talks to.

`status` is what the native companion reads. `install`, `launch`, `uninstall`
and `autostart` act on recorded state and say plainly when there is none, and
`doctor` reads all of it without changing any of it.
"""
import os
import shutil
import subprocess
from datetime import datetime, timezone

from ..cli_args import TRAY_USAGE, _parse_flag_args
from ..cli_helpers import _json_success, _write_json
from ..cli_render import _dim, _pad_table, _style, _warn
from ..config import get_cdx_home
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
    events_path,
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
from ..tray_plugins import ADAPTERS, collect_cards, enabled_plugins, set_plugin_enabled
from ..tray_terminal import REFUSAL as TERMINAL_REFUSAL
from ..tray_terminal import clear_terminal, set_terminal, terminal_preference

TRAY_ACTIONS = (
    "status", "install", "launch", "uninstall", "autostart", "doctor",
    "events", "ack", "heartbeat", "alerts", "plugin", "terminal",
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
    if action == "plugin":
        return _tray_plugin(args, ctx)
    if action == "terminal":
        return _tray_terminal(args, ctx)
    return _tray_install(args, ctx)


def _plugin_cache(ctx):
    """The per-process card cache.

    `cdx tray status` is a fresh process per poll, so this only helps within one
    invocation today. It exists as the seam the TTL is honoured through, and the
    place a longer-lived cache would go without every adapter learning about it.
    """
    return ctx.setdefault("plugin_cache", {})


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
    # Enabled integrations contribute a card each. A manual refresh passes no
    # cache, so it is what actually re-asks them; a poll reuses a card for its
    # TTL and does not make an integration pay the tray's rate.
    cards = collect_cards(
        ctx["service"]["base_dir"],
        env=ctx.get("env"),
        cache=None if parsed["refresh"] else _plugin_cache(ctx),
        directories=[row.get("cwd") for row in rows if row.get("active") and row.get("cwd")],
    )
    snapshot = build_snapshot(
        rows,
        datetime.now(timezone.utc),
        ctx["version"],
        refreshable=not any(row.get("active") for row in rows),
        plugins=cards,
        terminal=terminal_preference(ctx["service"]["base_dir"]),
    )
    # Pending alerts ride along with the snapshot rather than costing their own
    # call. Across WSL every invocation is a `wsl.exe` crossing measured at
    # 371-401 ms, so a companion asking three times per poll would triple the
    # idle cost adr_005 fixed a budget for. One crossing, everything the tray
    # needs.
    base_dir = ctx["service"]["base_dir"]
    snapshot["events"] = read_events(base_dir)
    snapshot["alerts_enabled"] = alerts_enabled(base_dir)
    # Where the alerts land, so a companion on this machine can watch the file
    # instead of waiting for its next poll. Meaningless across WSL — a Windows
    # process cannot stat a path in the Linux filesystem — and the companion
    # ignores it there rather than CDX pretending otherwise.
    snapshot["spool_path"] = events_path(base_dir)
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


def _confirm_autostart():
    answer = input("Start the CDX tray automatically at login? [Y/n] ")
    return answer.strip().lower() in ("", "y", "yes")


def _confirm_alerts():
    answer = input("Notify you when an agent finishes a turn or waits for you? [Y/n] ")
    return answer.strip().lower() in ("", "y", "yes")


def _accepted(parsed, ctx, on_flag, off_flag, confirm):
    """One consent, resolved the same way for each question.

    Two rules make it predictable. An explicit flag always wins, so a script
    gets what it asked for and never a prompt. And in the absence of one, only
    an interactive human-readable run asks — a piped or `--json` invocation
    declines rather than deciding on someone's behalf.
    """
    if parsed[off_flag]:
        return False, f"skipped with --{off_flag.replace('_', '-')}"
    if parsed[on_flag] or parsed["yes"]:
        return True, None
    if ctx["stdin_is_tty"] and not parsed["json"] and confirm():
        return True, None
    return False, None


def _enable_alerts_everywhere(ctx):
    """Turn alerts on for every session that can have them, and for future ones.

    The two halves are one promise: a user who accepted alerts means the tray
    tells them when an agent needs them, not that it does so for the sessions
    that happened to exist at the moment they answered.

    Providers with no hook mechanism are left alone rather than written to with
    a setting they will ignore.
    """
    from ..agent_notify import supports_agent_alerts
    from ..tray_defaults import set_alerts_default

    service = ctx["service"]
    set_alerts_default(service["base_dir"], True)
    enabled, codex = [], False
    for session in service["list_sessions"]():
        if not supports_agent_alerts(session["provider"]):
            continue
        if (session.get("launch") or {}).get("notify") is True:
            continue
        service["set_launch_settings"](session["name"], {"notify": True})
        enabled.append(session["name"])
        codex = codex or session["provider"] == "codex"
    return {"sessions": enabled, "codex_trust_required": codex}


def _tray_install(args, ctx):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--yes": {"key": "yes", "type": "bool", "default": False},
        "--autostart": {"key": "autostart", "type": "bool", "default": False},
        "--no-autostart": {"key": "no_autostart", "type": "bool", "default": False},
        "--alerts": {"key": "alerts", "type": "bool", "default": False},
        "--no-alerts": {"key": "no_alerts", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=0)
    env = ctx.get("env")
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

    # Installing something you asked for should show you the thing. The tray is
    # started here rather than left for a second command, and a failure to start
    # is reported without undoing an install that worked.
    started = False
    try:
        spawn = ctx.get("spawn_detached") or _spawn_detached
        spawn(launch_command(state["executable"]))
        started = True
    except Exception as error:  # noqa: BLE001 - the install itself succeeded
        ctx_error = str(error)
    else:
        ctx_error = None

    # Startup is asked for, never assumed. `req_038` AC1 originally forbade it
    # outright, for a good reason — an install that quietly adds a login item is
    # what people resent about desktop software. Asking keeps the reason and
    # drops the friction; a non-interactive run declines rather than deciding.
    autostart_on = False
    wanted, autostart_reason = _accepted(parsed, ctx, "autostart", "no_autostart", _confirm_autostart)
    if wanted:
        try:
            autostart_enable(state["executable"], env=env, run=ctx.get("spawn_sync"))
            autostart_on = True
        except Exception as error:  # noqa: BLE001
            autostart_reason = str(error)
    elif autostart_reason is None:
        autostart_reason = "not enabled; run: cdx tray autostart on"

    # The second question, asked separately because it is a different decision
    # with a different cost: one adds a login item, the other writes hooks into
    # each provider's own configuration.
    alerts_on = False
    alerts_reason = None
    alerts_result = {"sessions": [], "codex_trust_required": False}
    wanted, alerts_reason = _accepted(parsed, ctx, "alerts", "no_alerts", _confirm_alerts)
    if wanted:
        try:
            alerts_result = _enable_alerts_everywhere(ctx)
            alerts_on = True
        except Exception as error:  # noqa: BLE001 - the install itself succeeded
            alerts_reason = str(error)
    elif alerts_reason is None:
        alerts_reason = "not enabled; run: cdx set --all --notify on"

    if parsed["json"]:
        _write_json(ctx, _json_success(
            "tray.install", message,
            target=state["target"], executable=state["executable"],
            sha256=state["sha256"], applied=True,
            started=started, autostart=autostart_on,
            alerts=alerts_on,
            alerts_sessions=alerts_result["sessions"],
            codex_trust_required=alerts_result["codex_trust_required"],
        ))
        return 0
    ctx["out"](f"{message}\n{_dim(state['executable'], ctx['use_color'])}\n")
    ctx["out"](f"{'Started it.' if started else f'It is installed but did not start: {ctx_error}'}\n")
    ctx["out"](
        f"{'It will start at login.' if autostart_on else f'Startup: {autostart_reason}'}\n"
    )
    if alerts_on:
        count = len(alerts_result["sessions"])
        covered = f"{count} session(s)" if count else "no existing session"
        ctx["out"](
            f"Agent alerts: on for {covered}, and for new ones — "
            "hooks install at each session's next launch.\n"
        )
        if alerts_result["codex_trust_required"]:
            # Said here rather than discovered later: Codex puts an approval
            # prompt in front of the user at the next launch, and cdx will not
            # write that trust on their behalf.
            ctx["out"]("Codex will ask you once to approve the cdx hook plugin.\n")
    else:
        ctx["out"](f"Agent alerts: {alerts_reason}\n")
    return 0


PLUGIN_UNKNOWN = "tray_plugin_unknown"
TERMINAL_INVALID = "tray_terminal_invalid"


def _tray_terminal(args, ctx):
    """Choose the terminal a session row opens, or go back to the default.

    A refusal is a refusal, not a silent normalisation: a value that cannot be
    stored says why, and nothing is written. Storing a sanitized version of what
    someone typed would make the rule invisible exactly where it matters.
    """
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, TRAY_USAGE, positionals_key="args", max_positionals=2)
    positional = parsed["args"] or ["status"]
    mode = positional[0]
    base_dir = ctx["service"]["base_dir"]

    if mode == "clear":
        clear_terminal(base_dir)
    elif mode == "set":
        if len(positional) < 2:
            raise CdxError(TRAY_USAGE)
        try:
            set_terminal(base_dir, positional[1])
        except ValueError:
            return _refuse(ctx, parsed["json"], "tray.terminal", TERMINAL_INVALID, TERMINAL_REFUSAL)
    elif mode != "status":
        raise CdxError(TRAY_USAGE)

    chosen = terminal_preference(base_dir)
    message = (
        f"Tray session rows open {chosen}." if chosen
        else "Tray session rows open this platform's default terminal."
    )
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "tray.terminal", message, terminal=chosen, applied=mode in ("set", "clear"),
        ))
        return 0
    ctx["out"](f"{message}\n")
    if chosen:
        # Said once, at the moment it is chosen: the companion falls back
        # silently, and a user whose terminal never opens should know that is
        # the designed behaviour rather than a broken setting.
        ctx["out"](f"{_dim('If it is not installed, the platform default opens instead.', ctx['use_color'])}\n")
    return 0


def _tray_plugin(args, ctx):
    """Turn an integration on or off, and say what is on.

    Explicit in both directions and reversible, because an integration runs
    another tool's command on the user's behalf: nothing here has a default that
    turns something on, and `disable` is not a hidden setting.
    """
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--root": {"key": "root", "type": "str", "default": None},
    }, TRAY_USAGE, positionals_key="args", max_positionals=2)
    positional = parsed["args"] or ["status"]
    mode = positional[0]
    if mode not in ("enable", "disable", "status", "run"):
        raise CdxError(TRAY_USAGE)
    base_dir = ctx["service"]["base_dir"]

    if mode == "run":
        return _tray_plugin_run(positional[1:], parsed, ctx)

    if mode in ("enable", "disable"):
        if len(positional) < 2:
            raise CdxError(TRAY_USAGE)
        name = positional[1]
        if name not in ADAPTERS:
            return _refuse(
                ctx, parsed["json"], "tray.plugin", PLUGIN_UNKNOWN,
                f"No tray integration is called {name}. Known: {', '.join(sorted(ADAPTERS))}.",
            )
        set_plugin_enabled(base_dir, name, mode == "enable")

    enabled = enabled_plugins(base_dir)
    available = _available_plugins(ctx, enabled)
    message = (
        f"Tray integrations enabled: {', '.join(enabled)}" if enabled
        else "No tray integration is enabled."
    )
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "tray.plugin", message, enabled=enabled, known=sorted(ADAPTERS),
            activatable=available, applied=mode in ("enable", "disable"),
        ))
        return 0
    ctx["out"](f"{message}\n")
    for name in available:
        # Said once, as an offer rather than a nudge repeated on every command:
        # the tool is here, the card is not on, and this is how to turn it on.
        ctx["out"](f"{_dim(f'{name} is installed but not enabled. Run: cdx tray plugin enable {name}', ctx['use_color'])}\n")
    return 0


def _available_plugins(ctx, enabled):
    """Integrations whose tool is installed and whose card is not enabled."""
    from ..logics_view import resolve_logics_manager

    if "logics" in enabled or not resolve_logics_manager(ctx.get("env") or {}):
        return []
    return ["logics"]


def _tray_plugin_run(rest, parsed, ctx):
    """Perform one card action, named by its id.

    The tray sends an id back rather than a command, and this is where that
    matters: the id is matched against what CDX knows how to do, and anything
    else is refused. There is no path from a card to a shell.
    """
    from ..tray_plugin_actions import perform_action

    if not rest:
        raise CdxError(TRAY_USAGE)
    result = perform_action(rest[0], ctx, root=parsed["root"])
    if not result["ok"]:
        return _refuse(ctx, parsed["json"], "tray.plugin.run", result["code"], result["message"])
    if parsed["json"]:
        _write_json(ctx, _json_success("tray.plugin.run", result["message"], applied=True))
        return 0
    ctx["out"](f"{result['message']}\n")
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
    companion_cdx = (env or {}).get("CDX_TRAY_CDX") or shutil.which("cdx", path=(env or {}).get("PATH")) or "cdx"
    hook_store = get_cdx_home(env)

    checks = [
        ("companion", "installed" if state else ("override" if executable else "absent"),
         executable or "run: cdx tray install"),
        ("executable", "present" if executable and os.path.exists(executable) else "missing",
         executable or "-"),
        # Named rather than left as two numbers to compare: drift is the state
        # that makes someone reinstall by hand, and `cdx update` now fixes it,
        # so the report should say which one you are in.
        ("cdx_version",
         "aligned" if not state or state.get("cdx_version") == ctx["version"] else "drifted",
         f"cdx {ctx['version']}, companion {(state or {}).get('cdx_version') or 'not installed'}"),
        ("target", (state or {}).get("target") or "-", (state or {}).get("sha256") or "-"),
        ("running", "yes" if instance.get("pid") else "no", str(instance.get("pid") or "-")),
        ("autostart", "on" if autostart["enabled"] else "off", autostart["artifact"] or "unsupported"),
        ("alerts", "on" if alerts_enabled(base_dir) else "muted",
         "cdx tray alerts on|off"),
        ("companion_cdx", "override" if (env or {}).get("CDX_TRAY_CDX") else "path", companion_cdx),
        ("hook_store", "aligned" if os.path.realpath(hook_store) == os.path.realpath(base_dir) else "mismatched", hook_store),
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
