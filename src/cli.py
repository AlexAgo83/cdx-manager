#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime

from .claude_refresh import _refresh_claude_sessions
from .cli_render import (
    _dim,
    _format_sessions,
    _info,
    _pad_table,
    _should_use_color,
    _style,
    _success,
    _visible_len,
    _warn,
    format_error,
)
from .errors import CdxError
from .provider_runtime import (
    LOG_ROTATE_BYTES,
    _ensure_session_authentication,
    _list_launch_transcript_paths,
    _rotate_log_if_needed,
    _run_interactive_provider_command,
)
from .session_service import create_session_service
from .status_view import (
    _format_blocking_quota,
    _format_reset_time,
    _format_status_detail,
    _format_status_rows,
)

VERSION = "0.1.1"
STATUS_USAGE = "Usage: cdx status [--json] | cdx status --small|-s | cdx status <name> [--json]"


# ---------------------------------------------------------------------------
# Help / version
# ---------------------------------------------------------------------------

def _print_help(use_color=False):
    return "\n".join([
        _style("cdx - terminal session manager", "1", use_color),
        "",
        _style("Usage:", "1", use_color),
        f"  {_style('cdx', '36', use_color)}",
        f"  {_style('cdx status [--json]', '36', use_color)}",
        f"  {_style('cdx status --small|-s', '36', use_color)}",
        f"  {_style('cdx status <name> [--json]', '36', use_color)}",
        f"  {_style('cdx add [provider] <name>', '36', use_color)}",
        f"  {_style('cdx cp <source> <dest>', '36', use_color)}",
        f"  {_style('cdx ren <source> <dest>', '36', use_color)}",
        f"  {_style('cdx login <name>', '36', use_color)}",
        f"  {_style('cdx logout <name>', '36', use_color)}",
        f"  {_style('cdx rmv <name> [--force]', '36', use_color)}",
        f"  {_style('cdx clean [name]', '36', use_color)}",
        f"  {_style('cdx <name>', '36', use_color)}",
        f"  {_style('cdx --help', '36', use_color)}",
        f"  {_style('cdx --version', '36', use_color)}",
    ])


def _print_version():
    return VERSION


def _local_now_iso():
    return datetime.now().astimezone().isoformat()


# ---------------------------------------------------------------------------
# Argument helpers
# ---------------------------------------------------------------------------

def _parse_add_args(args):
    if len(args) == 1:
        return {"provider": "codex", "name": args[0]}
    if len(args) == 2:
        return {"provider": args[0], "name": args[1]}
    raise CdxError("Usage: cdx add [provider] <name>")


def _parse_copy_args(args):
    if len(args) != 2:
        raise CdxError("Usage: cdx cp <source> <dest>")
    return {"source": args[0], "dest": args[1]}


def _parse_rename_args(args):
    if len(args) != 2:
        raise CdxError("Usage: cdx ren <source> <dest>")
    return {"source": args[0], "dest": args[1]}


def _parse_remove_args(args):
    force = "--force" in args
    names = [a for a in args if a != "--force"]
    unknown = [a for a in args if a.startswith("-") and a != "--force"]
    if unknown or len(names) != 1 or len(args) > 2:
        raise CdxError("Usage: cdx rmv <name> [--force]")
    return {"name": names[0], "force": force}


