#!/usr/bin/env python3

import json
import os
import sys

from .cli_commands import (
    API_SCHEMA_VERSION,
    STATUS_USAGE,
    handle_add,
    handle_clean,
    handle_config,
    handle_configs,
    handle_can_resume,
    handle_context,
    handle_copy,
    handle_doctor,
    handle_disable,
    handle_enable,
    handle_export,
    handle_import,
    handle_handoff,
    handle_history,
    handle_last,
    handle_launch,
    handle_login,
    handle_logout,
    handle_launch_setting_alias,
    handle_notify,
    handle_next,
    handle_remove,
    handle_repair,
    handle_rename,
    handle_resume,
    handle_run,
    handle_run_report,
    handle_run_status,
    handle_runs,
    handle_select,
    handle_stats,
    handle_status,
    handle_set,
    handle_unset,
    handle_update,
    handle_view,
)
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

VERSION = "0.9.8"


_COMMAND_HANDLERS = {
    "add": handle_add,
    "cp": handle_copy,
    "clean": handle_clean,
    "config": handle_config,
    "configs": handle_configs,
    "context": handle_context,
    "doctor": handle_doctor,
    "disable": handle_disable,
    "enable": handle_enable,
    "export": handle_export,
    "handoff": handle_handoff,
    "history": handle_history,
    "import": handle_import,
    "last": handle_last,
    "login": handle_login,
    "logout": handle_logout,
    "next": handle_next,
    "notify": handle_notify,
    "repair": handle_repair,
    "rename": handle_rename,
    "resume": handle_resume,
    "can-resume": handle_can_resume,
    "rmv": handle_remove,
    "run": handle_run,
    "run-report": handle_run_report,
    "run-status": handle_run_status,
    "runs": handle_runs,
    "select": handle_select,
    "set": handle_set,
    "stats": handle_stats,
    "status": handle_status,
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
        f"  {_style('cdx select --provider PROVIDER [--min-reasoning-effort minimal|low|medium|high|xhigh] [--min-power minimal|low|medium|high|xhigh] [--require-ready] [--refresh] --json', '36', use_color)}",
        f"  {_style('cdx run [session] --cwd PATH (--prompt-file PATH|--prompt TEXT) [--provider PROVIDER] [--model MODEL] [--reasoning-effort minimal|low|medium|high|xhigh] [--power minimal|low|medium|high|xhigh] [--permission review|default|auto|full|workspace-write|read-only|danger-full-access] [--timeout-seconds N] --json', '36', use_color)}",
        f"  {_style('cdx runs [--limit N] --json', '36', use_color)}",
        f"  {_style('cdx run-status <run_id> --json', '36', use_color)}",
        f"  {_style('cdx run-report <run_id> --json', '36', use_color)}",
        f"  {_style('cdx context show|path|init|edit|clear|set [text...] [--json]', '36', use_color)}",
        f"  {_style('cdx config <name> [--json]', '36', use_color)}",
        f"  {_style('cdx configs [--json]', '36', use_color)}",
        f"  {_style('cdx power|perm|fast|model <name|all|provider:PROVIDER|a,b> <value|default> [--json]', '36', use_color)}",
        f"  {_style('cdx set <name>|--sessions all|a,b|--provider PROVIDER [--power minimal|low|medium|high|xhigh] [--permission review|default|auto|full] [--fast on|off] [--rtk on|off] [--logics on|off] [--model MODEL] [--priority 0..100] [--json]', '36', use_color)}",
        f"  {_style('cdx unset <name>|--sessions all|a,b|--provider PROVIDER (--power|--permission|--fast|--rtk|--logics|--model|--priority|--all) [--json]', '36', use_color)}",
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
        f"  {_style('cdx login <name> [--json]', '36', use_color)}",
        f"  {_style('cdx logout <name> [--json]', '36', use_color)}",
        f"  {_style('cdx disable <name> [--json]', '36', use_color)}",
        f"  {_style('cdx enable <name> [--json]', '36', use_color)}",
        f"  {_style('cdx rmv <name> [--force] [--json]', '36', use_color)}",
        f"  {_style('cdx clean [name] [--json]', '36', use_color)}",
        f"  {_style('cdx export <file> [--include-auth] [--sessions a,b] [--passphrase-env VAR] [--force] [--json]', '36', use_color)}",
        f"  {_style('cdx import <file> [--sessions a,b] [--passphrase-env VAR] [--force|--merge] [--json]', '36', use_color)}",
        f"  {_style('cdx doctor [--json]', '36', use_color)}",
        f"  {_style('cdx repair [--dry-run] [--force] [--json]', '36', use_color)}",
        f"  {_style('cdx view [--json]', '36', use_color)}",
        f"  {_style('cdx update [--check] [--yes] [--json] [--version TAG]', '36', use_color)}",
        f"  {_style('cdx ready [--refresh] [--json]', '36', use_color)}",
        f"  {_style('cdx notify <name> --at-reset [--schedule] [--refresh] [--json]', '36', use_color)}",
        f"  {_style('cdx notify --next-ready [--schedule] [--refresh] [--json]', '36', use_color)}",
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
    return notices


def _update_warning_payload(notices):
    if isinstance(notices, dict):
        notices = [notices]
    if not notices:
        return []
    warnings = []
    for notice in notices:
        tool = notice.get("tool") or "cdx-manager"
        current = notice.get("current_version") or VERSION
        command = notice.get("update_command") or ("cdx update" if tool == "cdx-manager" else None)
        message = f"Update available: {tool} {notice['latest_version']} (current {current})"
        if command:
            message = f"{message}. Run: {command}"
        warnings.append({
            "code": "update_available" if tool == "cdx-manager" else f"{tool.replace('-', '_')}_update_available",
            "message": message,
            "tool": tool,
            "latest_version": notice["latest_version"],
            "current_version": current,
            "update_command": command,
            "url": notice.get("url"),
        })
    return warnings


def _update_warning_text(notices):
    payloads = _update_warning_payload(notices)
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

    # Flags
    if "--help" in argv or "-h" in argv:
        if len(argv) != 1:
            raise CdxError("Usage: cdx --help")
        out(f"{_print_help(use_color=use_color)}\n")
        return 0

    if "--version" in argv or "-v" in argv:
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
        "spawn_headless": options.get("spawn_headless"),
        "spawn_sync": spawn_sync,
        "stdin_is_tty": stdin_is_tty,
        "version": VERSION,
        "cwd": options.get("cwd") or os.getcwd(),
        "update_notices": _get_update_notices(service, env, options) if _should_check_update_notices(command) else None,
        "use_color": use_color,
    }

    if resolved_command == "ready":
        if any(arg not in ("--refresh", "--json") for arg in rest):
            raise CdxError("Usage: cdx ready [--refresh] [--json]")
        return handle_notify(["--next-ready", "--schedule", *rest], ctx)

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
        "warnings": _update_warning_payload(notices),
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
        raise SystemExit(error.exit_code)


if __name__ == "__main__":
    cli_entry()
