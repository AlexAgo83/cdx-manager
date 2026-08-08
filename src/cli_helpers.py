#!/usr/bin/env python3
"""Shared helpers for cdx commands: JSON envelopes, formatting, handoff transcripts.

Split out of cli_commands.py as the low-level, side-effect-light helper layer
(no command dispatch). Imported back into cli_commands and used by handlers.
"""

import asyncio
import json
import os
import re
from datetime import datetime

from .cli_render import _dim, _info, _pad_table, _style, _warn
from .config import PROVIDER_CODEX
from .errors import CdxError
from .fs_utils import atomic_write
from .provider_runtime import _list_launch_transcript_paths, _run_interactive_provider_command, get_resume_capability
from .status_source import _normalize_terminal_transcript

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


def _update_notice_warnings(ctx):
    warnings = []
    for notice in ctx.get("update_notices") or []:
        if notice.get("code") == "disk_cleanup_available":
            warnings.append({
                "code": "disk_cleanup_available",
                "message": notice["message"],
                **{key: value for key, value in notice.items() if key not in ("code", "message")},
            })
            continue
        tool = notice.get("tool") or "cdx-manager"
        current = notice.get("current_version") or ctx.get("version")
        command = notice.get("update_command") or ("cdx update" if tool == "cdx-manager" else None)
        message = f"Update available: {tool} {notice['latest_version']}"
        if current:
            message = f"{message} (current {current})"
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


def _write_update_notice(ctx):
    warnings = _update_notice_warnings(ctx)
    if not warnings:
        return
    for warning in warnings:
        ctx["out"](f"{_warn(warning['message'], ctx['use_color'])}\n")


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
    return f"{int(amount)} {unit}" if amount.is_integer() else f"{amount:.1f} {unit}"


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


def _make_session_progress(ctx, start_event, start_message):
    progress_state = {"checked": 0, "total": 0}

    def progress(event):
        kind = event.get("event")
        if kind == start_event:
            if kind == "status_started":
                progress_state["checked"] = 0
                progress_state["total"] = event.get("check_count", event.get("session_count", 0)) or 0
            ctx["out"](f"{_info(start_message(event), ctx['use_color'])}\n")
        elif kind == "status_started":
            progress_state["checked"] = 0
            progress_state["total"] = event.get("check_count", event.get("session_count", 0)) or 0
            message = f"Loading status for {event.get('session_count', 0)} session(s)..."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
        elif kind == "session_started":
            provider = event.get("provider") or "session"
            message = f"Checking {event.get('session_name')} ({provider})..."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
        elif kind == "session_finished" and not event.get("cache_hit"):
            progress_state["checked"] += 1
            total = progress_state["total"] or progress_state["checked"]
            message = f"Checked {event.get('session_name')} ({progress_state['checked']}/{total})."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
        elif kind == "status_finished":
            message = f"Resolved {event.get('row_count', 0)} status row(s)."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
        elif kind == "notify_waiting":
            message = f"{event.get('message')}; checking again in {event.get('poll')}s..."
            ctx["out"](f"{_dim(message, ctx['use_color'])}\n")
    return progress


def _make_status_progress(ctx):
    return _make_session_progress(
        ctx,
        "status_started",
        lambda event: f"Resolving status for {event.get('session_count', 0)} session(s)...",
    )


def _make_notify_progress(ctx):
    return _make_session_progress(
        ctx,
        "notify_check_started",
        lambda event: f"Checking notification target: {event.get('session_name') or 'next ready session'}...",
    )


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
    native_paths = _collect_native_handoff_transcript_paths(session)
    if native_paths:
        return native_paths[0]
    return _latest_launch_transcript_path(session)


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
    if record.get("type") == "response_item":
        record = record.get("payload")
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
    if role not in ("user", "assistant"):
        return None
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
    with open(path, encoding="utf-8", errors="replace") as handle:
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
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _read_handoff_transcript(path):
    if path.endswith(".jsonl"):
        content = _read_jsonl_handoff_transcript(path)
    else:
        with open(path, encoding="utf-8", errors="replace") as handle:
            # `script`-captured PTY transcript: strip ANSI/control noise before
            # the char-budget truncation so the tail holds real text, not escapes.
            content = _normalize_terminal_transcript(handle.read())
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
    os.makedirs(cred_dir, mode=0o700, exist_ok=True)
    try:
        os.chmod(cred_dir, 0o700)
    except OSError:
        pass
    cred_path = os.path.join(cred_dir, "default.json")
    payload = {
        "version": "1.0",
        "type": "oauth_token",
        "access_token": token,
    }
    # atomic_write keeps the token 0o600 from creation — no umask window.
    atomic_write(cred_path, json.dumps(payload, indent=2) + "\n", mode=0o600)
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
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as handle:
            transcript = handle.read()
    finally:
        # The transcript holds the ~1-year OAuth token in cleartext; it must
        # not outlive the extraction, whether it succeeds or not.
        try:
            os.remove(transcript_path)
        except OSError:
            pass
    token = _extract_claude_oauth_token(transcript)
    if not token:
        raise CdxError(
            "Claude setup-token completed, but cdx could not find CLAUDE_CODE_OAUTH_TOKEN in the output. "
            "Run claude setup-token manually and save the token under credentials/default.json."
        )
    auth_home = session.get("authHome") or ""
    cred_path = _write_claude_oauth_token(auth_home, token)
    # ponytail: drop short-lived claude login creds so the ~1yr token wins at launch (provider_runtime _read_claude_launch_oauth_token)
    try:
        os.remove(os.path.join(auth_home, ".claude", ".credentials.json"))
    except OSError:
        pass
    return cred_path

