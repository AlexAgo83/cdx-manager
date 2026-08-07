import os
import shlex
import time
import uuid
from datetime import datetime

from .claude_refresh import _refresh_claude_sessions
from .cli_args import (
    CAN_RESUME_USAGE,
    HANDOFF_USAGE,
    LAST_USAGE,
    RESUME_USAGE,
    STATUS_USAGE,
    _filter_history_period,
    _has_history_period,
    _parse_config_args,
    _parse_configs_args,
    _parse_flag_args,
    _parse_history_args,
    _parse_json_flag,
    _parse_next_args,
    _parse_stats_args,
    _parse_timeout_seconds,
    _public_history_period,
)
from .cli_helpers import (  # noqa: F401  (several names are re-exported for cli.py / tests)
    API_SCHEMA_VERSION,
    _bootstrap_claude_setup_token,
    _build_handoff_context,
    _extract_claude_oauth_token,
    _format_bytes,
    _format_launch_config,
    _format_launch_setting_value,
    _format_launch_settings_hint,
    _handoff_launch_prompt,
    _json_failure,
    _json_success,
    _latest_handoff_transcript_path,
    _local_now_iso,
    _make_notify_progress,
    _make_status_progress,
    _read_handoff_transcript,
    _resolve_confirmation,
    _resume_capability_for_session,
    _update_notice_warnings,
    _warn_if_session_already_running,
    _write_claude_oauth_token,
    _write_json,
    _write_update_notice,
)
from .cli_render import _dim, _info, _pad_table, _style, _success, _warn
from .cli_view import handle_view as handle_view  # re-export for cli.py / tests
from .codex_usage import consume_codex_rate_limit_reset_credit
from .commands.backup import (  # noqa: F401
    _resolve_bundle_passphrase,
    handle_export,
    handle_import,
)

# Re-exported for cli.py and tests; see src/commands/__init__.py.
from .commands.context_memory import (  # noqa: F401
    _list_memory_entries,
    _memory_payload,
    _memory_target,
    _parse_memory_args,
    handle_context,
    handle_memory,
)
from .commands.lifecycle import (  # re-export for cli.py / tests
    _confirm_removal as _confirm_removal,
)
from .commands.lifecycle import (
    handle_add as handle_add,
)
from .commands.lifecycle import (
    handle_copy as handle_copy,
)
from .commands.lifecycle import (
    handle_disable as handle_disable,
)
from .commands.lifecycle import (
    handle_enable as handle_enable,
)
from .commands.lifecycle import (
    handle_label as handle_label,
)
from .commands.lifecycle import (
    handle_remove as handle_remove,
)
from .commands.lifecycle import (
    handle_rename as handle_rename,
)

# Re-exported for cli.py and tests; see src/commands/__init__.py.
from .commands.maintenance import (  # noqa: F401
    _candidate,
    _clean_profile_old_logs,
    _clean_profile_tmp,
    _collect_old_logs,
    _collect_profile_cleanup_candidates,
    _confirm_log_cleanup,
    _confirm_profile_cleanup,
    _directory_child_sizes,
    _directory_size_bytes,
    _format_cleanup_candidates,
    _format_disk_report,
    _format_update_all,
    _format_update_all_result,
    _handle_clean_profiles,
    _iter_profile_dirs,
    _parse_days,
    _remove_path,
    handle_clean,
    handle_disk,
    handle_doctor,
    handle_repair,
    handle_update,
)

# Re-exported for cli.py and tests; see src/commands/__init__.py.
from .commands.runs import (  # noqa: F401
    DETACHED_PROMPT_SUFFIX,
    DETACHED_RUN_ID_ENV,
    RUN_TAIL_READ_BYTES,
    _cdx_self_command,
    _consume_detached_prompt_file,
    _detached_child_argv,
    _detached_spawn_options,
    _run_registry,
    _select_headless_session,
    _selection_reason,
    _spawn_detached_run,
    _tail_file_lines,
    handle_run,
    handle_run_report,
    handle_run_status,
    handle_run_tail,
    handle_runs,
    handle_schema,
    handle_select,
)

