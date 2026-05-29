import asyncio
import getpass
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

from .claude_refresh import _refresh_claude_sessions
from .cli_render import _dim, _info, _success, _warn
from .config import PROVIDER_ANTIGRAVITY, PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_OLLAMA, PROVIDERS
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
    format_scheduled_notification,
    parse_notify_args,
    resolve_notify_event,
    schedule_notification_event,
    send_desktop_notification,
    wait_for_notification_event,
)
from .provider_runtime import (
    _ensure_session_authentication,
    _list_launch_transcript_paths,
    _normalize_reasoning_effort,
    _probe_provider_auth,
    _run_headless_provider_command,
    _run_interactive_provider_command,
)
from .repair import format_repair_report, repair_health
from .backup_bundle import read_bundle_meta
from .status_view import _format_status_detail, _format_status_rows
from .update_check import LatestReleaseCheckError, fetch_latest_release, fetch_latest_release_or_raise, is_newer_version
from .update_manager import build_update_plan, format_update_failure, run_update_plan


STATUS_USAGE = "Usage: cdx status [--json] [--refresh] | cdx status --small|-s [--refresh] | cdx status <name> [--json] [--refresh]"
DOCTOR_USAGE = "Usage: cdx doctor [--json]"
REPAIR_USAGE = "Usage: cdx repair [--dry-run] [--force] [--json]"
UPDATE_USAGE = "Usage: cdx update [--check] [--yes] [--json] [--version TAG]"
EXPORT_USAGE = "Usage: cdx export <file> [--include-auth] [--force] [--json] [--sessions name1,name2] [--passphrase-env VAR]"
IMPORT_USAGE = "Usage: cdx import <file> [--force] [--json] [--sessions name1,name2] [--passphrase-env VAR]"
CONTEXT_USAGE = "Usage: cdx context show|path|init|edit|clear|set [text...] [--json]"
HANDOFF_USAGE = "Usage: cdx handoff <name> [--json] | cdx handoff <source> <target> [--json]"
SET_USAGE = "Usage: cdx set <name>|--sessions all|a,b|--provider PROVIDER [--power low|medium|high|xhigh|max] [--permission review|default|auto|full] [--fast on|off] [--model MODEL] [--priority 0..100] [--json]"
UNSET_USAGE = "Usage: cdx unset <name>|--sessions all|a,b|--provider PROVIDER (--power|--permission|--fast|--model|--priority|--all) [--json]"
SETTING_ALIAS_USAGE = "Usage: cdx power|perm|fast|model <name|all|provider:PROVIDER|a,b> <value|default> [--json]"
CONFIG_USAGE = "Usage: cdx config <name> [--json]"
HISTORY_USAGE = "Usage: cdx history [name] [--limit N] [--summary] [--since 7d|today|DATE] [--from DATE] [--to DATE] [--json]"
LAST_USAGE = "Usage: cdx last [--json]"
SELECT_USAGE = "Usage: cdx select --provider PROVIDER [--min-reasoning-effort low|medium|high] [--min-power low|medium|high] [--require-ready] [--refresh] --json"
RUN_USAGE = "Usage: cdx run [session] --cwd PATH (--prompt-file PATH|--prompt TEXT) [--provider PROVIDER] [--model MODEL] [--reasoning-effort low|medium|high] [--power low|medium|high] [--permission review|default|auto|full|workspace-write|read-only|danger-full-access] [--timeout-seconds N] --json"
API_SCHEMA_VERSION = 1
HANDOFF_TRANSCRIPT_CHARS = 120000
HANDOFF_NATIVE_TRANSCRIPT_CANDIDATES = 64


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


def _json_failure(action, code, message, source="cdx", exit_code=1, warnings=None, **extra):
    payload = {
        "schema_version": API_SCHEMA_VERSION,
        "ok": False,
        "action": action,
        "warnings": warnings or [],
        "error": {
            "source": source,
            "code": code,
            "message": message,
            "exit_code": exit_code,
        },
    }
    payload.update(extra)
    return payload


def _write_json(ctx, payload):
    ctx["out"](f"{json.dumps(payload, indent=2)}\n")


def _update_notice_warning(ctx):
    notice = ctx.get("update_notice")
    if not notice:
        return None
    return {
        "code": "update_available",
        "message": f"Update available: cdx-manager {notice['latest_version']}",
        "latest_version": notice["latest_version"],
        "url": notice.get("url"),
    }


def _write_update_notice(ctx):
    notice = ctx.get("update_notice")
    if not notice:
        return
    text = f"Update available: cdx-manager {notice['latest_version']} (current version installed may be older). Run: cdx update"
    ctx["out"](f"{_warn(text, ctx['use_color'])}\n")


def _format_bytes(value):
    if value is None:
        return "n/a"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return str(value)
    units = ["B", "KB", "MB", "GB", "TB"]
    unit = units[0]
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            break
        amount /= 1024
    if unit == "B":
        return f"{int(amount)} B"
    return f"{amount:.1f} {unit}"


def _format_export_report(result):
    lines = [
        f"Path: {result['path']}",
        f"Sessions: {', '.join(result['session_names']) or '-'}",
        f"Auth: {'included and encrypted' if result['include_auth'] else 'not included'}",
        f"Bundle size: {_format_bytes(result.get('bundle_size_bytes'))}",
    ]
    if result.get("include_auth"):
        lines.extend([
            f"Auth files: {result.get('profile_file_count', 0)}",
            f"Auth data: {_format_bytes(result.get('profile_bytes'))}",
        ])
    return "\n".join(lines)


def _make_export_progress(ctx):
    def progress(event):
        kind = event.get("event")
        if kind == "export_started":
            auth = " with auth" if event.get("include_auth") else ""
            message = f"Exporting {event.get('session_count', 0)} session(s){auth}..."
            ctx["out"](f"{_info(message, ctx['use_color'])}\n")
        elif kind == "session_started":
            message = f"Collecting {event.get('session_name')}..."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
        elif kind == "profile_progress":
            message = f"  {event.get('session_name')}: {event.get('file_count', 0)} files, {_format_bytes(event.get('bytes'))}"
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
        elif kind == "encoding_started":
            ctx["out"](f"{_dim('Encoding and encrypting bundle...', ctx['use_color'])}\n")
        elif kind == "writing_started":
            message = f"Writing {_format_bytes(event.get('bundle_size_bytes'))}..."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
    return progress


def _make_status_progress(ctx):
    def progress(event):
        kind = event.get("event")
        if kind == "status_started":
            message = f"Resolving status for {event.get('session_count', 0)} session(s)..."
            ctx["out"](f"{_info(message, ctx['use_color'])}\n")
        elif kind == "session_started":
            provider = event.get("provider") or "session"
            message = f"Checking {event.get('session_name')} ({provider})..."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
        elif kind == "status_finished":
            message = f"Resolved {event.get('row_count', 0)} status row(s)."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
    return progress


