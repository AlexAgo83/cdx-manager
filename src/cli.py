#!/usr/bin/env python3

import json
import os
import sys

from .cli_commands import (
    API_SCHEMA_VERSION,
    STATUS_USAGE,
    handle_add,
    handle_clean,
    handle_copy,
    handle_doctor,
    handle_launch,
    handle_login,
    handle_logout,
    handle_notify,
    handle_remove,
    handle_repair,
    handle_rename,
    handle_status,
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
from .update_check import check_for_update

VERSION = "0.3.4"


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
        f"  {_style('cdx status [--json] [--refresh]', '36', use_color)}",
        f"  {_style('cdx status --small|-s [--refresh]', '36', use_color)}",
        f"  {_style('cdx status <name> [--json] [--refresh]', '36', use_color)}",
        f"  {_style('cdx add [provider] <name> [--json]', '36', use_color)}",
        f"  {_style('cdx cp <source> <dest> [--json]', '36', use_color)}",
        f"  {_style('cdx ren <source> <dest> [--json]', '36', use_color)}",
        f"  {_style('cdx login <name> [--json]', '36', use_color)}",
        f"  {_style('cdx logout <name> [--json]', '36', use_color)}",
        f"  {_style('cdx rmv <name> [--force] [--json]', '36', use_color)}",
        f"  {_style('cdx clean [name] [--json]', '36', use_color)}",
        f"  {_style('cdx doctor [--json]', '36', use_color)}",
        f"  {_style('cdx repair [--dry-run] [--force] [--json]', '36', use_color)}",
        f"  {_style('cdx notify <name> --at-reset [--json]', '36', use_color)}",
        f"  {_style('cdx notify --next-ready [--json]', '36', use_color)}",
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


def _update_warning_payload(notice):
    if not notice:
        return []
    message = f"Update available: cdx-manager {notice['latest_version']} (current {VERSION})"
    return [{
        "code": "update_available",
        "message": message,
        "latest_version": notice["latest_version"],
        "url": notice.get("url"),
    }]


def _update_warning_text(notice):
    if not notice:
        return None
    suffix = f" {notice['url']}" if notice.get("url") else ""
    return f"Update available: cdx-manager {notice['latest_version']} (current {VERSION}).{suffix}"


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
        notice = _get_update_notice(service, env, options)
        out(f"{json.dumps(_list_json_payload(rows, notice=notice), indent=2)}\n")
        return 0

    if not argv:
        notice = _get_update_notice(service, env, options)
        out(f"{_format_sessions(service, use_color=use_color)}\n")
        if notice:
            out(f"{_style(_update_warning_text(notice), '33', use_color)}\n")
        return 0

    command, *rest = argv
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
        "spawn_sync": spawn_sync,
        "stdin_is_tty": stdin_is_tty,
        "update_notice": _get_update_notice(service, env, options) if command not in (
            "add", "cp", "ren", "rename", "mv", "rmv", "clean", "doctor", "repair", "notify", "status", "login", "logout", "help", "version"
        ) else None,
        "use_color": use_color,
    }

    if command == "add":
        return handle_add(rest, ctx)

    if command == "cp":
        return handle_copy(rest, ctx)

    if command in ("ren", "rename", "mv"):
        return handle_rename(rest, ctx)

    if command == "rmv":
        return handle_remove(rest, ctx)

    if command == "clean":
        return handle_clean(rest, ctx)

    if command == "doctor":
        return handle_doctor(rest, ctx)

    if command == "repair":
        return handle_repair(rest, ctx)

    if command == "notify":
        return handle_notify(rest, ctx)

    if command == "status":
        return handle_status(rest, ctx)

    if command == "login":
        return handle_login(rest, ctx)

    if command == "logout":
        return handle_logout(rest, ctx)

    if command in ("help",):
        out(f"{_print_help(use_color=use_color)}\n")
        return 0

    if command in ("version",):
        out(f"{_print_version()}\n")
        return 0

    if not rest or rest == ["--json"]:
        return handle_launch(command, ctx)

    raise CdxError(f"Unknown command: {command}. Use cdx --help.")


def _list_json_payload(rows, notice=None):
    return {
        "schema_version": API_SCHEMA_VERSION,
        "ok": True,
        "action": "list",
        "message": "Listed known sessions",
        "warnings": _update_warning_payload(notice),
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