# Re-exported for cli.py and tests; see src/commands/__init__.py.
from .commands.settings import (  # re-export for cli.py / tests
    _apply_launch_settings as _apply_launch_settings,
)
from .commands.settings import (
    _clear_launch_settings as _clear_launch_settings,
)
from .commands.settings import (
    _format_bulk_launch_summary as _format_bulk_launch_summary,
)
from .commands.settings import (
    _resolve_bulk_launch_targets as _resolve_bulk_launch_targets,
)
from .commands.settings import (
    handle_launch_setting_alias as handle_launch_setting_alias,
)
from .commands.settings import (
    handle_set as handle_set,
)
from .commands.settings import (
    handle_unset as handle_unset,
)
from .config import PROVIDER_ANTIGRAVITY, PROVIDER_CLAUDE, PROVIDER_CODEX, PROVIDER_OLLAMA
from .context_store import (
    install_context_for_session,
    write_context,
)
from .errors import CdxError
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
    AUTH_PROBE_AUTHENTICATED,
    AUTH_PROBE_DEGRADED,
    _ensure_session_authentication,
    _probe_provider_auth_status,
    _run_interactive_provider_command,
)
from .status_view import (
    _format_status_detail,
    _format_status_rows,
    format_priority_instruction,
    recommend_priority_rows,
)


def _confirm_reset(name):
    answer = input(f"Consume one banked Codex reset for {name}? [y/N] ")
    return answer.strip().lower() in ("y", "yes")


def _format_next_pct(value):
    return "n/a" if value is None else f"{value}%"


def _next_action(row):
    instruction = format_priority_instruction(row, "first")
    return "refresh" if instruction.startswith("refresh ") else "use"


def _format_next_selection(session, row, use_color=False):

    action = _next_action(row)
    command = f"cdx status {session['name']} --refresh" if action == "refresh" else f"cdx {session['name']}"
    rows = [[_style(value, "1", use_color) for value in ["SESSION", "PROVIDER", "OK", "5H", "WEEK", "REASON"]]]
    rows.append([
        _style(session["name"], "36", use_color),
        _dim(session.get("provider") or "-", use_color),
        _format_next_pct(row.get("available_pct")),
        _format_next_pct(row.get("remaining_5h_pct")),
        _format_next_pct(row.get("remaining_week_pct")),
        format_priority_instruction(row, "first"),
    ])
    return "\n".join([
        _style("Next assistant:", "1", use_color),
        _pad_table(rows),
        "",
        f"{_style('Run:', '1', use_color)} {_style(command, '36', use_color)}",
    ])


def handle_next(rest, ctx):
    parsed = _parse_next_args(rest)
    rows = ctx["service"]["get_status_rows"](force_refresh=parsed["refresh"])
    priority = recommend_priority_rows(rows)
    if not priority:
        message = "No usable session status yet."
        if parsed["json"]:
            _write_json(ctx, _json_failure("next", "no_suitable_session", message, selection_policy="status_priority"))
            return 1
        ctx["out"](f"{_warn(message, ctx['use_color'])}\n")
        return 1
    row = priority[0]
    session_name = row.get("session_name")
    session = ctx["service"]["get_session"](session_name)
    if not session:
        message = f"Selected status row has no matching session: {session_name}"
        if parsed["json"]:
            _write_json(ctx, _json_failure("next", "missing_session", message, selection_policy="status_priority", row=row))
            return 1
        raise CdxError(message)
    action = _next_action(row)
    message = f"Selected next session {session['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "next",
            message,
            session=session,
            row=row,
            recommended_action=action,
            command=f"cdx status {session['name']} --refresh" if action == "refresh" else f"cdx {session['name']}",
            reason=format_priority_instruction(row, "first"),
            selection_policy="status_priority",
        ))
        return 0
    ctx["out"](f"{_format_next_selection(session, row, ctx['use_color'])}\n")
    return 0