def _make_notify_progress(ctx):
    def progress(event):
        kind = event.get("event")
        if kind == "notify_check_started":
            target = event.get("session_name") or "next ready session"
            ctx["out"](f"{_info(f'Checking notification target: {target}...', ctx['use_color'])}\n")
        elif kind == "status_started":
            message = f"Loading status for {event.get('session_count', 0)} session(s)..."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
        elif kind == "session_started":
            provider = event.get("provider") or "session"
            message = f"Checking {event.get('session_name')} ({provider})..."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
        elif kind == "notify_waiting":
            message = f"{event.get('message')}; checking again in {event.get('poll')}s..."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
    return progress


def _latest_launch_transcript_path(session):
    paths = _list_launch_transcript_paths(session)
    if not paths:
        return None
    return max(paths, key=lambda path: (os.path.getmtime(path), path))


def _get_session_home(session):
    return session.get("authHome") or session.get("sessionRoot") or session.get("codexHome", "")


def _safe_stat(path):
    try:
        return os.stat(path)
    except OSError:
        return None


def _sort_recent_paths(paths):
    stats = {path: stat for path, stat in ((_path, _safe_stat(_path)) for _path in set(paths)) if stat}
    return sorted(stats, key=lambda path: (stats[path].st_mtime, path), reverse=True)


def _collect_native_handoff_transcript_paths(session):
    root = _get_session_home(session)
    if not root:
        return []
    candidates = []
    direct = [
        os.path.join(root, "history.jsonl"),
        os.path.join(root, "session_index.jsonl"),
    ]
    candidates.extend(path for path in direct if _safe_stat(path))

    scan_roots = [
        os.path.join(root, "sessions"),
        os.path.join(root, ".claude", "projects"),
        os.path.join(root, "projects"),
    ]
    skip_dirs = {"cache", "plugins", "skills", "memories", "sqlite", "shell_snapshots", "tmp", "__pycache__"}
    for scan_root in scan_roots:
        if not os.path.isdir(scan_root):
            continue
        for dirpath, dirnames, filenames in os.walk(scan_root):
            dirnames[:] = [name for name in dirnames if not name.startswith(".") and name not in skip_dirs]
            for filename in filenames:
                if filename.endswith(".jsonl") or filename.endswith(".log"):
                    candidates.append(os.path.join(dirpath, filename))
    return _sort_recent_paths(candidates)[:HANDOFF_NATIVE_TRANSCRIPT_CANDIDATES]


def _latest_handoff_transcript_path(session):
    launch_path = _latest_launch_transcript_path(session)
    if launch_path:
        return launch_path
    native_paths = _collect_native_handoff_transcript_paths(session)
    return native_paths[0] if native_paths else None


def _collect_handoff_text_fragments(value):
    fragments = []
    if isinstance(value, str):
        text = value.strip()
        if text:
            fragments.append(text)
    elif isinstance(value, list):
        for item in value:
            fragments.extend(_collect_handoff_text_fragments(item))
    elif isinstance(value, dict):
        if isinstance(value.get("text"), str):
            fragments.extend(_collect_handoff_text_fragments(value.get("text")))
        if isinstance(value.get("content"), (str, list, dict)):
            fragments.extend(_collect_handoff_text_fragments(value.get("content")))
        if isinstance(value.get("message"), dict):
            fragments.extend(_collect_handoff_text_fragments(value.get("message")))
        if isinstance(value.get("payload"), dict):
            fragments.extend(_collect_handoff_text_fragments(value.get("payload")))
    return fragments


def _jsonl_record_to_handoff_text(record):
    if not isinstance(record, dict):
        return None
    message = record.get("message") if isinstance(record.get("message"), dict) else {}
    role = (
        message.get("role")
        or record.get("role")
        or record.get("type")
        or record.get("sender")
        or "entry"
    )
    text_sources = []
    for key in ("content", "text", "payload"):
        if key in record:
            text_sources.append(record.get(key))
    for key in ("content", "text"):
        if key in message:
            text_sources.append(message.get(key))
    fragments = []
    for value in text_sources:
        fragments.extend(_collect_handoff_text_fragments(value))
    text = "\n".join(fragment for fragment in fragments if fragment).strip()
    if not text:
        return None
    role = re.sub(r"[^A-Za-z0-9_-]+", "-", str(role).strip()).strip("-") or "entry"
    return f"[{role}]\n{text}"


def _read_jsonl_handoff_transcript(path):
    entries = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                text = _jsonl_record_to_handoff_text(json.loads(line))
            except json.JSONDecodeError:
                text = None
            if text:
                entries.append(text)
    if entries:
        return "\n\n".join(entries)
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _read_handoff_transcript(path):
    if path.endswith(".jsonl"):
        content = _read_jsonl_handoff_transcript(path)
    else:
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
        {"--model": {"key": "model", "type": "str", "default": None}},
        "Usage: cdx add [provider] <name> [--model MODEL] [--json]",
        positionals_key="values",
        max_positionals=2,
    )
    values = parsed["values"]
    if len(values) == 1:
        return {"provider": PROVIDER_CODEX, "name": values[0], "model": parsed["model"]}
    if len(values) == 2:
        return {"provider": values[0], "name": values[1], "model": parsed["model"]}
    raise CdxError("Usage: cdx add [provider] <name> [--model MODEL] [--json]")


def _parse_copy_args(args):
    if len(args) != 2:
        raise CdxError("Usage: cdx cp <source> <dest> [--json]")
    return {"source": args[0], "dest": args[1]}


def _parse_rename_args(args):
    if len(args) != 2:
        raise CdxError("Usage: cdx ren <source> <dest> [--json]")
    return {"source": args[0], "dest": args[1]}


def _parse_remove_args(args):
    parsed = _parse_flag_args(args, {
        "--force": {"key": "force", "type": "bool", "default": False},
    }, "Usage: cdx rmv <name> [--force] [--json]", positionals_key="names", max_positionals=1)
    if len(parsed["names"]) != 1:
        raise CdxError("Usage: cdx rmv <name> [--force] [--json]")
    return {"name": parsed["names"][0], "force": parsed["force"]}


def _parse_toggle_args(args, usage):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, usage, positionals_key="names", max_positionals=1)
    if len(parsed["names"]) != 1:
        raise CdxError(usage)
    return {"name": parsed["names"][0], "json": parsed["json"]}


def _parse_fast_value(value):
    text = str(value).strip().lower()
    if text in ("on", "true", "1", "yes"):
        return True
    if text in ("off", "false", "0", "no"):
        return False
    raise CdxError(SET_USAGE)


def _parse_priority_value(value):
    try:
        priority = int(value)
    except (TypeError, ValueError) as error:
        raise CdxError(SET_USAGE) from error
    if priority < 0 or priority > 100:
        raise CdxError(SET_USAGE)
    return priority


