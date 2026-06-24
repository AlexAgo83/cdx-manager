#!/usr/bin/env python3
"""Shared helpers for cdx commands: JSON envelopes, formatting, handoff transcripts.

Split out of cli_commands.py as the low-level, side-effect-light helper layer
(no command dispatch). Imported back into cli_commands and used by handlers.
"""

import json
import os
import re
from datetime import datetime

from .cli_render import _dim, _info, _warn
from .config import PROVIDER_CODEX
from .provider_runtime import _list_launch_transcript_paths
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


def _update_notice_warning(ctx):
    notices = ctx.get("update_notices") or []
    if not notices:
        return None
    warnings = _update_notice_warnings(ctx)
    return warnings[0] if warnings else None


def _update_notice_warnings(ctx):
    warnings = []
    for notice in ctx.get("update_notices") or []:
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
    progress_state = {"checked": 0, "total": 0}

    def progress(event):
        kind = event.get("event")
        if kind == "status_started":
            progress_state["checked"] = 0
            progress_state["total"] = event.get("check_count", event.get("session_count", 0)) or 0
            message = f"Resolving status for {event.get('session_count', 0)} session(s)..."
            ctx["out"](f"{_info(message, ctx['use_color'])}\n")
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
    return progress


def _make_notify_progress(ctx):
    progress_state = {"checked": 0, "total": 0}

    def progress(event):
        kind = event.get("event")
        if kind == "notify_check_started":
            target = event.get("session_name") or "next ready session"
            ctx["out"](f"{_info(f'Checking notification target: {target}...', ctx['use_color'])}\n")
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