def _format_launch_configs(sessions, use_color=False):
    from .cli_render import _dim, _style

    if not sessions:
        return "\n".join([
            _style("Launch settings:", "1", use_color),
            "No sessions.",
            "",
            _dim(_format_launch_settings_hint(), use_color),
        ])
    rows = [[_style(value, "1", use_color) for value in [
        "SESSION", "PROVIDER", "POWER", "PERMISSION", "FAST", "RTK", "LOGICS", "MODEL", "PRIORITY"
    ]]]
    for session in sessions:
        launch = session.get("launch") or {}
        rows.append([
            _style(session["name"], "36", use_color),
            _dim(session.get("provider") or "-", use_color),
            _format_launch_setting_value(launch, "power", use_color),
            _format_launch_setting_value(launch, "permission", use_color),
            _format_launch_setting_value(launch, "fast", use_color),
            _format_launch_setting_value(launch, "rtk", use_color),
            _format_launch_setting_value(launch, "logics", use_color),
            _format_launch_setting_value(launch, "model", use_color),
            _format_launch_setting_value(launch, "priority", use_color),
        ])
    return "\n".join([
        _style("Launch settings:", "1", use_color),
        _pad_table(rows),
        "",
        _dim(_format_launch_settings_hint(), use_color),
    ])


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
    if minutes < 60:
        return f"{minutes}m {remaining:02d}s"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours < 24:
        return f"{hours}h {remaining_minutes:02d}m"
    days = hours // 24
    remaining_hours = hours % 24
    return f"{days}d {remaining_hours:02d}h"


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


