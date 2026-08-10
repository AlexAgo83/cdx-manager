#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime, timezone

from .agent_notify import handle_notify
from .cli_commands import (
    API_SCHEMA_VERSION,
    STATUS_USAGE,
    _collect_profile_cleanup_candidates,
    _directory_child_sizes,
    _directory_size_bytes,
    handle_add,
    handle_can_resume,
    handle_clean,
    handle_config,
    handle_configs,
    handle_context,
    handle_copy,
    handle_disable,
    handle_disk,
    handle_doctor,
    handle_enable,
    handle_export,
    handle_handoff,
    handle_history,
    handle_import,
    handle_label,
    handle_last,
    handle_launch,
    handle_launch_setting_alias,
    handle_login,
    handle_logout,
    handle_memory,
    handle_next,
    handle_ready,
    handle_remove,
    handle_rename,
    handle_repair,
    handle_reset,
    handle_resume,
    handle_run,
    handle_run_report,
    handle_run_status,
    handle_run_tail,
    handle_runs,
    handle_schema,
    handle_select,
    handle_set,
    handle_stats,
    handle_status,
    handle_tray,
    handle_unset,
    handle_update,
    handle_view,
)
from .cli_commands import (
    _format_bytes as _format_disk_bytes,
)
from .cli_helpers import _update_notice_warnings
from .cli_render import (
    _format_sessions,
    _pad_table,
    _should_use_color,
    _style,
    _visible_len,
    format_error,
)
from .errors import CdxError
from .provider_runtime import (
    LOG_ROTATE_BYTES,
    _rotate_log_if_needed,
)
from .session_service import create_session_service
from .status_view import (
    _format_blocking_quota,
    _format_reset_time,
    _format_status_detail,
    _format_status_rows,
)
from .update_check import check_for_update, check_logics_manager_for_update


def _resolve_version():
    """The version, resolved rather than restated.

    This was a hardcoded string, a fourth copy alongside VERSION, package.json,
    and pyproject.toml, with nothing keeping the four in step — so
    `cdx --version` could report a release it was not.

    The VERSION file next to the package wins when it exists, because that only
    happens in a checkout, where it is the thing being edited and the installed
    metadata is whatever was last `pip install`ed. Installed packages have no
    such file and fall through to their own metadata.
    """
    version_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION"
    )
    try:
        with open(version_file, encoding="utf-8") as handle:
            text = handle.read().strip()
        if text:
            return text
    except OSError:
        pass
    try:
        from importlib.metadata import version

        return version("cdx-manager")
    except Exception:  # noqa: BLE001 - any resolution failure falls back below
        return "0.0.0"


VERSION = _resolve_version()

# Public surface: this module is a facade. Names below are imported above
# purely to be re-exported (consumed by tests and external callers); listing
# them here documents that and stops F401 from treating them as dead imports.
__all__ = [
    "STATUS_USAGE",
    "LOG_ROTATE_BYTES",
    "_format_blocking_quota",
    "_format_reset_time",
    "_format_status_detail",
    "_format_status_rows",
    "_pad_table",
    "_rotate_log_if_needed",
    "_visible_len",
    "cli_entry",
    "format_json_error",
    "main",
]


_COMMAND_HANDLERS = {
    "add": handle_add,
    "cp": handle_copy,
    "clean": handle_clean,
    "config": handle_config,
    "configs": handle_configs,
    "context": handle_context,
    "disk": handle_disk,
    "doctor": handle_doctor,
    "disable": handle_disable,
    "enable": handle_enable,
    "export": handle_export,
    "handoff": handle_handoff,
    "history": handle_history,
    "import": handle_import,
    "label": handle_label,
    "last": handle_last,
    "login": handle_login,
    "logout": handle_logout,
    "memory": handle_memory,
    "next": handle_next,
    "notify": handle_notify,
    "repair": handle_repair,
    "reset": handle_reset,
    "rename": handle_rename,
    "resume": handle_resume,
    "can-resume": handle_can_resume,
    "rmv": handle_remove,
    "run": handle_run,
    "run-report": handle_run_report,
    "run-status": handle_run_status,
    "run-tail": handle_run_tail,
    "runs": handle_runs,
    "schema": handle_schema,
    "select": handle_select,
    "set": handle_set,
    "stats": handle_stats,
    "status": handle_status,
    "tray": handle_tray,
    "unset": handle_unset,
    "update": handle_update,
    "view": handle_view,
}

