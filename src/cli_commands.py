import asyncio
import json
import os
from datetime import datetime

from .claude_refresh import _refresh_claude_sessions
from .cli_render import _dim, _info, _success, _warn
from .errors import CdxError
from .provider_runtime import (
    _ensure_session_authentication,
    _list_launch_transcript_paths,
    _run_interactive_provider_command,
)
from .status_view import _format_status_detail, _format_status_rows


STATUS_USAGE = "Usage: cdx status [--json] [--refresh] | cdx status --small|-s [--refresh] | cdx status <name> [--json] [--refresh]"


def _local_now_iso():
    return datetime.now().astimezone().isoformat()


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


def _resolve_confirmation(confirm_fn, name):
    confirmed = (
        asyncio.get_event_loop().run_until_complete(confirm_fn(name))
        if asyncio.iscoroutinefunction(confirm_fn)
        else confirm_fn(name)
    )
    if hasattr(confirmed, "__await__"):
        confirmed = asyncio.get_event_loop().run_until_complete(confirmed)
    return confirmed


def handle_add(rest, ctx):
    parsed = _parse_add_args(rest)
    session = ctx["service"]["create_session"](parsed["name"], parsed["provider"])
    message = f"Created session {parsed['name']} ({parsed['provider']})"
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    _ensure_session_authentication(
        session,
        ctx["service"],
        spawn=ctx.get("spawn"),
        spawn_sync=ctx.get("spawn_sync"),
        stdin_is_tty=ctx["stdin_is_tty"],
        behavior="bootstrap",
        signal_emitter=ctx.get("signal_emitter"),
    )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](parsed["name"], lambda auth: {
        **auth,
        "status": "authenticated",
        "lastCheckedAt": now,
        "lastAuthenticatedAt": now,
        "lastLoggedOutAt": auth.get("lastLoggedOutAt"),
    })
    return 0


def handle_copy(rest, ctx):
    parsed = _parse_copy_args(rest)
    result = ctx["service"]["copy_session"](parsed["source"], parsed["dest"])
    overwritten = " (overwritten)" if result["overwritten"] else ""
    message = f"Copied session {parsed['source']} to {parsed['dest']}{overwritten}"
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_rename(rest, ctx):
    parsed = _parse_rename_args(rest)
    ctx["service"]["rename_session"](parsed["source"], parsed["dest"])
    message = f"Renamed session {parsed['source']} to {parsed['dest']}"
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_remove(rest, ctx):
    parsed = _parse_remove_args(rest)
    if not parsed["force"]:
        confirm_fn = ctx["options"].get("confirmRemove")
        if confirm_fn:
            confirmed = _resolve_confirmation(confirm_fn, parsed["name"])
        elif not ctx["stdin_is_tty"]:
            raise CdxError("Removal requires confirmation in an interactive terminal or --force in non-interactive mode.")
        else:
            confirmed = _confirm_removal(parsed["name"])
        if not confirmed:
            ctx["out"](f"{_warn('Cancelled.', ctx['use_color'])}\n")
            return 0
    ctx["service"]["remove_session"](parsed["name"])
    message = f"Removed session {parsed['name']}"
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_clean(rest, ctx):
    service = ctx["service"]
    if len(rest) == 0:
        targets = service["list_sessions"]()
    elif len(rest) == 1:
        session = service["get_session"](rest[0])
        if not session:
            raise CdxError(f"Unknown session: {rest[0]}")
        targets = [session]
    else:
        raise CdxError("Usage: cdx clean [name]")

    for session in targets:
        log_paths = _list_launch_transcript_paths(session)
        if not log_paths:
            message = f"{session['name']}: no log found"
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
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
            ctx["out"](f"{_success(message, ctx['use_color'])}\n")
        else:
            message = f"{session['name']}: no log found"
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
    return 0