def _token_value(usage, key):
    if not isinstance(usage, dict):
        return None
    value = usage.get(key)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _summarize_stats(entries):
    rows = {}
    for entry in entries:
        name = entry.get("session_name") or "-"
        row = rows.setdefault(name, {
            "session_name": name,
            "provider": entry.get("provider") or "-",
            "launches": 0,
            "successes": 0,
            "failures": 0,
            "duration_ms": 0,
            "usage_runs": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
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
        usage = entry.get("usage") if isinstance(entry.get("usage"), dict) else {}
        parsed_usage = {
            key: _token_value(usage, key)
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens")
        }
        if any(value is not None for value in parsed_usage.values()):
            row["usage_runs"] += 1
            for key, value in parsed_usage.items():
                row[key] += value or 0
        started = entry.get("started_at")
        if started and (not row["last_started_at"] or started > row["last_started_at"]):
            row["last_started_at"] = started
            row["provider"] = entry.get("provider") or row["provider"]
    return sorted(
        rows.values(),
        key=lambda item: (item["total_tokens"], item["duration_ms"], item.get("last_started_at") or "", item["session_name"]),
        reverse=True,
    )


def _stats_totals(rows):
    return {
        "sessions": len(rows),
        "launches": sum(row["launches"] for row in rows),
        "successes": sum(row["successes"] for row in rows),
        "failures": sum(row["failures"] for row in rows),
        "duration_ms": sum(row["duration_ms"] for row in rows),
        "usage_runs": sum(row["usage_runs"] for row in rows),
        "input_tokens": sum(row["input_tokens"] for row in rows),
        "output_tokens": sum(row["output_tokens"] for row in rows),
        "reasoning_tokens": sum(row["reasoning_tokens"] for row in rows),
        "total_tokens": sum(row["total_tokens"] for row in rows),
    }


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


def _format_history_summary(entries, period=None, use_color=False, active_sessions=None):
    from .cli_render import _format_relative_age

    active_sessions = active_sessions or set()
    summary = _summarize_history(entries)
    if not summary:
        return "No launch history for this period." if _has_history_period(period or {}) else "No launch history."
    rows = [[_style(value, "1", use_color) for value in ["SESSION", "PROV.", "LAUNCHES", "OK", "FAIL", "TIME", "LAST"]]]
    for row in summary:
        session_name = row["session_name"]
        display_name = f"{session_name}*" if session_name in active_sessions else session_name
        rows.append([
            _style(display_name, "36", use_color),
            _dim(row["provider"], use_color),
            _style(str(row["launches"]), "1", use_color),
            _style(str(row["successes"]), "32" if row["successes"] else "2", use_color),
            _style(str(row["failures"]), "31" if row["failures"] else "2", use_color),
            _style(_format_duration_ms(row["duration_ms"]), "33" if row["duration_ms"] else "2", use_color),
            _dim(_format_relative_age(row.get("last_started_at")), use_color),
        ])
    lines = [_style("Assistant time:", "1", use_color)]
    period_line = _format_history_period(period or {})
    if period_line:
        lines.extend([_dim(period_line, use_color), ""])
    lines.append(_pad_table(rows))
    return "\n".join(lines)


def _format_history(entries, use_color=False, active_sessions=None):
    from .cli_render import _format_relative_age

    active_sessions = active_sessions or set()
    if not entries:
        return "No launch history."
    rows = [[_style(value, "1", use_color) for value in ["SESSION", "PROV.", "RESULT", "DURATION", "WHEN", "TRANSCRIPT"]]]
    for entry in entries:
        transcript_path = entry.get("transcript_path")
        session_name = entry.get("session_name") or "-"
        display_name = f"{session_name}*" if session_name in active_sessions else session_name
        status = entry.get("status") or "-"
        status_color = "32" if status == "success" else "31" if status == "failed" else "2"
        rows.append([
            _style(display_name, "36", use_color),
            _dim(entry.get("provider") or "-", use_color),
            _style(status, status_color, use_color),
            _style(_format_duration_ms(entry.get("duration_ms")), "33" if entry.get("duration_ms") else "2", use_color),
            _dim(_format_relative_age(entry.get("started_at")), use_color),
            _dim(os.path.basename(transcript_path) if transcript_path else "-", use_color),
        ])
    return "\n".join([
        _style("Recent launches:", "1", use_color),
        _pad_table(rows),
        "",
        _dim("Full transcript paths and cwd are available with --json.", use_color),
    ])


def _format_token_count(value):
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return "-"
    if amount >= 1000000:
        return f"{amount / 1000000:.1f}M"
    if amount >= 1000:
        return f"{amount / 1000:.1f}K"
    return str(amount)


def _format_stats(rows, totals, period=None, use_color=False, active_sessions=None):
    from .cli_render import _format_relative_age

    active_sessions = active_sessions or set()
    if not rows:
        return "No launch stats for this period." if _has_history_period(period or {}) else "No launch stats."
    table = [[_style(value, "1", use_color) for value in [
        "SESSION", "PROV.", "RUNS", "USAGE", "IN", "OUT", "REASON", "TOTAL", "TIME", "LAST"
    ]]]
    for row in rows:
        session_name = row["session_name"]
        display_name = f"{session_name}*" if session_name in active_sessions else session_name
        table.append([
            _style(display_name, "36", use_color),
            _dim(row["provider"], use_color),
            _style(str(row["launches"]), "1", use_color),
            _style(str(row["usage_runs"]), "32" if row["usage_runs"] else "2", use_color),
            _style(_format_token_count(row["input_tokens"]), "96" if row["input_tokens"] else "2", use_color),
            _style(_format_token_count(row["output_tokens"]), "96" if row["output_tokens"] else "2", use_color),
            _style(_format_token_count(row["reasoning_tokens"]), "95" if row["reasoning_tokens"] else "2", use_color),
            _style(_format_token_count(row["total_tokens"]), "1;96" if row["total_tokens"] else "2", use_color),
            _style(_format_duration_ms(row["duration_ms"]), "33" if row["duration_ms"] else "2", use_color),
            _dim(_format_relative_age(row.get("last_started_at")), use_color),
        ])
    lines = [_style("Assistant stats:", "1", use_color)]
    period_line = _format_history_period(period or {})
    if period_line:
        lines.extend([_dim(period_line, use_color), ""])
    lines.append(_pad_table(table))
    lines.extend([
        "",
        _dim(
            "Totals: "
            f"{totals['launches']} runs, {totals['usage_runs']} with usage, "
            f"{_format_token_count(totals['total_tokens'])} tokens, "
            f"{_format_duration_ms(totals['duration_ms'])}.",
            use_color,
        ),
    ])
    return "\n".join(lines)


def _active_session_names(ctx):
    return {
        row["name"]
        for row in ctx["service"]["format_list_rows"]()
        if row.get("active")
    }


def handle_config(rest, ctx):
    parsed = _parse_config_args(rest)
    session = ctx["service"]["get_session"](parsed["name"])
    if not session:
        raise CdxError(
            f"Unknown session: {parsed['name']}. Run cdx configs to inspect existing sessions or "
            f"cdx add {parsed['name']} to create it."
        )
    message = f"Launch settings for {parsed['name']}"
    if parsed["json"]:
        _write_json(ctx, _json_success("config", message, session=session, launch=session.get("launch") or {}))
        return 0
    ctx["out"](f"{_format_launch_config(session, ctx['use_color'])}\n")
    return 0


def handle_configs(rest, ctx):
    parsed = _parse_configs_args(rest)
    sessions = ctx["service"]["list_sessions"]()
    message = f"Listed launch settings for {len(sessions)} session{'s' if len(sessions) != 1 else ''}"
    if parsed["json"]:
        _write_json(ctx, _json_success("configs", message, count=len(sessions), sessions=sessions))
        return 0
    ctx["out"](f"{_format_launch_configs(sessions, ctx['use_color'])}\n")
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
    active_sessions = _active_session_names(ctx)
    if parsed["summary"]:
        ctx["out"](f"{_format_history_summary(entries, period=parsed['period'], use_color=ctx['use_color'], active_sessions=active_sessions)}\n")
        return 0
    ctx["out"](f"{_format_history(entries, use_color=ctx['use_color'], active_sessions=active_sessions)}\n")
    return 0


def handle_stats(rest, ctx):
    now_fn = ctx["options"].get("now") or time.time
    now = datetime.fromtimestamp(now_fn()).astimezone()
    parsed = _parse_stats_args(rest, now=now)
    entries = ctx["service"]["get_launch_history"](parsed["name"], limit=0)
    entries = _filter_history_period(entries, parsed["period"])
    rows = _summarize_stats(entries)
    totals = _stats_totals(rows)
    message = (
        f"Calculated stats for {parsed['name']}"
        if parsed["name"]
        else "Calculated stats"
    )
    if parsed["json"]:
        _write_json(ctx, _json_success(
            "stats",
            message,
            period=_public_history_period(parsed["period"]),
            stats=rows,
            totals=totals,
        ))
        return 0
    active_sessions = _active_session_names(ctx)
    ctx["out"](f"{_format_stats(rows, totals, period=parsed['period'], use_color=ctx['use_color'], active_sessions=active_sessions)}\n")
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


def handle_status(rest, ctx):
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--small": {"key": "small", "type": "bool", "default": False},
        "-s": {"key": "small", "type": "bool", "default": False},
        "--refresh": {"key": "refresh", "type": "bool", "default": False},
        "--cached": {"key": "cached", "type": "bool", "default": False},
        "--timeout": {"key": "timeout", "type": "str", "default": None, "transform": lambda value: _parse_timeout_seconds(value, STATUS_USAGE)},
    }, STATUS_USAGE, positionals_key="args", max_positionals=1)
    if parsed["json"] and parsed["small"]:
        raise CdxError(STATUS_USAGE)
    if parsed["refresh"] and parsed["cached"]:
        raise CdxError(STATUS_USAGE)
    args = parsed["args"]
    if len(args) == 1 and parsed["small"]:
        raise CdxError(STATUS_USAGE)

    auth_refresh = (
        {"errors": []}
        if parsed["cached"]
        else _refresh_claude_auth_states(
            ctx["service"],
            target_names=args if len(args) == 1 else None,
            spawn_sync=ctx.get("spawn_sync"),
            env_override=ctx.get("env"),
        )
    )
    warnings = [
        {
            "code": "claude_auth_probe_failed",
            "session": item.get("session") or "unknown",
            "message": item.get("error") or "unknown error",
        }
        for item in auth_refresh.get("errors", [])
    ]
    refresh_result = (
        {"errors": []}
        if parsed["cached"]
        else _refresh_claude_sessions(
            ctx["service"],
            ctx.get("refresh_fn"),
            target_names=args if len(args) == 1 else None,
            force=parsed["refresh"],
        )
    )
    refresh_errors = [
        {
            "session": item.get("session"),
            "error": str(item.get("error")),
        }
        for item in refresh_result.get("errors", [])
    ]
    status_progress = None if parsed["json"] else _make_status_progress(ctx)
    if len(args) == 1:
        row = ctx["service"]["get_status_row"](
            args[0],
            progress_callback=status_progress,
            force_refresh=parsed["refresh"],
            cache_only=parsed["cached"],
            status_timeout_seconds=parsed["timeout"],
        )
        output_warnings = [
            *warnings,
            *_refresh_warning_payloads(refresh_errors, [row]),
            *_update_notice_warnings(ctx),
        ]
        if parsed["json"]:
            _write_json(ctx, _json_success("status", f"Collected status for {args[0]}", warnings=output_warnings, session=row))
            return 0
        ctx["out"](f"{_format_status_detail(row, use_color=ctx['use_color'])}\n")
        _write_refresh_warnings(refresh_errors, ctx, rows=[row])
        _write_update_notice(ctx)
        return 0

    rows = ctx["service"]["get_status_rows"](
        progress_callback=status_progress,
        force_refresh=parsed["refresh"],
        cache_only=parsed["cached"],
        status_timeout_seconds=parsed["timeout"],
    )
    output_warnings = [
        *warnings,
        *_refresh_warning_payloads(refresh_errors, rows),
        *_update_notice_warnings(ctx),
    ]
    if parsed["json"]:
        _write_json(ctx, _json_success("status", "Collected session status rows", warnings=output_warnings, rows=rows))
        return 0
    ctx["out"](f"{_format_status_rows(rows, use_color=ctx['use_color'], small=parsed['small'])}\n")
    _write_refresh_warnings(refresh_errors, ctx, rows=rows)
    _write_update_notice(ctx)
    return 0