def _format_launch_config(session, use_color=False):
    from .cli_render import _dim, _style

    launch = session.get("launch") or {}
    rows = [[_style("SETTING", "1", use_color), _style("VALUE", "1", use_color)]]
    for key, label in [
        ("power", "Power"),
        ("permission", "Permission"),
        ("fast", "Fast"),
        ("rtk", "RTK"),
        ("logics", "Logics"),
        ("model", "Model"),
        ("fallback_model", "Fallback"),
        ("budget", "Budget"),
        ("priority", "Priority"),
    ]:
        rows.append([
            _dim(label, use_color),
            _format_launch_setting_value(launch, key, use_color=use_color),
        ])
    provider_label = f"({session['provider']})"
    return "\n".join([
        _style("Launch settings:", "1", use_color),
        f"{_style(session['name'], '36', use_color)} {_dim(provider_label, use_color)}",
        _pad_table(rows),
        "",
        _dim(_format_launch_settings_hint(session["name"]), use_color),
    ])

def _format_launch_settings_hint(name="<name>"):
    return (
        f"Set a value: cdx set {name} --power medium --permission auto "
        "--fast on --rtk on --logics on --model MODEL --priority 80"
    )

def _format_launch_setting_value(launch, key, use_color=False):
    if key in ("fast", "rtk", "logics"):
        if launch.get(key) is True:
            return _style("on", "32", use_color)
        if launch.get(key) is False:
            return _style("off", "2", use_color)
        if key == "logics":
            return _dim("auto", use_color)
        return _dim("default", use_color)
    value = launch.get(key)
    if value is None or value == "":
        return _dim("default", use_color)
    if key == "budget":
        from .provider_runtime import _format_budget_arg

        return _style(_format_budget_arg(value), "33", use_color)
    if key == "priority":
        return _style(str(value), "33", use_color)
    if key == "power":
        return _style(str(value), "96", use_color)
    if key == "permission":
        return _style(str(value), "32", use_color)
    return str(value)

def _resume_capability_for_session(session, ctx):
    capability = get_resume_capability(session, cwd=ctx.get("cwd") or os.getcwd())
    return {
        "session": session["name"],
        "provider": session["provider"],
        "resumable": bool(capability.get("resumable")),
        "strategy": capability.get("strategy"),
        "reason": capability.get("reason"),
        "command_preview": capability.get("command_preview") or [],
    }

def _warn_if_session_already_running(name, ctx):
    # ponytail: concurrent sessions on one profile share its single OAuth
    # .credentials.json; both refresh near token expiry and the rotated refresh
    # token invalidates the other session -> surprise logout. Warn before adding
    # a second live session on the same profile.
    active = ctx["service"].get("active_session_runtime")
    runtime = active(name) if active else None
    if not runtime:
        return
    pid = runtime.get("pid")
    ctx["out"](f"{_warn(f'A session named {name} is already running (pid {pid}).', ctx['use_color'])}\n")
    ctx["out"](
        f"{_dim('Two sessions on one profile share its login and can log each other out. Use a different profile instead.', ctx['use_color'])}\n"
    )
    if not ctx["stdin_is_tty"]:
        return
    answer = input(f"Launch a second {name} session anyway? [y/N] ")
    if answer.strip().lower() not in ("y", "yes"):
        raise CdxError("Launch cancelled.")
