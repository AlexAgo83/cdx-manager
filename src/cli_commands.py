import asyncio
import getpass
import json
import os
import sys
from datetime import datetime

from .claude_refresh import _refresh_claude_sessions
from .cli_render import _dim, _info, _success, _warn
from .config import PROVIDER_CODEX
from .context_store import (
    clear_context,
    edit_context,
    get_context_path,
    init_context,
    install_context_for_session,
    read_context,
    write_context,
)
from .errors import CdxError
from .health import collect_health_report, format_health_report
from .notify import (
    format_notify_event,
    parse_notify_args,
    send_desktop_notification,
    wait_for_notification_event,
)
from .provider_runtime import (
    _ensure_session_authentication,
    _list_launch_transcript_paths,
    _run_interactive_provider_command,
)
from .repair import format_repair_report, repair_health
from .backup_bundle import read_bundle_meta
from .status_view import _format_status_detail, _format_status_rows
from .update_check import fetch_latest_release, is_newer_version
from .update_manager import build_update_plan, format_update_failure, run_update_plan


STATUS_USAGE = "Usage: cdx status [--json] [--refresh] | cdx status --small|-s [--refresh] | cdx status <name> [--json] [--refresh]"
DOCTOR_USAGE = "Usage: cdx doctor [--json]"
REPAIR_USAGE = "Usage: cdx repair [--dry-run] [--force] [--json]"
UPDATE_USAGE = "Usage: cdx update [--check] [--yes] [--json] [--version TAG]"
EXPORT_USAGE = "Usage: cdx export <file> [--include-auth] [--force] [--json] [--sessions name1,name2] [--passphrase-env VAR]"
IMPORT_USAGE = "Usage: cdx import <file> [--force] [--json] [--sessions name1,name2] [--passphrase-env VAR]"
CONTEXT_USAGE = "Usage: cdx context show|path|init|edit|clear|set [text...] [--json]"
HANDOFF_USAGE = "Usage: cdx handoff <name> [--json] | cdx handoff <source> <target> [--json]"
API_SCHEMA_VERSION = 1
HANDOFF_TRANSCRIPT_CHARS = 120000


def _local_now_iso():
    return datetime.now().astimezone().isoformat()


def _json_success(action, message, warnings=None, **extra):
    payload = {
        "schema_version": API_SCHEMA_VERSION,
        "ok": True,
        "action": action,
        "message": message,
        "warnings": warnings or [],
    }
    payload.update(extra)
    return payload


def _write_json(ctx, payload):
    ctx["out"](f"{json.dumps(payload, indent=2)}\n")


def _latest_launch_transcript_path(session):
    paths = _list_launch_transcript_paths(session)
    if not paths:
        return None
    return max(paths, key=lambda path: (os.path.getmtime(path), path))