def handle_reset(rest, ctx):
    parsed = _parse_flag_args(rest, {
        "--json": {"key": "json", "type": "bool", "default": False},
        "--yes": {"key": "yes", "type": "bool", "default": False},
    }, "Usage: cdx reset <name> [--yes] [--json]", positionals_key="args", max_positionals=1)
    if len(parsed["args"]) != 1:
        raise CdxError("Usage: cdx reset <name> [--yes] [--json]")
    name = parsed["args"][0]
    session = ctx["service"]["get_session"](name)
    if not session:
        raise CdxError(f"Unknown session: {name}")
    if session["provider"] != PROVIDER_CODEX:
        raise CdxError("Banked rate-limit resets are only available for Codex sessions.")

    status = ctx["service"]["get_status_row"](name, force_refresh=True)
    if status.get("reset_credits_available") == 0:
        raise CdxError(f"No banked Codex reset is available for {name}.")
    if not parsed["yes"]:
        confirm_fn = ctx["options"].get("confirmReset")
        if confirm_fn:
            confirmed = _resolve_confirmation(confirm_fn, name)
        elif not ctx["stdin_is_tty"]:
            raise CdxError("Reset activation requires an interactive terminal or --yes in non-interactive mode.")
        else:
            confirmed = _confirm_reset(name)
        if not confirmed:
            if parsed["json"]:
                _write_json(ctx, _json_success("reset", "Cancelled.", cancelled=True, session=name))
                return 0
            ctx["out"](f"{_warn('Cancelled.', ctx['use_color'])}\n")
            return 0

    credit_rows = status.get("reset_credits") or []
    credit_id = credit_rows[0].get("id") if credit_rows else None
    consumer = ctx["options"].get("consumeCodexReset") or consume_codex_rate_limit_reset_credit
    result = consumer(
        session,
        ctx["options"].get("resetIdempotencyKey") or str(uuid.uuid4()),
        credit_id=credit_id,
    )
    if not result.get("ok"):
        if result.get("reason") == "reset_consume_failed":
            raise CdxError(
                f"Unable to activate Codex reset for {name}. "
                "The installed Codex version or account may not support reset activation."
            )
        raise CdxError(f"Unable to activate Codex reset for {name}: {result.get('reason') or 'unknown error'}")
    outcome = result.get("outcome")
    if outcome == "noCredit":
        raise CdxError(f"No banked Codex reset is available for {name}.")
    if outcome == "nothingToReset":
        raise CdxError(f"No current Codex rate-limit window is eligible for reset on {name}.")
    if outcome not in ("reset", "alreadyRedeemed"):
        raise CdxError(f"Unexpected Codex reset outcome for {name}: {outcome or 'missing'}")
    refreshed = ctx["service"]["get_status_row"](name, force_refresh=True)
    message = f"Activated banked Codex reset for {name}"
    if parsed["json"]:
        _write_json(ctx, _json_success("reset", message, cancelled=False, outcome=outcome, session=refreshed))
        return 0
    ctx["out"](f"{_success(message, ctx['use_color'])}\n")
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
            auth_status = _probe_provider_auth_status(
                session,
                spawn_sync=spawn_sync,
                env_override=env_override,
            )
            if auth_status == AUTH_PROBE_DEGRADED:
                errors.append({
                    "session": session["name"],
                    "error": "Auth probe timed out; authentication status is degraded.",
                })
                continue
            now = _local_now_iso()
            service["update_auth_state"](session["name"], lambda auth, auth_status=auth_status, now=now: {
                **auth,
                "status": "authenticated" if auth_status == AUTH_PROBE_AUTHENTICATED else "logged_out",
                "lastCheckedAt": now,
                **({"lastAuthenticatedAt": now} if auth_status == AUTH_PROBE_AUTHENTICATED else {}),
            })
            updated.append(session["name"])
        except Exception as error:
            errors.append({"session": session["name"], "error": str(error)})
    return {"updated": updated, "errors": errors}