_COMMAND_ALIASES = {
    "ren": "rename",
    "mv": "rename",
}

_SUPPRESS_UPDATE_NOTICE_COMMANDS = {
    *set(_COMMAND_HANDLERS),
    "fast",
    "help",
    "model",
    "perm",
    "power",
    "ready",
    "rename",
    "version",
} - {"status"}


def _resolve_command(command):
    return _COMMAND_ALIASES.get(command, command)


def _should_check_update_notices(command):
    return _resolve_command(command) not in _SUPPRESS_UPDATE_NOTICE_COMMANDS


# ---------------------------------------------------------------------------
# Help / version
# ---------------------------------------------------------------------------

def _print_help(use_color=False):
    return "\n".join([
        _style("cdx - terminal session manager", "1", use_color),
        "",
        _style("Usage:", "1", use_color),
        f"  {_style('cdx', '36', use_color)}",
        f"  {_style('cdx --json', '36', use_color)}",
        f"  {_style('cdx status [--json] [--refresh|--cached] [--timeout SECONDS]', '36', use_color)}",
        f"  {_style('cdx status --small|-s [--refresh|--cached] [--timeout SECONDS]', '36', use_color)}",
        f"  {_style('cdx status <name> [--json] [--refresh|--cached] [--timeout SECONDS]', '36', use_color)}",
        f"  {_style('cdx next [--json] [--refresh]', '36', use_color)}",
        f"  {_style('cdx reset <name> [--yes] [--json]', '36', use_color)}",
        f"  {_style('cdx select --provider PROVIDER [--min-reasoning-effort minimal|low|medium|high|xhigh] [--min-power minimal|low|medium|high|xhigh] [--require-ready] [--refresh] --json', '36', use_color)}",
        f"  {_style('cdx run [session] --cwd PATH (--prompt-file PATH|--prompt TEXT|--prompt-file -) [--provider PROVIDER] [--model MODEL] [--kind assistant|code-review] [--reasoning-effort minimal|low|medium|high|xhigh] [--power minimal|low|medium|high|xhigh] [--permission review|default|auto|full|workspace-write|read-only|danger-full-access] [--timeout-seconds N] [--detach] [--refresh] --json', '36', use_color)}",
        f"  {_style('cdx runs [--limit N] [--since 7d|today|DATE] --json', '36', use_color)}",
        f"  {_style('cdx run-status <run_id> --json', '36', use_color)}",
        f"  {_style('cdx run-report <run_id> --json', '36', use_color)}",
        f"  {_style('cdx run-tail <run_id> [--lines N] --json', '36', use_color)}",
        f"  {_style('cdx schema --json', '36', use_color)}",
        f"  {_style('cdx context show|path|init|edit|clear|set|append [text...] [--json]', '36', use_color)}",
        f"  {_style('cdx memory [--global|--project NAME_OR_PATH] [show|view|path|init|edit|clear|set|append|list] [text...] [--json]', '36', use_color)}",
        f"  {_style('cdx disk [profiles] [--candidates] [--json]', '36', use_color)}",
        f"  {_style('cdx config <name> [--json]', '36', use_color)}",
        f"  {_style('cdx configs [--json]', '36', use_color)}",
        f"  {_style('cdx power|perm|fast|model <name|all|provider:PROVIDER|a,b> <value|default> [--json]', '36', use_color)}",
        f"  {_style('cdx set <name>|--sessions all|a,b|--provider PROVIDER [--power minimal|low|medium|high|xhigh] [--permission review|default|auto|full] [--fast on|off] [--rtk on|off] [--logics on|off] [--notify on|off] [--notify-preview on|off] [--model MODEL] [--priority 0..100] [--json]', '36', use_color)}",
        f"  {_style('cdx unset <name>|--sessions all|a,b|--provider PROVIDER (--power|--permission|--fast|--rtk|--logics|--notify|--notify-preview|--model|--priority|--all) [--json]', '36', use_color)}",
        f"  {_style('cdx history [name] [--limit N] [--summary] [--since 7d|today|DATE] [--from DATE] [--to DATE] [--json]', '36', use_color)}",
        f"  {_style('cdx stats [name] [--since 7d|today|DATE] [--from DATE] [--to DATE] [--json]', '36', use_color)}",
        f"  {_style('cdx last [--json]', '36', use_color)}",
        f"  {_style('cdx resume <name> [--json]', '36', use_color)}",
        f"  {_style('cdx can-resume <name> [--json]', '36', use_color)}",
        f"  {_style('cdx handoff <name> [--json]', '36', use_color)}",
        f"  {_style('cdx handoff <source> <target> [--json]', '36', use_color)}",
        f"  {_style('cdx add [provider] <name> [--model MODEL] [--json]', '36', use_color)}",
        f"  {_style('cdx cp <source> <dest> [--json]', '36', use_color)}",
        f"  {_style('cdx ren <source> <dest> [--json]', '36', use_color)}",
        f"  {_style('cdx label <name> <label> [--json]', '36', use_color)}",
        f"  {_style('cdx label <name> --clear [--json]', '36', use_color)}",
        f"  {_style('cdx login <name> [--json]', '36', use_color)}",
        f"  {_style('cdx logout <name> [--json]', '36', use_color)}",
        f"  {_style('cdx disable <name> [--json]', '36', use_color)}",
        f"  {_style('cdx enable <name> [--json]', '36', use_color)}",
        f"  {_style('cdx rmv <name> [--force] [--json]', '36', use_color)}",
        f"  {_style('cdx clean [name] [--yes] [--json]', '36', use_color)}",
        f"  {_style('cdx clean profiles (--tmp|--old-logs DAYS) [--yes] [--json]', '36', use_color)}",
        f"  {_style('cdx export <file> [--include-auth] [--sessions a,b] [--passphrase-env VAR|--passphrase-stdin] [--force] [--json]', '36', use_color)}",
        f"  {_style('cdx import <file> [--sessions a,b] [--passphrase-env VAR|--passphrase-stdin] [--force|--merge] [--allow-authless-force] [--json]', '36', use_color)}",
        f"  {_style('cdx doctor [--severity OK|WARN|FAIL[,OK|WARN|FAIL...]] [--check-provider-flags] [--json]', '36', use_color)}",
        f"  {_style('cdx repair [--dry-run] [--force] [--json]', '36', use_color)}",
        f"  {_style('cdx view [--json]', '36', use_color)}",
        f"  {_style('cdx tray status [--json] [--refresh]', '36', use_color)}",
        f"  {_style('cdx tray install|launch|uninstall|doctor [--json]', '36', use_color)}",
        f"  {_style('cdx tray autostart [on|off|status] [--json]', '36', use_color)}",
        f"  {_style('cdx update [all] [--check] [--yes] [--json] [--version TAG]', '36', use_color)}",
        f"  {_style('cdx ready [--refresh] [--json]', '36', use_color)}",
        "",
        _style("Notifications:", "1", use_color),
        f"  {_style('cdx set <name> --notify on', '36', use_color)}  # agent finishes or needs attention",
        f"  {_style('cdx ready', '36', use_color)}  # next session to become ready",
        f"  {_style('cdx <name> [--json]', '36', use_color)}",
        f"  {_style('cdx --help', '36', use_color)}",
        f"  {_style('cdx --version', '36', use_color)}",
    ])