def handle_status(rest, ctx):
    json_flag = "--json" in rest
    small_flag = "--small" in rest or "-s" in rest
    refresh_flag = "--refresh" in rest
    status_flags = {"--json", "--small", "-s", "--refresh"}
    args = [a for a in rest if a not in status_flags]
    unknown_flags = [a for a in args if a.startswith("-")]
    if unknown_flags or (json_flag and small_flag):
        raise CdxError(STATUS_USAGE)
    if len(args) > 1 or (len(args) == 1 and small_flag):
        raise CdxError(STATUS_USAGE)

    refresh_result = _refresh_claude_sessions(
        ctx["service"],
        ctx.get("refresh_fn"),
        target_names=args if len(args) == 1 else None,
        force=refresh_flag,
    )
    refresh_errors = [
        {
            "session": item.get("session"),
            "error": str(item.get("error")),
        }
        for item in refresh_result.get("errors", [])
    ]

    rows = ctx["service"]["get_status_rows"]()
    if len(args) == 0:
        if json_flag:
            payload = rows
            if refresh_errors:
                payload = {"rows": rows, "refresh_errors": refresh_errors}
            ctx["out"](f"{json.dumps(payload, indent=2)}\n")
            return 0
        ctx["out"](f"{_format_status_rows(rows, use_color=ctx['use_color'], small=small_flag)}\n")
        _write_refresh_warnings(refresh_errors, ctx)
        return 0

    row = next((r for r in rows if r["session_name"] == args[0]), None)
    if not row:
        raise CdxError(f"Unknown session: {args[0]}")
    if json_flag:
        payload = row
        if refresh_errors:
            payload = {"row": row, "refresh_errors": refresh_errors}
        ctx["out"](f"{json.dumps(payload, indent=2)}\n")
        return 0
    ctx["out"](f"{_format_status_detail(row, use_color=ctx['use_color'])}\n")
    _write_refresh_warnings(refresh_errors, ctx)
    return 0


def _write_refresh_warnings(refresh_errors, ctx):
    for item in refresh_errors:
        session = item.get("session") or "unknown"
        error = item.get("error") or "unknown error"
        ctx["out"](f"{_warn(f'Warning: Claude refresh failed for {session}: {error}', ctx['use_color'])}\n")


def handle_login(rest, ctx):
    if len(rest) != 1:
        raise CdxError("Usage: cdx login <name>")
    if not ctx["stdin_is_tty"]:
        raise CdxError("Login requires an interactive terminal.")
    session = ctx["service"]["get_session"](rest[0])
    if not session:
        raise CdxError(f"Unknown session: {rest[0]}")
    _run_interactive_provider_command(
        session, "logout", spawn=ctx.get("spawn"), signal_emitter=ctx.get("signal_emitter")
    )
    _run_interactive_provider_command(
        session, "login", spawn=ctx.get("spawn"), signal_emitter=ctx.get("signal_emitter")
    )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](rest[0], lambda auth: {
        **auth, "status": "authenticated",
        "lastCheckedAt": now, "lastAuthenticatedAt": now,
    })
    message = f"Reauthenticated session {session['name']} ({session['provider']})"
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_logout(rest, ctx):
    if len(rest) != 1:
        raise CdxError("Usage: cdx logout <name>")
    session = ctx["service"]["get_session"](rest[0])
    if not session:
        raise CdxError(f"Unknown session: {rest[0]}")
    _run_interactive_provider_command(
        session, "logout", spawn=ctx.get("spawn"), signal_emitter=ctx.get("signal_emitter")
    )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](rest[0], lambda auth: {
        **auth, "status": "logged_out",
        "lastCheckedAt": now, "lastLoggedOutAt": now,
    })
    message = f"Logged out session {session['name']} ({session['provider']})"
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_launch(command, ctx):
    session = ctx["service"]["launch_session"](command)
    _ensure_session_authentication(
        session,
        ctx["service"],
        spawn=ctx.get("spawn"),
        spawn_sync=ctx.get("spawn_sync"),
        stdin_is_tty=ctx["stdin_is_tty"],
        behavior="launch",
        signal_emitter=ctx.get("signal_emitter"),
    )
    message = f"Launching {session['provider']} session {session['name']}"
    ctx["out"](f"{_info(message, ctx['use_color'])}\n")
    if session["provider"] == "codex":
        ctx["out"](f"{_dim('Tip: run /status once the Codex session opens.', ctx['use_color'])}\n")
    _run_interactive_provider_command(
        session, "launch", spawn=ctx.get("spawn"), signal_emitter=ctx.get("signal_emitter")
    )
    return 0