def _rows_by_session(rows):
    return {
        row.get("session_name"): row
        for row in (rows or [])
        if row.get("session_name")
    }


def _is_invalid_claude_usage_auth(error):
    text = str(error or "").lower()
    return "http 401" in text and "invalid authentication credentials" in text


def _has_valid_local_claude_auth(item, rows_by_name):
    session = item.get("session")
    row = rows_by_name.get(session)
    return bool(row and row.get("provider") == PROVIDER_CLAUDE and row.get("auth_status") == "authenticated")


def _refresh_warning_payloads(refresh_errors, rows=None):
    rows_by_name = _rows_by_session(rows)
    warnings = []
    for item in refresh_errors:
        session = item.get("session") or "unknown"
        error = item.get("error") or "unknown error"
        warning = {
            "code": "claude_refresh_failed",
            "session": session,
            "message": error,
        }
        if _is_invalid_claude_usage_auth(error) and _has_valid_local_claude_auth(item, rows_by_name):
            warning.update({
                "auth_status": "authenticated",
                "status_freshness": "stale",
                "message": (
                    "Claude quota refresh failed, but local Claude auth is still valid; "
                    f"cached quota may be stale. Original error: {error}"
                ),
            })
        warnings.append(warning)
    return warnings


def _format_refresh_warning(item, rows_by_name):
    session = item.get("session") or "unknown"
    error = item.get("error") or "unknown error"
    if _is_invalid_claude_usage_auth(error) and _has_valid_local_claude_auth(item, rows_by_name):
        return (
            f"Warning: Claude quota refresh failed for {session}, but local auth is still valid; "
            f"cached quota may be stale. ({error})"
        )
    return f"Warning: Claude refresh failed for {session}: {error}"