def _print_version():
    return VERSION


def wants_json(argv):
    return "--json" in argv


def format_json_error(error):
    message = str(error)
    # An error that already knows its own code keeps it. Only errors that never
    # declared one fall back to sniffing the message prefix below.
    declared = getattr(error, "code", None)
    if declared:
        allowed = getattr(error, "allowed", None)
        # Same field set as run_result_payload's error object, so a caller does
        # not need two shapes depending on which command raised.
        return json.dumps({
            "schema_version": API_SCHEMA_VERSION,
            "ok": False,
            "error": {
                "source": "cdx",
                "code": declared,
                "message": message,
                "arguments": list(getattr(error, "arguments", ()) or []),
                "allowed_values": list(allowed) if allowed else None,
                "exit_code": error.exit_code,
            },
        }, indent=2)
    code = "cdx_error"
    if message.startswith("Usage:"):
        code = "invalid_usage"
    elif message.startswith("Unknown session:"):
        code = "unknown_session"
    elif message.startswith("Unknown command:"):
        code = "unknown_command"
    elif message.startswith("Session already exists:"):
        code = "session_exists"
    elif message.startswith("Session is disabled:"):
        code = "session_disabled"
    elif "requires an interactive terminal" in message or "requires confirmation" in message:
        code = "interactive_terminal_required"
    return json.dumps({
        "schema_version": API_SCHEMA_VERSION,
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "exit_code": error.exit_code,
        },
    }, indent=2)