def _confirm_removal(name):
    answer = input(f"Remove session {name}? [y/N] ")
    return answer.strip().lower() in ("y", "yes")


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

    if not argv:
        out(f"{_format_sessions(service, use_color=use_color)}\n")
        return 0

    command, *rest = argv

    if command == "add":
        parsed = _parse_add_args(rest)
        session = service["create_session"](parsed["name"], parsed["provider"])
        message = f"Created session {parsed['name']} ({parsed['provider']})"
        out(f"{_success(message, use_color)}\n")
        _ensure_session_authentication(
            session, service, spawn=spawn, spawn_sync=spawn_sync,
            stdin_is_tty=stdin_is_tty, behavior="bootstrap", signal_emitter=signal_emitter,
        )
        now = _local_now_iso()
        service["update_auth_state"](parsed["name"], lambda auth: {
            **auth,
            "status": "authenticated",
            "lastCheckedAt": now,
            "lastAuthenticatedAt": now,
            "lastLoggedOutAt": auth.get("lastLoggedOutAt"),
        })
        return 0

    if command == "cp":
        parsed = _parse_copy_args(rest)
        result = service["copy_session"](parsed["source"], parsed["dest"])
        overwritten = " (overwritten)" if result["overwritten"] else ""
        message = f"Copied session {parsed['source']} to {parsed['dest']}{overwritten}"
        out(f"{_success(message, use_color)}\n")
        return 0

    if command in ("ren", "rename", "mv"):
        parsed = _parse_rename_args(rest)
        service["rename_session"](parsed["source"], parsed["dest"])
        message = f"Renamed session {parsed['source']} to {parsed['dest']}"
        out(f"{_success(message, use_color)}\n")
        return 0

    if command == "rmv":
        parsed = _parse_remove_args(rest)
        if not parsed["force"]:
            confirm_fn = options.get("confirmRemove")
            if confirm_fn:
                import asyncio
                confirmed = asyncio.get_event_loop().run_until_complete(confirm_fn(parsed["name"])) \
                    if asyncio.iscoroutinefunction(confirm_fn) else confirm_fn(parsed["name"])
                # Handle both coroutine and plain return
                if hasattr(confirmed, "__await__"):
                    import asyncio
                    confirmed = asyncio.get_event_loop().run_until_complete(confirmed)
            elif not stdin_is_tty:
                raise CdxError("Removal requires confirmation in an interactive terminal or --force in non-interactive mode.")
            else:
                confirmed = _confirm_removal(parsed["name"])
            if not confirmed:
                out(f"{_warn('Cancelled.', use_color)}\n")
                return 0
        service["remove_session"](parsed["name"])
        message = f"Removed session {parsed['name']}"
        out(f"{_success(message, use_color)}\n")
        return 0

    if command == "clean":
        if len(rest) == 0:
            targets = service["list_sessions"]()
        elif len(rest) == 1:
            s = service["get_session"](rest[0])
            if not s:
                raise CdxError(f"Unknown session: {rest[0]}")
            targets = [s]
        else:
            raise CdxError("Usage: cdx clean [name]")
        for session in targets:
            log_paths = _list_launch_transcript_paths(session)
            if not log_paths:
                message = f"{session['name']}: no log found"
                out(f"{_dim(message, use_color)}\n")
                continue
            total_size = 0
            cleared = 0
            for log_path in log_paths:
                try:
                    total_size += os.path.getsize(log_path)
                    open(log_path, "w").close()
                    cleared += 1
                except OSError:
                    continue
            if cleared:
                message = (
                    f"Cleared {session['name']} logs ({cleared} file"
                    f"{'' if cleared == 1 else 's'}, {round(total_size / 1024)} KB freed)"
                )
                out(f"{_success(message, use_color)}\n")
            else:
                message = f"{session['name']}: no log found"
                out(f"{_dim(message, use_color)}\n")
        return 0

    if command == "status":
        json_flag = "--json" in rest
        small_flag = "--small" in rest or "-s" in rest
        status_flags = {"--json", "--small", "-s"}
        args = [a for a in rest if a not in status_flags]
        unknown_flags = [a for a in args if a.startswith("-")]
        if unknown_flags or (json_flag and small_flag):
            raise CdxError(STATUS_USAGE)
        if len(args) > 1 or (len(args) == 1 and small_flag):
            raise CdxError(STATUS_USAGE)

        _refresh_claude_sessions(service, refresh_fn)

        if len(args) == 0:
            rows = service["get_status_rows"]()
            if json_flag:
                out(f"{json.dumps(rows, indent=2)}\n")
                return 0
            out(f"{_format_status_rows(rows, use_color=use_color, small=small_flag)}\n")
            return 0
        rows = service["get_status_rows"]()
        row = next((r for r in rows if r["session_name"] == args[0]), None)
        if not row:
            raise CdxError(f"Unknown session: {args[0]}")
        if json_flag:
            out(f"{json.dumps(row, indent=2)}\n")
            return 0
        out(f"{_format_status_detail(row, use_color=use_color)}\n")
        return 0

    if command == "login":
        if len(rest) != 1:
            raise CdxError("Usage: cdx login <name>")
        if not stdin_is_tty:
            raise CdxError("Login requires an interactive terminal.")
        session = service["get_session"](rest[0])
        if not session:
            raise CdxError(f"Unknown session: {rest[0]}")
        _run_interactive_provider_command(session, "logout", spawn=spawn, signal_emitter=signal_emitter)
        _run_interactive_provider_command(session, "login", spawn=spawn, signal_emitter=signal_emitter)
        now = _local_now_iso()
        service["update_auth_state"](rest[0], lambda auth: {
            **auth, "status": "authenticated",
            "lastCheckedAt": now, "lastAuthenticatedAt": now,
        })
        message = f"Reauthenticated session {session['name']} ({session['provider']})"
        out(f"{_success(message, use_color)}\n")
        return 0

    if command == "logout":
        if len(rest) != 1:
            raise CdxError("Usage: cdx logout <name>")
        session = service["get_session"](rest[0])
        if not session:
            raise CdxError(f"Unknown session: {rest[0]}")
        _run_interactive_provider_command(session, "logout", spawn=spawn, signal_emitter=signal_emitter)
        now = _local_now_iso()
        service["update_auth_state"](rest[0], lambda auth: {
            **auth, "status": "logged_out",
            "lastCheckedAt": now, "lastLoggedOutAt": now,
        })
        message = f"Logged out session {session['name']} ({session['provider']})"
        out(f"{_success(message, use_color)}\n")
        return 0

    if command in ("help",):
        out(f"{_print_help(use_color=use_color)}\n")
        return 0

    if command in ("version",):
        out(f"{_print_version()}\n")
        return 0

    if not rest:
        session = service["launch_session"](command)
        _ensure_session_authentication(
            session, service, spawn=spawn, spawn_sync=spawn_sync,
            stdin_is_tty=stdin_is_tty, behavior="launch", signal_emitter=signal_emitter,
        )
        message = f"Launching {session['provider']} session {session['name']}"
        out(f"{_info(message, use_color)}\n")
        if session["provider"] == "codex":
            out(f"{_dim('Tip: run /status once the Codex session opens.', use_color)}\n")
        _run_interactive_provider_command(session, "launch", spawn=spawn, signal_emitter=signal_emitter)
        return 0

    raise CdxError(f"Unknown command: {command}. Use cdx --help.")


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except CdxError as error:
        sys.stderr.write(f"{format_error(error)}\n")
        raise SystemExit(error.exit_code)