def _read_handoff_transcript(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        content = handle.read()
    if len(content) <= HANDOFF_TRANSCRIPT_CHARS:
        return content, False
    return content[-HANDOFF_TRANSCRIPT_CHARS:], True


def _build_handoff_context(source, target, transcript_path, transcript, truncated=False):
    truncation_note = (
        "Only the tail of the previous transcript is included because the log was large."
        if truncated else
        "The previous transcript is included below."
    )
    return "\n".join([
        "# Shared Context",
        "",
        "## Goal",
        f"Resume the work from `{source['name']}` in `{target['name']}` because the source account has no usage left.",
        "",
        "## Current State",
        f"- Source session: `{source['name']}` ({source['provider']})",
        f"- Target session: `{target['name']}` ({target['provider']})",
        f"- Transcript source: `{transcript_path}`",
        f"- {truncation_note}",
        "",
        "## Previous Session Transcript",
        transcript.rstrip(),
        "",
        "## Next Steps",
        "- Read the transcript above.",
        "- Continue the task from the latest actionable state.",
        "- Preserve the target account authentication; do not copy source credentials.",
    ])


def _handoff_launch_prompt(session, install=None):
    if session.get("provider") == PROVIDER_CODEX:
        context_ref = "$CODEX_HOME/shared-context.md"
    else:
        context_ref = (install or {}).get("target_path") or os.path.join(
            session.get("authHome") or session.get("sessionRoot") or "~",
            "shared-context.md",
        )
    return (
        f"Read {context_ref} first, then resume the previous session "
        "from the latest actionable state. Do not ask me to paste the context again."
    )


def _parse_json_flag(args):
    json_flag = "--json" in args
    cleaned = [arg for arg in args if arg != "--json"]
    return json_flag, cleaned


def _parse_flag_args(args, schema, usage, positionals_key=None, max_positionals=0):
    parsed = {spec["key"]: spec.get("default") for spec in schema.values()}
    positionals = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in schema:
            spec = schema[arg]
            if spec["type"] == "bool":
                parsed[spec["key"]] = True
                index += 1
                continue
            value, index = _read_option_value(args, index, usage)
            parsed[spec["key"]] = spec.get("transform", lambda item: item)(value)
            continue
        if arg.startswith("--") and "=" in arg:
            flag, value = arg.split("=", 1)
            spec = schema.get(flag)
            if not spec or spec["type"] == "bool":
                raise CdxError(usage)
            parsed[spec["key"]] = spec.get("transform", lambda item: item)(value)
            index += 1
            continue
        if arg.startswith("-"):
            raise CdxError(usage)
        positionals.append(arg)
        if len(positionals) > max_positionals:
            raise CdxError(usage)
        index += 1

    if positionals_key is not None:
        parsed[positionals_key] = positionals
    return parsed


def _parse_add_args(args):
    parsed = _parse_flag_args(
        args,
        {},
        "Usage: cdx add [provider] <name> [--json]",
        positionals_key="values",
        max_positionals=2,
    )
    values = parsed["values"]
    if len(values) == 1:
        return {"provider": PROVIDER_CODEX, "name": values[0]}
    if len(values) == 2:
        return {"provider": values[0], "name": values[1]}
    raise CdxError("Usage: cdx add [provider] <name> [--json]")


def _parse_copy_args(args):
    if len(args) != 2:
        raise CdxError("Usage: cdx cp <source> <dest> [--json]")
    return {"source": args[0], "dest": args[1]}


def _parse_rename_args(args):
    if len(args) != 2:
        raise CdxError("Usage: cdx ren <source> <dest> [--json]")
    return {"source": args[0], "dest": args[1]}


def _parse_remove_args(args):
    force = "--force" in args
    names = [a for a in args if a != "--force"]
    unknown = [a for a in args if a.startswith("-") and a != "--force"]
    if unknown or len(names) != 1 or len(args) > 2:
        raise CdxError("Usage: cdx rmv <name> [--force] [--json]")
    return {"name": names[0], "force": force}


def _parse_toggle_args(args, usage):
    json_flag, cleaned = _parse_json_flag(args)
    if len(cleaned) != 1:
        raise CdxError(usage)
    return {"name": cleaned[0], "json": json_flag}


def _read_option_value(args, index, usage):
    if index + 1 >= len(args):
        raise CdxError(usage)
    return args[index + 1], index + 2


def _parse_session_names(value):
    if value is None:
        return None
    names = [item.strip() for item in value.split(",") if item.strip()]
    if not names:
        raise CdxError("At least one session name is required in --sessions.")
    return names


def _parse_update_args(args):
    parsed = {
        "check": False,
        "json": False,
        "yes": False,
        "version": None,
    }
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--check":
            parsed["check"] = True
            index += 1
            continue
        if arg == "--json":
            parsed["json"] = True
            index += 1
            continue
        if arg == "--yes":
            parsed["yes"] = True
            index += 1
            continue
        if arg == "--version":
            value, index = _read_option_value(args, index, UPDATE_USAGE)
            parsed["version"] = value
            continue
        if arg.startswith("--version="):
            parsed["version"] = arg.split("=", 1)[1]
            index += 1
            continue
        raise CdxError(UPDATE_USAGE)

    if parsed["check"] and parsed["version"]:
        raise CdxError("Usage: cdx update --check cannot be combined with --version.")
    if parsed["version"] is not None and not parsed["version"].strip():
        raise CdxError("Usage: cdx update [--check] [--yes] [--json] [--version TAG]")
    return parsed


def _parse_export_args(args):
    parsed = _parse_flag_args(args, {
        "--include-auth": {"key": "include_auth", "type": "bool", "default": False},
        "--force": {"key": "force", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
        "--sessions": {
            "key": "session_names",
            "type": "str",
            "default": None,
            "transform": _parse_session_names,
        },
        "--passphrase-env": {"key": "passphrase_env", "type": "str", "default": None},
    }, EXPORT_USAGE, positionals_key="positionals", max_positionals=1)
    parsed["file_path"] = parsed.pop("positionals")[0] if parsed["positionals"] else None
    if not parsed["file_path"]:
        raise CdxError(EXPORT_USAGE)
    if parsed["passphrase_env"] and not parsed["include_auth"]:
        raise CdxError("--passphrase-env requires --include-auth for export.")
    return parsed


def _parse_import_args(args):
    parsed = _parse_flag_args(args, {
        "--force": {"key": "force", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
        "--sessions": {
            "key": "session_names",
            "type": "str",
            "default": None,
            "transform": _parse_session_names,
        },
        "--passphrase-env": {"key": "passphrase_env", "type": "str", "default": None},
    }, IMPORT_USAGE, positionals_key="positionals", max_positionals=1)
    parsed["file_path"] = parsed.pop("positionals")[0] if parsed["positionals"] else None
    if not parsed["file_path"]:
        raise CdxError(IMPORT_USAGE)
    return parsed


def _resolve_bundle_passphrase(ctx, env_var, prompt, confirm=False):
    env = ctx.get("env", {})
    if env_var:
        passphrase = env.get(env_var)
        if not passphrase:
            raise CdxError(f"Environment variable {env_var} is empty or unset.")
        return passphrase
    if not ctx["stdin_is_tty"]:
        raise CdxError("Encrypted bundle export/import requires an interactive terminal or --passphrase-env.")
    getpass_fn = ctx["options"].get("getpass") or getpass.getpass
    passphrase = getpass_fn(prompt)
    if not passphrase:
        raise CdxError("Bundle passphrase cannot be empty.")
    if confirm:
        confirmation = getpass_fn("Confirm bundle passphrase: ")
        if passphrase != confirmation:
            raise CdxError("Bundle passphrase confirmation does not match.")
    return passphrase


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
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_add_args(args)
    session = ctx["service"]["create_session"](parsed["name"], parsed["provider"])
    message = f"Created session {parsed['name']} ({parsed['provider']})"
    _ensure_session_authentication(
        session,
        ctx["service"],
        spawn=ctx.get("spawn"),
        spawn_sync=ctx.get("spawn_sync"),
        env_override=ctx.get("env"),
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
    if json_flag:
        _write_json(ctx, _json_success(
            "add",
            message,
            session=ctx["service"]["get_session"](parsed["name"]),
        ))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_copy(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_copy_args(args)
    result = ctx["service"]["copy_session"](parsed["source"], parsed["dest"])
    overwritten = " (overwritten)" if result["overwritten"] else ""
    message = f"Copied session {parsed['source']} to {parsed['dest']}{overwritten}"
    if json_flag:
        _write_json(ctx, _json_success(
            "copy",
            message,
            session=result["session"],
            overwritten=result["overwritten"],
        ))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_rename(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_rename_args(args)
    session = ctx["service"]["rename_session"](parsed["source"], parsed["dest"])
    message = f"Renamed session {parsed['source']} to {parsed['dest']}"
    if json_flag:
        _write_json(ctx, _json_success("rename", message, session=session))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_remove(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_remove_args(args)
    if not parsed["force"]:
        confirm_fn = ctx["options"].get("confirmRemove")
        if confirm_fn:
            confirmed = _resolve_confirmation(confirm_fn, parsed["name"])
        elif not ctx["stdin_is_tty"]:
            raise CdxError("Removal requires confirmation in an interactive terminal or --force in non-interactive mode.")
        else:
            confirmed = _confirm_removal(parsed["name"])
        if not confirmed:
            if json_flag:
                _write_json(ctx, _json_success("remove", "Cancelled.", cancelled=True, session=None))
                return 0
            ctx["out"](f"{_warn('Cancelled.', ctx['use_color'])}\n")
            return 0
    removed = ctx["service"]["remove_session"](parsed["name"])
    message = f"Removed session {parsed['name']}"
    if json_flag:
        _write_json(ctx, _json_success("remove", message, session=removed, cancelled=False))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_disable(rest, ctx):
    parsed = _parse_toggle_args(rest, "Usage: cdx disable <name> [--json]")
    session = ctx["service"]["set_session_enabled"](parsed["name"], False)
    message = f"Disabled session {parsed['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("disable", message, session=session))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_enable(rest, ctx):
    parsed = _parse_toggle_args(rest, "Usage: cdx enable <name> [--json]")
    session = ctx["service"]["set_session_enabled"](parsed["name"], True)
    message = f"Enabled session {parsed['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("enable", message, session=session))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_clean(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    service = ctx["service"]
    if len(args) == 0:
        targets = service["list_sessions"]()
    elif len(args) == 1:
        session = service["get_session"](args[0])
        if not session:
            raise CdxError(f"Unknown session: {args[0]}")
        targets = [session]
    else:
        raise CdxError("Usage: cdx clean [name] [--json]")

    cleaned_sessions = []
    for session in targets:
        log_paths = _list_launch_transcript_paths(session)
        if not log_paths:
            message = f"{session['name']}: no log found"
            cleaned_sessions.append({
                "session_name": session["name"],
                "cleared": False,
                "files_cleared": 0,
                "freed_kb": 0,
                "message": message,
            })
            if json_flag:
                continue
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
            cleaned_sessions.append({
                "session_name": session["name"],
                "cleared": True,
                "files_cleared": cleared,
                "freed_kb": round(total_size / 1024),
                "message": message,
            })
            if json_flag:
                continue
            ctx["out"](f"{_success(message, ctx['use_color'])}\n")
        else:
            message = f"{session['name']}: no log found"
            cleaned_sessions.append({
                "session_name": session["name"],
                "cleared": False,
                "files_cleared": 0,
                "freed_kb": 0,
                "message": message,
            })
            if json_flag:
                continue
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
    if json_flag:
        _write_json(ctx, _json_success("clean", "Cleaned session logs", sessions=cleaned_sessions))
    return 0


def handle_doctor(rest, ctx):
    json_flag = "--json" in rest
    unknown = [arg for arg in rest if arg != "--json"]
    if unknown:
        raise CdxError(DOCTOR_USAGE)
    report = collect_health_report(
        ctx["service"],
        ctx["service"]["base_dir"],
        env=ctx.get("env"),
    )
    if json_flag:
        _write_json(ctx, _json_success("doctor", "Collected health report", report=report))
    else:
        ctx["out"](f"{format_health_report(report, use_color=ctx['use_color'])}\n")
    return 0


def handle_repair(rest, ctx):
    json_flag = "--json" in rest
    dry_run = "--dry-run" in rest or "--force" not in rest
    force = "--force" in rest
    allowed = {"--json", "--dry-run", "--force"}
    unknown = [arg for arg in rest if arg not in allowed]
    if unknown:
        raise CdxError(REPAIR_USAGE)
    report = repair_health(
        ctx["service"],
        ctx["service"]["base_dir"],
        env=ctx.get("env"),
        dry_run=dry_run,
        force=force,
    )
    if json_flag:
        _write_json(ctx, _json_success("repair", "Collected repair report", report=report))
    else:
        ctx["out"](f"{format_repair_report(report, use_color=ctx['use_color'])}\n")
        if dry_run:
            ctx["out"](f"{_dim('Tip: run cdx repair --force to apply safe repairs.', ctx['use_color'])}\n")
    return 0


def handle_notify(rest, ctx):
    parsed = parse_notify_args(rest)

    def notifier(title, message):
        send_desktop_notification(
            title,
            message,
            spawn_sync=ctx.get("spawn_sync"),
            env=ctx.get("env"),
        )

    event = wait_for_notification_event(
        ctx["service"],
        parsed,
        notifier=notifier,
        sleep_fn=ctx["options"].get("sleep"),
        now_fn=ctx["options"].get("now"),
    )
    if parsed["json"]:
        _write_json(ctx, _json_success("notify", "Resolved notification event", event=event))
    else:
        ctx["out"](f"{format_notify_event(event)}\n")
    return 0


def handle_context(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if not args:
        args = ["show"]
    action = args[0]
    base_dir = ctx["service"]["base_dir"]
    cwd = ctx.get("cwd")

    if action == "show":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        content = read_context(base_dir, cwd)
        payload = {
            "path": get_context_path(base_dir, cwd),
            "exists": bool(content.strip()),
            "content": content,
        }
        if json_flag:
            _write_json(ctx, _json_success("context.show", "Loaded shared context", context=payload))
            return 0
        if content.strip():
            ctx["out"](content if content.endswith("\n") else f"{content}\n")
        else:
            ctx["out"](f"{_dim('No shared context for this workspace. Run: cdx context init or cdx context set <text>', ctx['use_color'])}\n")
        return 0

    if action == "path":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        path = get_context_path(base_dir, cwd)
        if json_flag:
            _write_json(ctx, _json_success("context.path", "Resolved shared context path", path=path))
            return 0
        ctx["out"](f"{path}\n")
        return 0

    if action == "init":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        result = init_context(base_dir, cwd)
        message = "Created shared context" if result.get("created") else "Shared context already exists"
        if json_flag:
            _write_json(ctx, _json_success("context.init", message, context=result))
            return 0
        text = f"{message}: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    if action == "edit":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        result = edit_context(
            base_dir,
            cwd,
            env=ctx.get("env"),
            spawn_sync=ctx.get("spawn_sync"),
        )
        if json_flag:
            _write_json(ctx, _json_success("context.edit", "Edited shared context", context=result))
            return 0
        text = f"Edited shared context: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    if action == "clear":
        if len(args) != 1:
            raise CdxError(CONTEXT_USAGE)
        result = clear_context(base_dir, cwd)
        message = "Cleared shared context" if result["removed"] else "No shared context to clear"
        if json_flag:
            _write_json(ctx, _json_success("context.clear", message, context=result))
            return 0
        ctx["out"](f"{_success(message, ctx['use_color'])}\n")
        return 0

    if action == "set":
        content_args = args[1:]
        if content_args:
            content = " ".join(content_args)
        else:
            stdin = ctx["options"].get("stdin_data")
            if stdin is None and not ctx.get("stdin_is_tty"):
                stdin = sys.stdin.read()
            if stdin is None:
                raise CdxError("Usage: cdx context set <text> [--json]")
            content = stdin
        result = write_context(base_dir, content, cwd)
        if json_flag:
            _write_json(ctx, _json_success("context.set", "Saved shared context", context=result))
            return 0
        text = f"Saved shared context: {result['path']}"
        ctx["out"](f"{_success(text, ctx['use_color'])}\n")
        return 0

    raise CdxError(CONTEXT_USAGE)


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
    warnings = [
        {
            "code": "claude_refresh_failed",
            "session": item.get("session") or "unknown",
            "message": item.get("error") or "unknown error",
        }
        for item in refresh_errors
    ]

    rows = ctx["service"]["get_status_rows"]()
    if len(args) == 0:
        if json_flag:
            _write_json(ctx, _json_success("status", "Collected session status rows", warnings=warnings, rows=rows))
            return 0
        ctx["out"](f"{_format_status_rows(rows, use_color=ctx['use_color'], small=small_flag)}\n")
        _write_refresh_warnings(refresh_errors, ctx)
        return 0

    row = next((r for r in rows if r["session_name"] == args[0]), None)
    if not row:
        raise CdxError(f"Unknown session: {args[0]}")
    if json_flag:
        _write_json(ctx, _json_success("status", f"Collected status for {args[0]}", warnings=warnings, session=row))
        return 0
    ctx["out"](f"{_format_status_detail(row, use_color=ctx['use_color'])}\n")
    _write_refresh_warnings(refresh_errors, ctx)
    return 0


def _write_refresh_warnings(refresh_errors, ctx, stream="out"):
    write = ctx["err"] if stream == "err" and "err" in ctx else ctx["out"]
    for item in refresh_errors:
        session = item.get("session") or "unknown"
        error = item.get("error") or "unknown error"
        write(f"{_warn(f'Warning: Claude refresh failed for {session}: {error}', ctx['use_color'])}\n")


def handle_export(rest, ctx):
    parsed = _parse_export_args(rest)
    passphrase = None
    if parsed["include_auth"]:
        passphrase = _resolve_bundle_passphrase(
            ctx,
            parsed["passphrase_env"],
            "Bundle passphrase: ",
            confirm=True,
        )
    result = ctx["service"]["export_bundle"](
        parsed["file_path"],
        include_auth=parsed["include_auth"],
        session_names=parsed["session_names"],
        passphrase=passphrase,
        force=parsed["force"],
    )
    session_count = len(result["session_names"])
    auth_suffix = " with auth" if result["include_auth"] else ""
    message = f"Exported {session_count} session{'s' if session_count != 1 else ''}{auth_suffix} to {result['path']}"
    payload = _json_success(
        "export",
        message,
        bundle=result,
    )
    if parsed["json"]:
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_import(rest, ctx):
    parsed = _parse_import_args(rest)
    passphrase = None
    try:
        with open(parsed["file_path"], "rb") as handle:
            meta = read_bundle_meta(handle.read())
    except OSError as error:
        raise CdxError(f"Bundle file not found: {parsed['file_path']}") from error
    if meta.get("encrypted"):
        passphrase = _resolve_bundle_passphrase(
            ctx,
            parsed["passphrase_env"],
            "Bundle passphrase: ",
            confirm=False,
        )
    result = ctx["service"]["import_bundle"](
        parsed["file_path"],
        passphrase=passphrase,
        session_names=parsed["session_names"],
        force=parsed["force"],
    )
    session_count = len(result["session_names"])
    auth_suffix = " with auth" if result["include_auth"] else ""
    message = f"Imported {session_count} session{'s' if session_count != 1 else ''}{auth_suffix} from {result['path']}"
    payload = _json_success(
        "import",
        message,
        bundle=result,
    )
    if parsed["json"]:
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_login(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError("Usage: cdx login <name> [--json]")
    if not ctx["stdin_is_tty"]:
        raise CdxError("Login requires an interactive terminal.")
    session = ctx["service"]["get_session"](args[0])
    if not session:
        raise CdxError(f"Unknown session: {args[0]}")
    _run_interactive_provider_command(
        session, "logout", spawn=ctx.get("spawn"), env_override=ctx.get("env"),
        signal_emitter=ctx.get("signal_emitter")
    )
    _run_interactive_provider_command(
        session, "login", spawn=ctx.get("spawn"), env_override=ctx.get("env"),
        signal_emitter=ctx.get("signal_emitter")
    )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](args[0], lambda auth: {
        **auth, "status": "authenticated",
        "lastCheckedAt": now, "lastAuthenticatedAt": now,
    })
    message = f"Reauthenticated session {session['name']} ({session['provider']})"
    if json_flag:
        _write_json(ctx, _json_success("login", message, session=ctx["service"]["get_session"](session["name"])))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_logout(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError("Usage: cdx logout <name> [--json]")
    session = ctx["service"]["get_session"](args[0])
    if not session:
        raise CdxError(f"Unknown session: {args[0]}")
    _run_interactive_provider_command(
        session, "logout", spawn=ctx.get("spawn"), env_override=ctx.get("env"),
        signal_emitter=ctx.get("signal_emitter")
    )
    now = _local_now_iso()
    ctx["service"]["update_auth_state"](args[0], lambda auth: {
        **auth, "status": "logged_out",
        "lastCheckedAt": now, "lastLoggedOutAt": now,
    })
    message = f"Logged out session {session['name']} ({session['provider']})"
    if json_flag:
        _write_json(ctx, _json_success("logout", message, session=ctx["service"]["get_session"](session["name"])))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_update(rest, ctx):
    parsed = _parse_update_args(rest)
    json_flag = parsed["json"]
    current_version = str(ctx.get("version") or "").strip()
    release_fetcher = ctx["options"].get("fetchLatestRelease") or fetch_latest_release
    target_version = None
    release_url = None
    update_available = False

    if parsed["version"] is not None:
        target_version = str(parsed["version"]).strip().lstrip("v")
    else:
        latest = release_fetcher()
        if not latest:
            raise CdxError("Unable to check for the latest cdx-manager release. Check your network and try again.")
        target_version = str(latest.get("latest_version") or "").strip()
        release_url = latest.get("url")
        if not target_version:
            raise CdxError("Unable to determine the latest cdx-manager release.")
        update_available = is_newer_version(current_version, target_version)
        if parsed["check"] or not update_available:
            message = (
                f"Update available: cdx-manager {target_version} (current {current_version})"
                if update_available
                else f"cdx-manager {current_version} is already up to date."
            )
            if json_flag:
                _write_json(ctx, _json_success(
                    "update",
                    message,
                    checked=True,
                    update_available=update_available,
                    current_version=current_version,
                    target_version=target_version,
                    release_url=release_url,
                    warnings=[{
                        "code": "update_available",
                        "message": message,
                        "latest_version": target_version,
                        "url": release_url,
                    }] if update_available else [],
                ))
                return 0
            ctx["out"](f"{_warn(message, ctx['use_color']) if update_available else _success(message, ctx['use_color'])}\n")
            return 0

    if not parsed["yes"]:
        if not ctx["stdin_is_tty"]:
            raise CdxError("Update requires an interactive terminal or --yes in non-interactive mode.")
        answer = input(f"Update cdx-manager to {target_version}? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            message = "Cancelled."
            if json_flag:
                _write_json(ctx, _json_success("update", message, cancelled=True, current_version=current_version, target_version=target_version))
                return 0
            ctx["out"](f"{_warn(message, ctx['use_color'])}\n")
            return 0

    plan = build_update_plan(
        target_version=target_version,
        package_root=ctx["options"].get("packageRoot"),
        prefix=ctx["options"].get("prefix"),
        base_prefix=ctx["options"].get("basePrefix"),
    )
    results = run_update_plan(plan, runner=ctx["options"].get("runUpdate"), env=ctx.get("env"))
    failed = any((result.get("returncode") not in (0, None)) for result in results)
    if failed:
        raise CdxError(format_update_failure(results))

    message = f"Updated cdx-manager to {target_version}"
    if json_flag:
        _write_json(ctx, _json_success(
            "update",
            message,
            updated=True,
            current_version=current_version,
            target_version=target_version,
            mode=plan["mode"],
            steps=results,
        ))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    return 0


def handle_launch(command, ctx, initial_prompt=None):
    json_flag = "--json" in ctx["options"].get("raw_args", [])
    update_notice = ctx.get("update_notice")
    warnings = []
    if update_notice:
        warnings.append({
            "code": "update_available",
            "message": f"Update available: cdx-manager {update_notice['latest_version']}",
            "latest_version": update_notice["latest_version"],
            "url": update_notice.get("url"),
        })
    session = ctx["service"]["launch_session"](command)
    _ensure_session_authentication(
        session,
        ctx["service"],
        spawn=ctx.get("spawn"),
        spawn_sync=ctx.get("spawn_sync"),
        env_override=ctx.get("env"),
        stdin_is_tty=ctx["stdin_is_tty"],
        behavior="launch",
        signal_emitter=ctx.get("signal_emitter"),
    )
    message = f"Launching {session['provider']} session {session['name']}"
    if not json_flag:
        ctx["out"](f"{_info(message, ctx['use_color'])}\n")
        if update_notice:
            text = f"Update available: cdx-manager {update_notice['latest_version']} (current version installed may be older)."
            if update_notice.get("url"):
                text = f"{text} {update_notice['url']}"
            ctx["out"](f"{_warn(text, ctx['use_color'])}\n")
    if session["provider"] == PROVIDER_CODEX:
        if not json_flag:
            ctx["out"](f"{_dim('Tip: cdx status reads Codex rate limits from the local app-server when available.', ctx['use_color'])}\n")
    _run_interactive_provider_command(
        session, "launch", spawn=ctx.get("spawn"), env_override=ctx.get("env"),
        signal_emitter=ctx.get("signal_emitter"), initial_prompt=initial_prompt,
    )
    if json_flag:
        _write_json(ctx, _json_success("launch", message, warnings=warnings, session=ctx["service"]["get_session"](session["name"])))
    return 0


def handle_handoff(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if len(args) not in (1, 2):
        raise CdxError(HANDOFF_USAGE)
    if len(args) == 1:
        name = args[0]
        session = ctx["service"]["get_session"](name)
        if not session:
            raise CdxError(f"Unknown session: {name}")
        install = install_context_for_session(ctx["service"]["base_dir"], session, ctx.get("cwd"))
        launch_prompt = _handoff_launch_prompt(session, install)
        if json_flag:
            _write_json(ctx, _json_success(
                "handoff",
                f"Installed shared context for {name}",
                context=install,
                launch_prompt=launch_prompt,
                session=session,
            ))
            return 0
        text = f"Shared context installed for {name}: {install['target_path']}"
        ctx["out"](f"{_info(text, ctx['use_color'])}\n")
        return handle_launch(name, ctx, initial_prompt=launch_prompt)

    source_name, target_name = args
    if source_name == target_name:
        raise CdxError("Source and target sessions must be different")
    source = ctx["service"]["get_session"](source_name)
    if not source:
        raise CdxError(f"Unknown session: {source_name}")
    target = ctx["service"]["get_session"](target_name)
    if not target:
        raise CdxError(f"Unknown session: {target_name}")
    transcript_path = _latest_launch_transcript_path(source)
    if not transcript_path:
        raise CdxError(f"No launch transcript found for session: {source_name}")
    transcript, truncated = _read_handoff_transcript(transcript_path)
    context = _build_handoff_context(source, target, transcript_path, transcript, truncated=truncated)
    write_result = write_context(ctx["service"]["base_dir"], context, ctx.get("cwd"))
    install = install_context_for_session(ctx["service"]["base_dir"], target, ctx.get("cwd"))
    launch_prompt = _handoff_launch_prompt(target, install)
    if json_flag:
        _write_json(ctx, _json_success(
            "handoff",
            f"Prepared handoff from {source_name} to {target_name}",
            context=install,
            source_session=source,
            target_session=target,
            source_transcript=transcript_path,
            shared_context=write_result,
            launch_prompt=launch_prompt,
        ))
        return 0
    text = f"Handoff prepared from {source_name} to {target_name}: {install['target_path']}"
    ctx["out"](f"{_info(text, ctx['use_color'])}\n")
    return handle_launch(target_name, ctx, initial_prompt=launch_prompt)