def _get_update_notice(service, env, options):
    checker = options.get("checkForUpdate") or check_for_update
    return checker(
        service["base_dir"],
        VERSION,
        env=env,
        now_fn=options.get("now"),
    )


def _get_update_notices(service, env, options):
    notices = []
    cdx_notice = _get_update_notice(service, env, options)
    if cdx_notice:
        notices.append({"tool": "cdx-manager", **cdx_notice})
    checker = options.get("checkLogicsManagerForUpdate") or check_logics_manager_for_update
    logics_notice = checker(
        service["base_dir"],
        env=env,
        now_fn=options.get("now"),
    )
    if logics_notice:
        notices.append(logics_notice)
    disk_notice = _get_disk_cleanup_notice(service, options)
    if disk_notice:
        notices.append(disk_notice)
    return notices


_DISK_CHECK_INTERVAL_SECONDS = 24 * 60 * 60
_DISK_HOME_THRESHOLD_BYTES = 10 * 1024 * 1024 * 1024
_DISK_RECLAIMABLE_THRESHOLD_BYTES = 1 * 1024 * 1024 * 1024
_DISK_CATEGORY_THRESHOLD_BYTES = 500 * 1024 * 1024
_DISK_PROFILE_THRESHOLD_BYTES = 2 * 1024 * 1024 * 1024