def _write_refresh_warnings(refresh_errors, ctx, stream="out", rows=None):
    write = ctx["err"] if stream == "err" and "err" in ctx else ctx["out"]
    rows_by_name = _rows_by_session(rows)
    for item in refresh_errors:
        write(f"{_warn(_format_refresh_warning(item, rows_by_name), ctx['use_color'])}\n")


def handle_login(rest, ctx):
    rest = [arg for arg in rest if arg != "--setup-token"]  # accepted for back-compat; setup-token is now the default for Claude
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError("Usage: cdx login <name> [--json]")
    if not ctx["stdin_is_tty"]:
        raise CdxError("Login requires an interactive terminal.")
    session = ctx["service"]["get_session"](args[0])
    if not session:
        raise CdxError(f"Unknown session: {args[0]}")
    if session["provider"] == PROVIDER_CLAUDE:
        # ponytail: setup-token mints a ~1yr token; claude login mints a ~daily one that forces reconnects
        _bootstrap_claude_setup_token(session, ctx)
    else:
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
        trust_local_credentials=False,
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


def _format_resume_capability(capability, use_color=False):
    name = capability["session"]
    provider = capability["provider"]
    if capability["resumable"]:
        preview = shlex.join(capability.get("command_preview") or [])
        detail = f"({provider}, {capability['strategy']})"
        return (
            f"{_success(f'{name} can resume', use_color)} "
            f"{_dim(detail, use_color)}\n"
            f"{_dim(preview, use_color)}"
        )
    reason = capability.get("reason") or "not_supported"
    return (
        f"{_warn(f'{name} cannot resume', use_color)} "
        f"{_dim(f'({provider}, {reason})', use_color)}"
    )