def _parse_set_args(args):
    parsed = _parse_flag_args(args, {
        "--power": {"key": "power", "type": "str", "default": None},
        "--permission": {"key": "permission", "type": "str", "default": None},
        "--fast": {"key": "fast", "type": "str", "default": None, "transform": _parse_fast_value},
        "--model": {"key": "model", "type": "str", "default": None},
        "--priority": {"key": "priority", "type": "str", "default": None, "transform": _parse_priority_value},
        "--sessions": {"key": "sessions", "type": "str", "default": None, "transform": _parse_set_unset_sessions},
        "--provider": {"key": "provider", "type": "str", "default": None, "transform": lambda value: _parse_provider_filter(value, SET_USAGE)},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, SET_USAGE, positionals_key="names", max_positionals=1)
    if len(parsed["names"]) > 1:
        raise CdxError(SET_USAGE)
    if parsed["names"] and parsed["sessions"]:
        raise CdxError(SET_USAGE)
    if parsed["names"] and parsed["provider"]:
        raise CdxError(SET_USAGE)
    if not parsed["names"] and not parsed["sessions"] and not parsed["provider"]:
        raise CdxError(SET_USAGE)
    settings = {
        key: parsed[key]
        for key in ("power", "permission", "fast", "model", "priority")
        if parsed[key] is not None
    }
    if not settings:
        raise CdxError(SET_USAGE)
    return {
        "name": parsed["names"][0] if parsed["names"] else None,
        "sessions": parsed["sessions"],
        "provider": parsed["provider"],
        "settings": settings,
        "json": parsed["json"],
    }


def _parse_unset_args(args):
    parsed = _parse_flag_args(args, {
        "--power": {"key": "power", "type": "bool", "default": False},
        "--permission": {"key": "permission", "type": "bool", "default": False},
        "--fast": {"key": "fast", "type": "bool", "default": False},
        "--model": {"key": "model", "type": "bool", "default": False},
        "--priority": {"key": "priority", "type": "bool", "default": False},
        "--all": {"key": "all", "type": "bool", "default": False},
        "--sessions": {"key": "sessions", "type": "str", "default": None, "transform": _parse_set_unset_sessions},
        "--provider": {"key": "provider", "type": "str", "default": None, "transform": lambda value: _parse_provider_filter(value, UNSET_USAGE)},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, UNSET_USAGE, positionals_key="names", max_positionals=1)
    if len(parsed["names"]) > 1:
        raise CdxError(UNSET_USAGE)
    if parsed["names"] and parsed["sessions"]:
        raise CdxError(UNSET_USAGE)
    if parsed["names"] and parsed["provider"]:
        raise CdxError(UNSET_USAGE)
    if not parsed["names"] and not parsed["sessions"] and not parsed["provider"]:
        raise CdxError(UNSET_USAGE)
    keys = ["power", "permission", "fast", "model", "priority"] if parsed["all"] else [
        key for key in ("power", "permission", "fast", "model", "priority") if parsed[key]
    ]
    if not keys:
        raise CdxError(UNSET_USAGE)
    return {
        "name": parsed["names"][0] if parsed["names"] else None,
        "sessions": parsed["sessions"],
        "provider": parsed["provider"],
        "keys": keys,
        "json": parsed["json"],
    }


def _parse_config_args(args):
    parsed = _parse_flag_args(args, {
        "--json": {"key": "json", "type": "bool", "default": False},
    }, CONFIG_USAGE, positionals_key="names", max_positionals=1)
    if len(parsed["names"]) != 1:
        raise CdxError(CONFIG_USAGE)
    return {"name": parsed["names"][0], "json": parsed["json"]}


def _parse_select_args(args):
    parsed = _parse_flag_args(args, {
        "--provider": {"key": "provider", "type": "str", "default": None, "transform": lambda value: _parse_provider_filter(value, SELECT_USAGE)},
        "--min-reasoning-effort": {"key": "min_reasoning_effort", "type": "str", "default": None},
        "--min-power": {"key": "min_power", "type": "str", "default": None},
        "--require-ready": {"key": "require_ready", "type": "bool", "default": False},
        "--refresh": {"key": "refresh", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, SELECT_USAGE)
    if not parsed["provider"] or not parsed["json"]:
        raise CdxError(SELECT_USAGE)
    effort = _normalize_reasoning_effort(
        reasoning_effort=parsed["min_reasoning_effort"],
        power=parsed["min_power"],
        usage=SELECT_USAGE,
    ).get("reasoning_effort")
    return {
        "provider": parsed["provider"],
        "min_reasoning_effort": effort,
        "require_ready": parsed["require_ready"],
        "refresh": parsed["refresh"],
        "json": parsed["json"],
    }


def _parse_timeout_seconds(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise CdxError(RUN_USAGE) from error
    if parsed <= 0:
        raise CdxError(RUN_USAGE)
    return parsed


def _normalize_run_permission(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    aliases = {
        "workspace-write": "default",
        "read-only": "review",
        "danger-full-access": "full",
    }
    text = aliases.get(text, text)
    if text not in ("review", "default", "auto", "full"):
        raise CdxError(RUN_USAGE)
    return text


def _parse_run_args(args):
    parsed = _parse_flag_args(args, {
        "--cwd": {"key": "cwd", "type": "str", "default": None},
        "--prompt-file": {"key": "prompt_file", "type": "str", "default": None},
        "--prompt": {"key": "prompt", "type": "str", "default": None},
        "--provider": {"key": "provider", "type": "str", "default": None, "transform": lambda value: _parse_provider_filter(value, RUN_USAGE)},
        "--model": {"key": "model", "type": "str", "default": None},
        "--reasoning-effort": {"key": "reasoning_effort", "type": "str", "default": None},
        "--power": {"key": "power", "type": "str", "default": None},
        "--permission": {"key": "permission", "type": "str", "default": None, "transform": _normalize_run_permission},
        "--timeout-seconds": {"key": "timeout_seconds", "type": "str", "default": None, "transform": _parse_timeout_seconds},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, RUN_USAGE, positionals_key="names", max_positionals=1)
    if not parsed["json"]:
        raise CdxError(RUN_USAGE)
    name = parsed["names"][0] if parsed["names"] else None
    if name and parsed["provider"]:
        raise CdxError(RUN_USAGE)
    if not name and not parsed["provider"]:
        raise CdxError(RUN_USAGE)
    if not parsed["cwd"]:
        raise CdxError(RUN_USAGE)
    if bool(parsed["prompt_file"]) == bool(parsed["prompt"]):
        raise CdxError(RUN_USAGE)
    effort = _normalize_reasoning_effort(
        reasoning_effort=parsed["reasoning_effort"],
        power=parsed["power"],
        usage=RUN_USAGE,
    )
    return {
        "name": name,
        "provider": parsed["provider"],
        "cwd": parsed["cwd"],
        "prompt_file": parsed["prompt_file"],
        "prompt": parsed["prompt"],
        "model": parsed["model"],
        "permission": parsed["permission"],
        "timeout_seconds": parsed["timeout_seconds"],
        "reasoning_effort": effort.get("reasoning_effort"),
        "power": effort.get("power"),
    }


def _parse_positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise CdxError(HISTORY_USAGE) from error
    if parsed < 1:
        raise CdxError(HISTORY_USAGE)
    return parsed


def _local_timezone():
    return datetime.now().astimezone().tzinfo


def _parse_datetime_value(value, usage, end_of_day=False):
    text = str(value or "").strip()
    if not text:
        raise CdxError(usage)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    is_date_only = len(text) == 10 and text[4] == "-" and text[7] == "-"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise CdxError(usage) from error
    if is_date_only and end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_local_timezone())
    return parsed.astimezone()


def _parse_since_value(value, now, usage):
    text = str(value or "").strip().lower()
    if not text:
        raise CdxError(usage)
    if text == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if text == "yesterday":
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return today - timedelta(days=1)
    unit = text[-1:]
    amount_text = text[:-1]
    if unit in ("m", "h", "d", "w") and amount_text.isdigit():
        amount = int(amount_text)
        if amount < 1:
            raise CdxError(usage)
        multipliers = {
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
            "w": timedelta(weeks=amount),
        }
        return now - multipliers[unit]
    return _parse_datetime_value(value, usage, end_of_day=False)


def _format_period_datetime(value):
    if value is None:
        return None
    return value.isoformat(timespec="seconds")


def _parse_history_period(parsed, now):
    since = parsed.get("since")
    from_value = parsed.get("from")
    to_value = parsed.get("to")
    if since and from_value:
        raise CdxError("Usage: cdx history cannot combine --since and --from.")
    start = _parse_since_value(since, now, HISTORY_USAGE) if since else None
    if from_value:
        start = _parse_datetime_value(from_value, HISTORY_USAGE, end_of_day=False)
    end = _parse_datetime_value(to_value, HISTORY_USAGE, end_of_day=True) if to_value else None
    if start and end and start.timestamp() > end.timestamp():
        raise CdxError("Usage: cdx history period start must be before period end.")
    return {
        "from": _format_period_datetime(start),
        "to": _format_period_datetime(end),
        "from_ts": start.timestamp() if start else None,
        "to_ts": end.timestamp() if end else None,
    }


def _has_history_period(period):
    return period.get("from_ts") is not None or period.get("to_ts") is not None


def _parse_entry_timestamp(entry):
    value = entry.get("started_at")
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_local_timezone())
    return parsed.timestamp()


def _filter_history_period(entries, period):
    if not _has_history_period(period):
        return entries
    filtered = []
    start = period.get("from_ts")
    end = period.get("to_ts")
    for entry in entries:
        timestamp = _parse_entry_timestamp(entry)
        if timestamp is None:
            continue
        if start is not None and timestamp < start:
            continue
        if end is not None and timestamp > end:
            continue
        filtered.append(entry)
    return filtered


def _public_history_period(period):
    return {
        "from": period.get("from"),
        "to": period.get("to"),
    }


def _parse_history_args(args, now=None):
    now = now or datetime.now().astimezone()
    parsed = _parse_flag_args(args, {
        "--limit": {"key": "limit", "type": "str", "default": 20, "transform": _parse_positive_int},
        "--summary": {"key": "summary", "type": "bool", "default": False},
        "--since": {"key": "since", "type": "str", "default": None},
        "--from": {"key": "from", "type": "str", "default": None},
        "--to": {"key": "to", "type": "str", "default": None},
        "--json": {"key": "json", "type": "bool", "default": False},
    }, HISTORY_USAGE, positionals_key="names", max_positionals=1)
    period = _parse_history_period(parsed, now)
    return {
        "name": parsed["names"][0] if parsed["names"] else None,
        "limit": parsed["limit"],
        "summary": parsed["summary"],
        "period": period,
        "json": parsed["json"],
    }


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


def _parse_set_unset_sessions(value):
    text = str(value or "").strip()
    if not text:
        raise CdxError("At least one session name is required in --sessions.")
    if text.lower() == "all":
        return "all"
    return _parse_session_names(text)


def _parse_provider_filter(value, usage):
    provider = str(value or "").strip()
    if provider not in PROVIDERS:
        raise CdxError(usage)
    return provider


def _parse_launch_setting_target(value, usage):
    text = str(value or "").strip()
    if not text:
        raise CdxError(usage)
    if text == "all":
        return {"name": None, "sessions": "all", "provider": None}
    if text.startswith("provider:"):
        return {"name": None, "sessions": None, "provider": _parse_provider_filter(text.split(":", 1)[1], usage)}
    if "," in text:
        return {"name": None, "sessions": _parse_session_names(text), "provider": None}
    return {"name": text, "sessions": None, "provider": None}


def _parse_launch_setting_alias_args(kind, args):
    json_flag, cleaned = _parse_json_flag(args)
    if len(cleaned) != 2:
        raise CdxError(SETTING_ALIAS_USAGE)
    target = _parse_launch_setting_target(cleaned[0], SETTING_ALIAS_USAGE)
    value = cleaned[1]
    field = "permission" if kind == "perm" else kind
    if value == "default":
        return {**target, "keys": [field], "json": json_flag, "alias": kind}
    if field == "fast":
        value = _parse_fast_value(value)
    return {**target, "settings": {field: value}, "json": json_flag, "alias": kind}


def _parse_update_args(args):
    parsed = _parse_flag_args(args, {
        "--check": {"key": "check", "type": "bool", "default": False},
        "--json": {"key": "json", "type": "bool", "default": False},
        "--yes": {"key": "yes", "type": "bool", "default": False},
        "--version": {"key": "version", "type": "str", "default": None},
    }, UPDATE_USAGE)
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


def _extract_claude_oauth_token(text):
    if not text:
        return None
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", str(text))
    patterns = [
        r"CLAUDE_CODE_OAUTH_TOKEN=([^\s\"']+)",
        r"(sk-ant-oat[0-9A-Za-z._-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            token = match.group(1).strip()
            if token.startswith("<") or any(ord(ch) < 32 or ord(ch) == 127 for ch in token):
                continue
            return token
    return None


def _write_claude_oauth_token(auth_home, token):
    cred_dir = os.path.join(auth_home, "credentials")
    os.makedirs(cred_dir, exist_ok=True)
    cred_path = os.path.join(cred_dir, "default.json")
    payload = {
        "version": "1.0",
        "type": "oauth_token",
        "access_token": token,
    }
    with open(cred_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    try:
        os.chmod(cred_path, 0o600)
    except OSError:
        pass
    return cred_path


def _bootstrap_claude_setup_token(session, ctx):
    ctx["out"](
        "Claude login did not create isolated credentials; falling back to claude setup-token.\n"
    )
    run_info = _run_interactive_provider_command(
        session,
        "setup-token",
        spawn=ctx.get("spawn"),
        env_override=ctx.get("env"),
        signal_emitter=ctx.get("signal_emitter"),
    )
    transcript_path = run_info.get("transcript_path")
    if not transcript_path or not os.path.isfile(transcript_path):
        raise CdxError(
            "Claude setup-token completed, but cdx could not capture the token. "
            "Run claude setup-token and save the token under credentials/default.json."
        )
    with open(transcript_path, "r", encoding="utf-8", errors="replace") as handle:
        transcript = handle.read()
    token = _extract_claude_oauth_token(transcript)
    if not token:
        raise CdxError(
            "Claude setup-token completed, but cdx could not find CLAUDE_CODE_OAUTH_TOKEN in the output. "
            f"Transcript kept at: {transcript_path}"
        )
    try:
        os.remove(transcript_path)
    except OSError:
        pass
    return _write_claude_oauth_token(session.get("authHome") or "", token)


def handle_add(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    parsed = _parse_add_args(args)
    if parsed["provider"] == PROVIDER_OLLAMA and not parsed.get("model"):
        raise CdxError("Usage: cdx add ollama <name> --model MODEL [--json]")
    if parsed.get("model") and parsed["provider"] != PROVIDER_OLLAMA:
        raise CdxError("--model is only supported when adding an ollama session.")
    session = ctx["service"]["create_session"](parsed["name"], parsed["provider"])
    if parsed.get("model"):
        session = ctx["service"]["set_launch_settings"](parsed["name"], {"model": parsed["model"]})
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


def handle_select(rest, ctx):
    parsed = _parse_select_args(rest)
    selected = _select_headless_session(
        ctx,
        parsed["provider"],
        min_reasoning_effort=parsed["min_reasoning_effort"],
        require_ready=parsed["require_ready"],
        force_refresh=parsed["refresh"],
    )
    policy = "ready_then_cooldown_then_health_then_priority_then_name"
    if not selected:
        message = "No suitable session found."
        _write_json(ctx, _json_failure(
            "select",
            "no_suitable_session",
            message,
            provider=parsed["provider"],
            min_reasoning_effort=parsed["min_reasoning_effort"],
            require_ready=parsed["require_ready"],
            selection_policy=policy,
        ))
        return 1
    session = selected["session"]
    row = selected.get("row") or {}
    reason = "lowest available suitable session"
    _write_json(ctx, _json_success(
        "select",
        f"Selected session {session['name']}",
        session=session["name"],
        provider=session["provider"],
        reason=reason,
        selection_policy=policy,
        min_reasoning_effort=parsed["min_reasoning_effort"],
        reasoning_effort=_session_reasoning_effort(session),
        available_pct=row.get("available_pct"),
        auth_status=row.get("auth_status"),
    ))
    return 0


def _read_run_prompt(parsed):
    if parsed.get("prompt") is not None:
        return parsed["prompt"]
    try:
        with open(parsed["prompt_file"], "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as error:
        raise CdxError(f"Unable to read prompt file: {parsed['prompt_file']}") from error


def _run_usage_payload():
    return {
        "input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "total_tokens": None,
    }


def _run_cdx_error_code(error):
    message = str(error)
    if message.startswith("Usage:"):
        return "invalid_request"
    if message.startswith("Session is disabled:"):
        return "session_disabled"
    if "CLI not found on PATH" in message:
        return "provider_cli_not_found"
    if (
        message.startswith("Unsupported reasoning effort:")
        or message.startswith("Unsupported power:")
        or "--reasoning-effort and --power must match" in message
    ):
        return "invalid_reasoning_effort"
    return "cdx_error"


def _run_result_payload(ok, parsed, session, run_info=None, error=None, error_source=None, error_code=None):
    run_info = run_info or {}
    return {
        "schema_version": API_SCHEMA_VERSION,
        "ok": bool(ok),
        "action": "run",
        "session": session.get("name") if session else None,
        "provider": session.get("provider") if session else parsed.get("provider"),
        "model": parsed.get("model") or ((session.get("launch") or {}).get("model") if session else None),
        "reasoning_effort": parsed.get("reasoning_effort") or ((session.get("launch") or {}).get("reasoning_effort") if session else None),
        "power": parsed.get("power") or ((session.get("launch") or {}).get("power") if session else None),
        "cwd": os.path.abspath(parsed.get("cwd") or os.getcwd()),
        "run_id": run_info.get("run_id"),
        "exit_code": run_info.get("returncode"),
        "duration_seconds": (run_info.get("duration_ms") / 1000.0) if run_info.get("duration_ms") is not None else None,
        "transcript_path": run_info.get("transcript_path"),
        "stdout_path": run_info.get("stdout_path"),
        "stderr_path": run_info.get("stderr_path"),
        "usage": _run_usage_payload(),
        "warnings": [],
        "error": None if ok else {
            "source": error_source or "cdx",
            "code": error_code or "cdx_error",
            "message": str(error) if error else "Run failed.",
            "provider_code": run_info.get("returncode") if error_source == "provider" else None,
        },
    }


def handle_run(rest, ctx):
    try:
        parsed = _parse_run_args(rest)
        session = None
        if parsed["name"]:
            session = ctx["service"]["get_session"](parsed["name"])
            if not session:
                raise CdxError(f"Unknown session: {parsed['name']}")
            if session.get("enabled", True) is False:
                raise CdxError(f"Session is disabled: {parsed['name']}")
        else:
            selected = _select_headless_session(
                ctx,
                parsed["provider"],
                min_reasoning_effort=parsed["reasoning_effort"],
                require_ready=True,
                force_refresh=False,
            )
            if not selected:
                _write_json(ctx, _json_failure(
                    "run",
                    "no_suitable_session",
                    "No suitable session found.",
                    provider=parsed["provider"],
                ))
                return 1
            session = selected["session"]

        prompt = _read_run_prompt(parsed)
        launch_updates = {}
        if parsed.get("model"):
            launch_updates["model"] = parsed["model"]
        if parsed.get("permission"):
            launch_updates["permission"] = parsed["permission"]
        if parsed.get("reasoning_effort"):
            launch_updates["reasoning_effort"] = parsed["reasoning_effort"]
            launch_updates["power"] = parsed["reasoning_effort"]
        run_session = {
            **session,
            "launch": {
                **(session.get("launch") or {}),
                **launch_updates,
            },
        }
        _ensure_session_authentication(
            run_session,
            ctx["service"],
            spawn=ctx.get("spawn"),
            spawn_sync=ctx.get("spawn_sync"),
            env_override=ctx.get("env"),
            stdin_is_tty=False,
            behavior="launch",
            signal_emitter=ctx.get("signal_emitter"),
        )
        run_info = _run_headless_provider_command(
            run_session,
            cwd=os.path.abspath(parsed["cwd"]),
            env_override=ctx.get("env"),
            initial_prompt=prompt,
            timeout_seconds=parsed.get("timeout_seconds"),
            spawn=ctx.get("spawn_headless") or ctx.get("spawn"),
        )
        ok = run_info.get("returncode") == 0
        if ok:
            ctx["service"]["record_launch_history"](session["name"], {
                "status": "success",
                "cwd": os.path.abspath(parsed["cwd"]),
                "exit_code": 0,
                **run_info,
            })
            _write_json(ctx, _run_result_payload(True, parsed, run_session, run_info=run_info))
            return 0
        message = "Provider process timed out." if run_info.get("timed_out") else "Provider process exited with a non-zero status."
        error = CdxError(message, run_info.get("returncode") or 1)
        ctx["service"]["record_launch_history"](session["name"], {
            "status": "failed",
            "cwd": os.path.abspath(parsed["cwd"]),
            "error": str(error),
            "exit_code": error.exit_code,
            **run_info,
        })
        _write_json(ctx, _run_result_payload(
            False,
            parsed,
            run_session,
            run_info=run_info,
            error=error,
            error_source="provider",
            error_code="provider_timeout" if run_info.get("timed_out") else "provider_failed",
        ))
        return error.exit_code or 1
    except CdxError as error:
        run_info = getattr(error, "run_info", None)
        _write_json(ctx, _run_result_payload(
            False,
            locals().get("parsed", {}) or {},
            locals().get("session"),
            run_info=run_info,
            error=error,
            error_source="cdx",
            error_code=_run_cdx_error_code(error),
        ))
        return error.exit_code


def _format_launch_config(session):
    launch = session.get("launch") or {}
    return "\n".join([
        f"{session['name']} ({session['provider']})",
        f"power:      {launch.get('power') or 'default'}",
        f"permission: {launch.get('permission') or 'default'}",
        f"fast:       {'on' if launch.get('fast') is True else 'off' if launch.get('fast') is False else 'default'}",
        f"model:      {launch.get('model') or 'default'}",
        f"priority:   {launch.get('priority') if launch.get('priority') is not None else 'default'}",
    ])


def _resolve_bulk_launch_targets(parsed, service):
    sessions = service["list_sessions"]()
    by_name = {session["name"]: session for session in sessions}
    if parsed.get("name"):
        session = by_name.get(parsed["name"])
        if not session:
            raise CdxError(f"Unknown session: {parsed['name']}")
        targets = [session]
    elif parsed.get("sessions") == "all":
        targets = sessions
    elif parsed.get("sessions"):
        targets = []
        for name in parsed["sessions"]:
            session = by_name.get(name)
            if not session:
                raise CdxError(f"Unknown session: {name}")
            targets.append(session)
    else:
        targets = sessions
    if parsed.get("provider"):
        targets = [session for session in targets if session["provider"] == parsed["provider"]]
    if not targets:
        raise CdxError("No sessions matched.")
    return targets


def _reasoning_rank(value):
    order = {"low": 0, "medium": 1, "high": 2, "xhigh": 2, "max": 2}
    return order.get(str(value or "low").lower(), 0)


def _session_reasoning_effort(session):
    launch = session.get("launch") or {}
    return (
        launch.get("reasoning_effort")
        or launch.get("reasoningEffort")
        or launch.get("power")
        or ("low" if launch.get("fast") is True else None)
        or "low"
    )


def _session_selection_priority(session):
    launch = session.get("launch") or {}
    try:
        return int(launch.get("priority") or 0)
    except (TypeError, ValueError):
        return 0


def _row_blocks_ready(row):
    auth = row.get("auth_status") or "unknown"
    if auth not in ("authenticated", "n/a"):
        return True
    available = row.get("available_pct")
    if available is not None:
        try:
            if float(available) <= 0:
                return True
        except (TypeError, ValueError):
            return True
    return False


def _select_headless_session(ctx, provider, min_reasoning_effort=None, require_ready=False, force_refresh=False):
    sessions = [
        session for session in ctx["service"]["list_sessions"]()
        if session.get("provider") == provider and session.get("enabled", True) is not False
    ]
    minimum = _reasoning_rank(min_reasoning_effort)
    sessions = [
        session for session in sessions
        if _reasoning_rank(_session_reasoning_effort(session)) >= minimum
    ]
    rows = ctx["service"]["get_status_rows"](force_refresh=force_refresh)
    row_by_name = {row.get("session_name"): row for row in rows}
    candidates = []
    for session in sessions:
        row = row_by_name.get(session["name"], {})
        if require_ready and _row_blocks_ready(row):
            continue
        available = row.get("available_pct")
        try:
            available_sort = float(available) if available is not None else -1.0
        except (TypeError, ValueError):
            available_sort = -1.0
        cooldown_sort = 1 if available_sort > 0 else 0
        candidates.append({
            "session": session,
            "row": row,
            "sort_key": (
                -cooldown_sort,
                -available_sort,
                _reasoning_rank(_session_reasoning_effort(session)),
                -_session_selection_priority(session),
                session["name"],
            ),
        })
    if not candidates:
        return None
    candidates.sort(key=lambda item: item["sort_key"])
    return candidates[0]


def _format_bulk_launch_summary(sessions):
    names = [session["name"] for session in sessions]
    if len(names) <= 8:
        return ", ".join(names)
    return ", ".join(names[:8]) + f", +{len(names) - 8} more"


def _format_duration_ms(value):
    if value is None:
        return "-"
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return str(value)
    if amount < 1000:
        return f"{amount}ms"
    seconds = amount / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining = int(seconds % 60)
    return f"{minutes}m{remaining:02d}s"


def _summarize_history(entries):
    by_session = {}
    for entry in entries:
        name = entry.get("session_name") or "-"
        row = by_session.setdefault(name, {
            "session_name": name,
            "provider": entry.get("provider") or "-",
            "launches": 0,
            "successes": 0,
            "failures": 0,
            "duration_ms": 0,
            "last_started_at": None,
        })
        row["launches"] += 1
        if entry.get("status") == "success":
            row["successes"] += 1
        elif entry.get("status") == "failed":
            row["failures"] += 1
        try:
            row["duration_ms"] += int(entry.get("duration_ms") or 0)
        except (TypeError, ValueError):
            pass
        started = entry.get("started_at")
        if started and (not row["last_started_at"] or started > row["last_started_at"]):
            row["last_started_at"] = started
            row["provider"] = entry.get("provider") or row["provider"]
    return sorted(
        by_session.values(),
        key=lambda item: (item["duration_ms"], item.get("last_started_at") or "", item["session_name"]),
        reverse=True,
    )


def _format_history_period(period):
    if not _has_history_period(period or {}):
        return None
    start = _format_period_display(period.get("from")) or "beginning"
    end = _format_period_display(period.get("to")) or "now"
    return f"Period: {start} -> {end}"


def _format_period_display(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return parsed.strftime("%Y-%m-%d %H:%M")


def _format_history_summary(entries, period=None, use_color=False):
    from .cli_render import _format_relative_age, _pad_table

    summary = _summarize_history(entries)
    if not summary:
        return "No launch history for this period." if _has_history_period(period or {}) else "No launch history."
    rows = [["SESSION", "PROV.", "LAUNCHES", "OK", "FAIL", "TIME", "LAST"]]
    for row in summary:
        rows.append([
            row["session_name"],
            row["provider"],
            str(row["launches"]),
            str(row["successes"]),
            str(row["failures"]),
            _format_duration_ms(row["duration_ms"]),
            _format_relative_age(row.get("last_started_at")),
        ])
    lines = ["Assistant time:"]
    period_line = _format_history_period(period or {})
    if period_line:
        lines.extend([period_line, ""])
    lines.append(_pad_table(rows))
    return "\n".join(lines)


def _format_history(entries, use_color=False):
    from .cli_render import _format_relative_age, _pad_table

    if not entries:
        return "No launch history."
    rows = [["SESSION", "PROV.", "RESULT", "DURATION", "WHEN", "TRANSCRIPT"]]
    for entry in entries:
        transcript_path = entry.get("transcript_path")
        rows.append([
            entry.get("session_name") or "-",
            entry.get("provider") or "-",
            entry.get("status") or "-",
            _format_duration_ms(entry.get("duration_ms")),
            _format_relative_age(entry.get("started_at")),
            os.path.basename(transcript_path) if transcript_path else "-",
        ])
    return "\n".join([
        "Recent launches:",
        _pad_table(rows),
        "",
        _dim("Full transcript paths and cwd are available with --json.", use_color),
    ])


def _apply_launch_settings(parsed, ctx, action="set"):
    targets = _resolve_bulk_launch_targets(parsed, ctx["service"])
    sessions = [
        ctx["service"]["set_launch_settings"](session["name"], parsed["settings"])
        for session in targets
    ]
    if len(sessions) == 1:
        session = sessions[0]
        message = f"Updated launch settings for {session['name']}"
    else:
        message = f"Updated launch settings for {len(sessions)} sessions: {_format_bulk_launch_summary(sessions)}"
    if parsed["json"]:
        payload = _json_success(
            action,
            message,
            updated_count=len(sessions),
            session=sessions[0] if len(sessions) == 1 else None,
            sessions=sessions,
            launch=sessions[0].get("launch") or {} if len(sessions) == 1 else None,
        )
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    if len(sessions) == 1:
        ctx["out"](f"{_format_launch_config(sessions[0])}\n")
    return 0


def _clear_launch_settings(parsed, ctx, action="unset"):
    targets = _resolve_bulk_launch_targets(parsed, ctx["service"])
    sessions = [
        ctx["service"]["unset_launch_settings"](session["name"], parsed["keys"])
        for session in targets
    ]
    if len(sessions) == 1:
        session = sessions[0]
        message = f"Cleared launch settings for {session['name']}"
    else:
        message = f"Cleared launch settings for {len(sessions)} sessions: {_format_bulk_launch_summary(sessions)}"
    if parsed["json"]:
        payload = _json_success(
            action,
            message,
            updated_count=len(sessions),
            session=sessions[0] if len(sessions) == 1 else None,
            sessions=sessions,
            launch=sessions[0].get("launch") or {} if len(sessions) == 1 else None,
        )
        _write_json(ctx, payload)
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
    if len(sessions) == 1:
        ctx["out"](f"{_format_launch_config(sessions[0])}\n")
    return 0


def handle_set(rest, ctx):
    return _apply_launch_settings(_parse_set_args(rest), ctx)


def handle_unset(rest, ctx):
    return _clear_launch_settings(_parse_unset_args(rest), ctx)


def handle_launch_setting_alias(kind, rest, ctx):
    parsed = _parse_launch_setting_alias_args(kind, rest)
    if parsed.get("settings"):
        return _apply_launch_settings(parsed, ctx, action=kind)
    return _clear_launch_settings(parsed, ctx, action=kind)


def handle_config(rest, ctx):
    parsed = _parse_config_args(rest)
    session = ctx["service"]["get_session"](parsed["name"])
    if not session:
        raise CdxError(f"Unknown session: {parsed['name']}")
    message = f"Launch settings for {parsed['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("config", message, session=session, launch=session.get("launch") or {}))
        return 0
    ctx["out"](f"{_format_launch_config(session)}\n")
    return 0


def handle_history(rest, ctx):
    now_fn = ctx["options"].get("now") or time.time
    now = datetime.fromtimestamp(now_fn()).astimezone()
    parsed = _parse_history_args(rest, now=now)
    has_period = _has_history_period(parsed["period"])
    limit = 0 if parsed["summary"] or has_period else parsed["limit"]
    entries = ctx["service"]["get_launch_history"](parsed["name"], limit=limit)
    entries = _filter_history_period(entries, parsed["period"])
    if has_period and not parsed["summary"]:
        entries = entries[:parsed["limit"]]
    message = (
        f"Listed launch history for {parsed['name']}"
        if parsed["name"]
        else "Listed launch history"
    )
    if parsed["json"]:
        payload = {"history": entries, "period": _public_history_period(parsed["period"])}
        if parsed["summary"]:
            payload["summary"] = _summarize_history(entries)
        _write_json(ctx, _json_success("history", message, **payload))
        return 0
    if parsed["summary"]:
        ctx["out"](f"{_format_history_summary(entries, period=parsed['period'], use_color=ctx['use_color'])}\n")
        return 0
    ctx["out"](f"{_format_history(entries, use_color=ctx['use_color'])}\n")
    return 0


def _resolve_last_launch_session(ctx):
    for entry in ctx["service"]["get_launch_history"](limit=0):
        name = entry.get("session_name")
        if not name:
            continue
        session = ctx["service"]["get_session"](name)
        if session:
            return session
    raise CdxError("No launch history yet. Run cdx <name> first.")


def handle_last(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if args:
        raise CdxError(LAST_USAGE)
    session = _resolve_last_launch_session(ctx)
    if not json_flag:
        message = f"Launching last session: {session['name']}"
        ctx["out"](f"{_info(message, ctx['use_color'])}\n")
    return handle_launch(session["name"], ctx)


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
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--dry-run": {"key": "dry_run", "type": "bool", "default": False},
        "--force": {"key": "force", "type": "bool", "default": False},
    }, REPAIR_USAGE)
    dry_run = parsed["dry_run"] or not parsed["force"]
    report = repair_health(
        ctx["service"],
        ctx["service"]["base_dir"],
        env=ctx.get("env"),
        dry_run=dry_run,
        force=parsed["force"],
    )
    if parsed["json"]:
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

    if parsed["schedule"]:
        event = resolve_notify_event(
            ctx["service"]["get_status_rows"](
                progress_callback=None if parsed["json"] else _make_notify_progress(ctx),
                force_refresh=parsed.get("refresh", False),
            ),
            parsed,
            (ctx["options"].get("now") or time.time)(),
        )
        if event["ready"]:
            notifier(event["title"], event["message"])
            schedule = {
                "scheduled": False,
                "backend": "immediate",
                "message": event["message"],
                "target_timestamp": event.get("target_timestamp"),
            }
        else:
            schedule = schedule_notification_event(
                ctx["service"]["base_dir"],
                parsed,
                event,
                spawn_sync=ctx.get("spawn_sync"),
                env=ctx.get("env"),
                now_fn=ctx["options"].get("now"),
            )
        if parsed["json"]:
            _write_json(ctx, _json_success("notify", "Scheduled notification event", event=event, schedule=schedule))
        else:
            ctx["out"](f"{format_scheduled_notification(schedule)}\n")
        return 0

    event = wait_for_notification_event(
        ctx["service"],
        parsed,
        notifier=notifier,
        sleep_fn=ctx["options"].get("sleep"),
        now_fn=ctx["options"].get("now"),
        progress_callback=None if parsed["json"] else _make_notify_progress(ctx),
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
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--small": {"key": "small", "type": "bool", "default": False},
        "-s": {"key": "small", "type": "bool", "default": False},
        "--refresh": {"key": "refresh", "type": "bool", "default": False},
    }, STATUS_USAGE, positionals_key="args", max_positionals=1)
    if parsed["json"] and parsed["small"]:
        raise CdxError(STATUS_USAGE)
    args = parsed["args"]
    if len(args) == 1 and parsed["small"]:
        raise CdxError(STATUS_USAGE)

    auth_refresh = _refresh_claude_auth_states(
        ctx["service"],
        target_names=args if len(args) == 1 else None,
        spawn_sync=ctx.get("spawn_sync"),
        env_override=ctx.get("env"),
    )
    warnings = [
        {
            "code": "claude_auth_probe_failed",
            "session": item.get("session") or "unknown",
            "message": item.get("error") or "unknown error",
        }
        for item in auth_refresh.get("errors", [])
    ]
    refresh_result = _refresh_claude_sessions(
        ctx["service"],
        ctx.get("refresh_fn"),
        target_names=args if len(args) == 1 else None,
        force=parsed["refresh"],
    )
    refresh_errors = [
        {
            "session": item.get("session"),
            "error": str(item.get("error")),
        }
        for item in refresh_result.get("errors", [])
    ]
    warnings.extend([
        {
            "code": "claude_refresh_failed",
            "session": item.get("session") or "unknown",
            "message": item.get("error") or "unknown error",
        }
        for item in refresh_errors
    ])
    update_warning = _update_notice_warning(ctx)
    if update_warning:
        warnings.append(update_warning)

    status_progress = None if parsed["json"] else _make_status_progress(ctx)
    rows = ctx["service"]["get_status_rows"](
        progress_callback=status_progress,
        force_refresh=parsed["refresh"],
    )
    if len(args) == 0:
        if parsed["json"]:
            _write_json(ctx, _json_success("status", "Collected session status rows", warnings=warnings, rows=rows))
            return 0
        ctx["out"](f"{_format_status_rows(rows, use_color=ctx['use_color'], small=parsed['small'])}\n")
        _write_refresh_warnings(refresh_errors, ctx)
        _write_update_notice(ctx)
        return 0

    row = next((r for r in rows if r["session_name"] == args[0]), None)
    if not row:
        raise CdxError(f"Unknown session: {args[0]}")
    if parsed["json"]:
        _write_json(ctx, _json_success("status", f"Collected status for {args[0]}", warnings=warnings, session=row))
        return 0
    ctx["out"](f"{_format_status_detail(row, use_color=ctx['use_color'])}\n")
    _write_refresh_warnings(refresh_errors, ctx)
    _write_update_notice(ctx)
    return 0


def _refresh_claude_auth_states(service, target_names=None, spawn_sync=None, env_override=None):
    target_names = set(target_names or [])
    errors = []
    updated = []
    for session in service["list_sessions"]():
        if session["provider"] != PROVIDER_CLAUDE:
            continue
        if session.get("enabled", True) is False:
            continue
        if target_names and session["name"] not in target_names:
            continue
        if (session.get("auth") or {}).get("status") not in ("authenticated", "logged_out"):
            continue
        try:
            authenticated = _probe_provider_auth(
                session,
                spawn_sync=spawn_sync,
                env_override=env_override,
            )
            now = _local_now_iso()
            service["update_auth_state"](session["name"], lambda auth: {
                **auth,
                "status": "authenticated" if authenticated else "logged_out",
                "lastCheckedAt": now,
                **({"lastAuthenticatedAt": now} if authenticated else {}),
            })
            updated.append(session["name"])
        except Exception as error:
            errors.append({"session": session["name"], "error": str(error)})
    return {"updated": updated, "errors": errors}


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
        progress_callback=None if parsed["json"] else _make_export_progress(ctx),
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
    ctx["out"](f"{_format_export_report(result)}\n")
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
    if session["provider"] == PROVIDER_CODEX:
        _run_interactive_provider_command(
            session, "logout", spawn=ctx.get("spawn"), env_override=ctx.get("env"),
            signal_emitter=ctx.get("signal_emitter")
        )
    _run_interactive_provider_command(
        session, "login", spawn=ctx.get("spawn"), env_override=ctx.get("env"),
        signal_emitter=ctx.get("signal_emitter")
    )
    auth_probe = _ensure_session_authentication(
        session,
        ctx["service"],
        spawn_sync=ctx.get("spawn_sync"),
        env_override=ctx.get("env"),
        behavior="probe-only",
    )
    if not auth_probe.get("authenticated") and session["provider"] == PROVIDER_CLAUDE:
        _bootstrap_claude_setup_token(session, ctx)
        auth_probe = _ensure_session_authentication(
            session,
            ctx["service"],
            spawn_sync=ctx.get("spawn_sync"),
            env_override=ctx.get("env"),
            behavior="probe-only",
        )
    if not auth_probe.get("authenticated"):
        raise CdxError(
            f"Login command completed, but session {session['name']} is still not authenticated."
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
    if session["provider"] == PROVIDER_ANTIGRAVITY:
        raise CdxError("Antigravity logout is managed inside agy. Launch the session and run /logout.")
    if session["provider"] == PROVIDER_OLLAMA:
        raise CdxError("Ollama sessions do not use cdx-managed authentication.")
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
        try:
            latest = (
                release_fetcher()
                if ctx["options"].get("fetchLatestRelease")
                else fetch_latest_release_or_raise(env=ctx.get("env"))
            )
        except LatestReleaseCheckError as error:
            raise CdxError(str(error)) from error
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
    json_flag = "--json" in ctx.get("raw_args", ctx["options"].get("raw_args", []))
    update_notice = ctx.get("update_notice")
    warnings = []
    if update_notice:
        warnings.append(_update_notice_warning(ctx))
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
        _write_update_notice(ctx)
    cwd = ctx.get("cwd") or os.getcwd()
    runtime_run_id = None

    def runtime_lifecycle(event, info):
        nonlocal runtime_run_id
        if event == "started":
            runtime = ctx["service"]["start_session_runtime"](session["name"], info)
            runtime_run_id = runtime.get("runId")
        elif event == "finished" and runtime_run_id:
            ctx["service"]["finish_session_runtime"](
                session["name"],
                runtime_run_id,
                {"status": "stopped", "returncode": info.get("returncode")},
            )

    try:
        run_info = _run_interactive_provider_command(
            session, "launch", spawn=ctx.get("spawn"), cwd=cwd, env_override=ctx.get("env"),
            signal_emitter=ctx.get("signal_emitter"), initial_prompt=initial_prompt,
            lifecycle_callback=runtime_lifecycle,
        )
    except CdxError as error:
        run_info = getattr(error, "run_info", {}) or {}
        if runtime_run_id:
            ctx["service"]["finish_session_runtime"](
                session["name"],
                runtime_run_id,
                {"status": "failed", "returncode": run_info.get("returncode")},
            )
        if run_info:
            ctx["service"]["record_launch_history"](session["name"], {
                "status": "failed",
                "cwd": cwd,
                "error": str(error),
                "exit_code": error.exit_code,
                **run_info,
            })
        raise
    ctx["service"]["record_launch_history"](session["name"], {
        "status": "success",
        "cwd": cwd,
        "exit_code": 0,
        **run_info,
    })
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
    transcript_path = _latest_handoff_transcript_path(source)
    if not transcript_path:
        raise CdxError(f"No transcript found for session: {source_name}")
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