def _now_utc(options):
    now_fn = options.get("now")
    value = now_fn() if callable(now_fn) else None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _read_json_file(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _write_json_file(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp_path, path)


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _get_disk_cleanup_notice(service, options):
    checker = options.get("checkDiskCleanup")
    if callable(checker):
        return checker(service, options)

    base_dir = service["base_dir"]
    state_path = os.path.join(base_dir, "state", "disk-cleanup-check.json")
    now = _now_utc(options)
    state = _read_json_file(state_path)
    last_checked = _parse_iso_datetime(state.get("last_checked_at"))
    if last_checked and (now - last_checked).total_seconds() < _DISK_CHECK_INTERVAL_SECONDS:
        return None

    runner = options.get("diskUsageRunner")
    try:
        home_bytes = _directory_size_bytes(base_dir, runner=runner)
        profiles_dir = os.path.join(base_dir, "profiles")
        profile_rows = _directory_child_sizes(profiles_dir, runner=runner)
        profile_total = sum(row["bytes"] for row in profile_rows)
        candidates = _collect_profile_cleanup_candidates(base_dir, runner=runner, now=now.timestamp())
    except Exception:
        return None

    reclaimable_bytes = sum(item["bytes"] for item in candidates)
    tmp_bytes = sum(item["bytes"] for item in candidates if item["kind"].startswith("tmp-"))
    old_log_bytes = sum(item["bytes"] for item in candidates if item["kind"].startswith("old-logs-"))
    large_profiles = [
        {
            "name": row["name"],
            "bytes": row["bytes"],
            "size": _format_disk_bytes(row["bytes"]),
            "share_pct": round((row["bytes"] / profile_total) * 100, 1) if profile_total else 0,
        }
        for row in profile_rows
        if row["bytes"] >= _DISK_PROFILE_THRESHOLD_BYTES
        or (
            profile_total >= _DISK_RECLAIMABLE_THRESHOLD_BYTES
            and row["bytes"] / profile_total >= 0.25
        )
    ]
    triggered = (
        home_bytes >= _DISK_HOME_THRESHOLD_BYTES
        or reclaimable_bytes >= _DISK_RECLAIMABLE_THRESHOLD_BYTES
        or tmp_bytes >= _DISK_CATEGORY_THRESHOLD_BYTES
        or old_log_bytes >= _DISK_CATEGORY_THRESHOLD_BYTES
        or bool(large_profiles)
    )
    state_payload = {
        "last_checked_at": now.isoformat(),
        "home_bytes": home_bytes,
        "reclaimable_bytes": reclaimable_bytes,
        "tmp_bytes": tmp_bytes,
        "old_log_bytes": old_log_bytes,
        "large_profiles": large_profiles,
    }
    try:
        _write_json_file(state_path, state_payload)
    except OSError:
        pass
    if not triggered:
        return None

    if reclaimable_bytes > 0:
        message = (
            f"Disk cleanup available: {_format_disk_bytes(reclaimable_bytes)} reclaimable "
            f"in CDX profiles. Inspect: cdx disk profiles --candidates"
        )
    else:
        message = (
            f"CDX_HOME uses {_format_disk_bytes(home_bytes)}. "
            "Inspect: cdx disk profiles --candidates"
        )
    if tmp_bytes >= _DISK_CATEGORY_THRESHOLD_BYTES:
        message = (
            f"{message}. Safe temp cleanup: {_format_disk_bytes(tmp_bytes)} "
            "with cdx clean profiles --tmp"
        )
    if old_log_bytes >= _DISK_CATEGORY_THRESHOLD_BYTES:
        message = (
            f"{message}. Old logs: {_format_disk_bytes(old_log_bytes)} "
            "with cdx clean profiles --old-logs 30d"
        )
    return {
        "tool": "cdx-disk",
        "code": "disk_cleanup_available",
        "message": message,
        "reclaimable_bytes": reclaimable_bytes,
        "reclaimable_size": _format_disk_bytes(reclaimable_bytes),
        "home_bytes": home_bytes,
        "home_size": _format_disk_bytes(home_bytes),
        "tmp_bytes": tmp_bytes,
        "tmp_size": _format_disk_bytes(tmp_bytes),
        "old_log_bytes": old_log_bytes,
        "old_log_size": _format_disk_bytes(old_log_bytes),
        "large_profiles": large_profiles,
        "inspect_command": "cdx disk profiles --candidates",
        "cleanup_tmp_command": "cdx clean profiles --tmp" if tmp_bytes >= _DISK_CATEGORY_THRESHOLD_BYTES else None,
        "cleanup_old_logs_command": "cdx clean profiles --old-logs 30d" if old_log_bytes >= _DISK_CATEGORY_THRESHOLD_BYTES else None,
    }


def _update_warning_text(notices):
    payloads = _update_notice_warnings({"update_notices": notices or [], "version": VERSION})
    if not payloads:
        return None
    return "\n".join(payload["message"] for payload in payloads)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main(argv, options=None):
    if options is None:
        options = {}

    env = options.get("env", os.environ)
    stdout = options.get("stdout", sys.stdout)
    stderr = options.get("stderr", sys.stderr)
    stdin_is_tty = options.get("stdin", {}).get("isTTY", hasattr(sys.stdin, "isatty") and sys.stdin.isatty())
    use_color = _should_use_color(env, stdout)
    service = options.get("service") or create_session_service({"env": env})
    spawn = options.get("spawn")
    spawn_sync = options.get("spawn_sync")
    refresh_fn = options.get("refreshClaudeSessionStatus")
    signal_emitter = options.get("signalEmitter")

    def out(text):
        stdout.write(text)

    def err(text):
        stderr.write(text)

    # Flags — only when leading, so 'cdx history -h' reaches the subcommand
    # instead of being hijacked as a malformed top-level help call.
    if argv[:1] in (["--help"], ["-h"]):
        if len(argv) != 1:
            raise CdxError("Usage: cdx --help")
        out(f"{_print_help(use_color=use_color)}\n")
        return 0

    if argv[:1] in (["--version"], ["-v"]):
        if len(argv) != 1:
            raise CdxError("Usage: cdx --version")
        out(f"{_print_version()}\n")
        return 0

    if argv == ["--json"]:
        rows = service["format_list_rows"]()
        notices = _get_update_notices(service, env, options)
        out(f"{json.dumps(_list_json_payload(rows, notices=notices), indent=2)}\n")
        return 0

    if not argv:
        notices = _get_update_notices(service, env, options)
        out(f"{_format_sessions(service, use_color=use_color)}\n")
        warning_text = _update_warning_text(notices)
        if warning_text:
            out(f"{_style(warning_text, '33', use_color)}\n")
        return 0

    command, *rest = argv
    resolved_command = _resolve_command(command)
    ctx = {
        "env": env,
        "options": options,
        "raw_args": argv,
        "err": err,
        "out": out,
        "refresh_fn": refresh_fn,
        "service": service,
        "signal_emitter": signal_emitter,
        "spawn": spawn,
        "spawn_detached": options.get("spawn_detached"),
        "spawn_headless": options.get("spawn_headless"),
        # Stream `--prompt-file -` reads from. Distinct from "stdin", which is
        # the {"isTTY": ...} descriptor the interactive paths use.
        "prompt_stdin": options.get("prompt_stdin"),
        "spawn_sync": spawn_sync,
        "stdin_is_tty": stdin_is_tty,
        "version": VERSION,
        "cwd": options.get("cwd") or os.getcwd(),
        "update_notices": _get_update_notices(service, env, options) if _should_check_update_notices(command) else None,
        "use_color": use_color,
    }

    if resolved_command == "ready":
        return handle_ready(rest, ctx)

    if resolved_command in ("power", "perm", "fast", "model"):
        return handle_launch_setting_alias(resolved_command, rest, ctx)

    if resolved_command == "help":
        out(f"{_print_help(use_color=use_color)}\n")
        return 0

    if resolved_command == "version":
        out(f"{_print_version()}\n")
        return 0

    handler = _COMMAND_HANDLERS.get(resolved_command)
    if handler:
        return handler(rest, ctx)

    if all(arg in ("--json", "-r", "--resume") for arg in rest):
        return handle_launch(command, ctx, resume=("-r" in rest or "--resume" in rest))

    raise CdxError(f"Unknown command: {command}. Use cdx --help.")


def _list_json_payload(rows, notices=None):
    return {
        "schema_version": API_SCHEMA_VERSION,
        "ok": True,
        "action": "list",
        "message": "Listed known sessions",
        "warnings": _update_notice_warnings({"update_notices": notices or [], "version": VERSION}),
        "sessions": rows,
    }


def _enable_windows_ansi():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        for handle_id in (-10, -11, -12):  # stdin, stdout, stderr
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _configure_windows_encoding():
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def cli_entry():
    _enable_windows_ansi()
    _configure_windows_encoding()
    try:
        raise SystemExit(main(sys.argv[1:]))
    except CdxError as error:
        if wants_json(sys.argv[1:]):
            sys.stderr.write(f"{format_json_error(error)}\n")
        else:
            sys.stderr.write(f"{format_error(error)}\n")
        raise SystemExit(error.exit_code) from None


if __name__ == "__main__":
    cli_entry()