def handle_can_resume(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError(CAN_RESUME_USAGE)
    session = ctx["service"]["get_session"](args[0])
    if not session:
        raise CdxError(f"Unknown session: {args[0]}")
    if session.get("enabled", True) is False:
        capability = {
            "session": session["name"],
            "provider": session["provider"],
            "resumable": False,
            "strategy": "session_disabled",
            "reason": "session_disabled",
            "command_preview": [],
        }
    else:
        capability = _resume_capability_for_session(session, ctx)
    if json_flag:
        _write_json(ctx, {
            "schema_version": API_SCHEMA_VERSION,
            "ok": True,
            **capability,
        })
        return 0
    ctx["out"](f"{_format_resume_capability(capability, ctx['use_color'])}\n")
    return 0


def handle_resume(rest, ctx):
    json_flag, args = _parse_json_flag(rest)
    if len(args) != 1:
        raise CdxError(RESUME_USAGE)
    return handle_launch(args[0], ctx, resume=True, force_json=json_flag)


def handle_launch(command, ctx, initial_prompt=None, resume=False, force_json=None):
    json_flag = "--json" in ctx.get("raw_args", ctx["options"].get("raw_args", []))
    if force_json is not None:
        json_flag = force_json
    warnings = _update_notice_warnings(ctx)
    _warn_if_session_already_running(command, ctx)
    session = ctx["service"]["launch_session"](command)
    capability = _resume_capability_for_session(session, ctx) if resume else None
    if capability and not capability["resumable"]:
        raise CdxError(
            f"Provider {session['provider']} does not support native resume through cdx."
        )
    _ensure_session_authentication(
        session,
        ctx["service"],
        spawn=ctx.get("spawn"),
        spawn_sync=ctx.get("spawn_sync"),
        env_override=ctx.get("env"),
        stdin_is_tty=ctx["stdin_is_tty"],
        behavior="launch",
        signal_emitter=ctx.get("signal_emitter"),
        trust_local_credentials=False,
    )
    message = (
        f"Resuming {session['provider']} session {session['name']}"
        if resume else
        f"Launching {session['provider']} session {session['name']}"
    )
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
            session, "resume" if resume else "launch", spawn=ctx.get("spawn"), cwd=cwd, env_override=ctx.get("env"),
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
        "action": "resume" if resume else "launch",
        "cwd": cwd,
        "exit_code": 0,
        **run_info,
    })
    if json_flag:
        extra = {"session": ctx["service"]["get_session"](session["name"])}
        if capability:
            extra["resume"] = capability
        _write_json(ctx, _json_success("resume" if resume else "launch", message, warnings=warnings, **extra))
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
