"""Status domain commands: status, next, config, configs, last, history, stats.

Split out of cli_commands.py. Moved verbatim; re-exported by cli_commands.
"""

import os
import threading
import time
from datetime import datetime

from ..claude_refresh import _refresh_claude_sessions
from ..cli_args import (
    LAST_USAGE,
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
from ..cli_helpers import (
    _format_launch_config,
    _format_launch_setting_value,
    _format_launch_settings_hint,
    _json_failure,
    _json_success,
    _local_now_iso,
    _make_status_progress,
    _update_notice_warnings,
    _write_json,
    _write_update_notice,
)
from ..cli_hints import write_hint
from ..cli_render import _dim, _info, _pad_table, _style, _warn
from ..commands.launch import handle_launch
from ..config import PROVIDER_CLAUDE
from ..errors import CdxError
from ..provider_runtime import (
    AUTH_PROBE_AUTHENTICATED,
    AUTH_PROBE_DEGRADED,
    AUTH_PROBE_TIMEOUT_SECONDS,
    _probe_provider_auth_status,
)
from ..run_usage import (
    USAGE_KEYS,
    estimate_cost,
    is_vouched,
    normalize_usage,
    token_prices,
    weighted_usage,
)
from ..status_view import _format_status_detail, _format_status_rows, format_priority_instruction, recommend_priority_rows


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
    from ..cli_render import _dim, _style

    if not sessions:
        return "\n".join([
            _style("Launch settings:", "1", use_color),
            "No sessions.",
            "",
            _dim(_format_launch_settings_hint(), use_color),
        ])
    # The table is already nine columns wide, so the two headless-only settings
    # follow the LABEL convention from the session list: shown once somebody
    # uses them, absent otherwise.
    has_headless = any(
        (session.get("launch") or {}).get(key) is not None
        for session in sessions
        for key in ("fallback_model", "budget")
    )
    has_extra = any((session.get("launch") or {}).get("extra_args") for session in sessions)
    headers = ["SESSION", "PROVIDER", "POWER", "PERMISSION", "FAST", "RTK", "LOGICS", "ALERTS", "MODEL"]
    if has_headless:
        headers += ["FALLBACK", "BUDGET"]
    if has_extra:
        headers.append("EXTRA ARGS")
    headers.append("PRIORITY")
    rows = [[_style(value, "1", use_color) for value in headers]]
    for session in sessions:
        launch = session.get("launch") or {}
        row = [
            _style(session["name"], "36", use_color),
            _dim(session.get("provider") or "-", use_color),
            _format_launch_setting_value(launch, "power", use_color),
            _format_launch_setting_value(launch, "permission", use_color),
            _format_launch_setting_value(launch, "fast", use_color),
            _format_launch_setting_value(launch, "rtk", use_color),
            _format_launch_setting_value(launch, "logics", use_color),
            _format_launch_setting_value(launch, "notify", use_color),
            _format_launch_setting_value(launch, "model", use_color),
        ]
        if has_headless:
            row.append(_format_launch_setting_value(launch, "fallback_model", use_color))
            row.append(_format_launch_setting_value(launch, "budget", use_color))
        if has_extra:
            row.append(_format_launch_setting_value(launch, "extra_args", use_color))
        row.append(_format_launch_setting_value(launch, "priority", use_color))
        rows.append(row)
    lines = [
        _style("Launch settings:", "1", use_color),
        _pad_table(rows),
        "",
    ]
    if has_headless:
        lines.append(_dim(
            "FALLBACK and BUDGET apply to headless Claude runs only "
            "(cdx run); the provider accepts them with --print alone.",
            use_color,
        ))
    if has_extra:
        lines.append(_dim(
            "EXTRA ARGS are passed to the provider unchanged and unvalidated. "
            "cdx does not check them, and cdx schema does not describe them.",
            use_color,
        ))
    lines.append(_dim(_format_launch_settings_hint(), use_color))
    return "\n".join(lines)

def _format_usd(amount):
    if not amount:
        return "-"
    return f"${amount:,.2f}" if amount >= 0.01 else "<$0.01"


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
            "cost_usd": 0.0,
            "weighted_tokens": 0,
            "priced_runs": 0,
            "unpriced_models": set(),
            "unvouched_runs": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
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
        if usage and not is_vouched(usage):
            # Written before the definition existed, so the figures are
            # fictitious rather than merely old. Excluded from every total and
            # counted, so the exclusion is visible instead of silent.
            row["unvouched_runs"] += 1
            usage = {}
        parsed_usage = {
            key: _token_value(usage, key)
            for key in USAGE_KEYS
        }
        if any(value is not None for value in parsed_usage.values()):
            row["usage_runs"] += 1
            for key, value in parsed_usage.items():
                row[key] += value or 0
            # Priced per run, against the model that served it. A run whose
            # model cdx never saw stays unpriced rather than being charged at a
            # default tier, and `priced_runs` says how much of the figure is
            # actually covered.
            # Weighted per entry, not on the summed row: the output ratio is
            # the one multiplier that differs between vendors, and a session's
            # runs can span models.
            row["weighted_tokens"] += weighted_usage(
                entry.get("usage"), entry.get("usage_model")) or 0
            cost = estimate_cost(entry.get("usage"), entry.get("usage_model"))
            if cost is not None:
                row["cost_usd"] += cost
                row["priced_runs"] += 1
            elif entry.get("usage_model"):
                # Named the model but could not price it. Recording which one
                # turns an unexplained "-" into something actionable: that
                # string is exactly what CDX_TOKEN_PRICES needs a key for.
                row["unpriced_models"].add(entry["usage_model"])
        started = entry.get("started_at")
        if started and (not row["last_started_at"] or started > row["last_started_at"]):
            row["last_started_at"] = started
            row["provider"] = entry.get("provider") or row["provider"]
    for row in rows.values():
        # Derive from the summed parts rather than summing each run's stored
        # total. Records written before the definition was settled carry a
        # total that excluded cache, and adding those to correct ones produced
        # a row that contradicted itself -- CACHE in the hundreds of millions
        # beside a TOTAL in the low millions.
        #
        # Those records also lack the creation/read split, so the fused
        # `cached_input_tokens` is the one field both eras share. Where the
        # split is missing it is read as cache read: that is what the
        # overwhelming majority of cached tokens are, and weighting the whole
        # of it at the creation rate would overstate legacy sessions by more
        # than reading it as reads understates them.
        split = row["cache_creation_tokens"] + row["cache_read_tokens"]
        legacy_cache = max(0, row["cached_input_tokens"] - split)
        derived = normalize_usage(
            input_tokens=row["input_tokens"],
            cache_creation_tokens=row["cache_creation_tokens"],
            cache_read_tokens=row["cache_read_tokens"] + legacy_cache,
            output_tokens=row["output_tokens"],
        )
        row["total_tokens"] = derived["total_tokens"] or 0
        if not row["weighted_tokens"]:
            # Records written before the model was recorded: weigh the row as a
            # whole, at the default ratio, rather than reporting nothing.
            row["weighted_tokens"] = weighted_usage(derived) or 0
        row["unpriced_models"] = sorted(row["unpriced_models"])
    for row in rows.values():
        # Derive from the summed parts rather than summing each run's stored
        # total. Records written before the definition was settled carry a
        # total that excluded cache, and adding those to correct ones produced
        # a row that contradicted itself -- CACHE in the hundreds of millions
        # beside a TOTAL in the low millions.
        #
        # Those records also lack the creation/read split, so the fused
        # `cached_input_tokens` is the one field both eras share. Where the
        # split is missing it is read as cache read: that is what the
        # overwhelming majority of cached tokens are, and weighting the whole
        # of it at the creation rate would overstate legacy sessions by more
        # than reading it as reads understates them.
        split = row["cache_creation_tokens"] + row["cache_read_tokens"]
        legacy_cache = max(0, row["cached_input_tokens"] - split)
        derived = normalize_usage(
            input_tokens=row["input_tokens"],
            cache_creation_tokens=row["cache_creation_tokens"],
            cache_read_tokens=row["cache_read_tokens"] + legacy_cache,
            output_tokens=row["output_tokens"],
        )
        row["total_tokens"] = derived["total_tokens"] or 0
        if not row["weighted_tokens"]:
            # Records written before the model was recorded: weigh the row as a
            # whole, at the default ratio, rather than reporting nothing.
            row["weighted_tokens"] = weighted_usage(derived) or 0
        row["unpriced_models"] = sorted(row["unpriced_models"])
    return sorted(
        rows.values(),
        # Ranked by what a session cost, not by how many tokens it moved: a
        # cache read is 0.1x an uncached input token and an output token is 5x,
        # so a raw total sorts a cache-heavy session above one that spent far
        # more on generation.
        key=lambda item: (item["weighted_tokens"], item["duration_ms"], item.get("last_started_at") or "", item["session_name"]),
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
        **{key: sum(row[key] for row in rows) for key in USAGE_KEYS},
        "weighted_tokens": sum(row["weighted_tokens"] for row in rows),
        "cost_usd": sum(row["cost_usd"] for row in rows),
        "priced_runs": sum(row["priced_runs"] for row in rows),
        "unpriced_models": sorted({m for row in rows for m in row["unpriced_models"]}),
        "unvouched_runs": sum(row["unvouched_runs"] for row in rows),
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
    from ..cli_render import _format_relative_age

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
    from ..cli_render import _format_relative_age

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
    from ..cli_render import _format_relative_age

    active_sessions = active_sessions or set()
    if not rows:
        return "No launch stats for this period." if _has_history_period(period or {}) else "No launch stats."
    table = [[_style(value, "1", use_color) for value in [
        "SESSION", "PROV.", "RUNS", "USAGE", "IN", "CACHE", "OUT", "REASON", "TOTAL", "COST~", "USD~", "TIME", "LAST"
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
            _style(_format_token_count(row["cached_input_tokens"]), "96" if row["cached_input_tokens"] else "2", use_color),
            _style(_format_token_count(row["output_tokens"]), "96" if row["output_tokens"] else "2", use_color),
            _style(_format_token_count(row["reasoning_tokens"]), "95" if row["reasoning_tokens"] else "2", use_color),
            _style(_format_token_count(row["total_tokens"]), "96" if row["total_tokens"] else "2", use_color),
            _style(_format_token_count(row["weighted_tokens"]), "1;95" if row["weighted_tokens"] else "2", use_color),
            _style(_format_usd(row["cost_usd"]) if row["priced_runs"] else "-",
                   "1;33" if row["priced_runs"] else "2", use_color),
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
            f"{_format_token_count(totals['total_tokens'])} tokens "
            f"({_format_token_count(totals['weighted_tokens'])} cost-equivalent"
            + (f", {_format_usd(totals['cost_usd'])} at list on {totals['priced_runs']} priced run"
               f"{'s' if totals['priced_runs'] != 1 else ''} [{token_prices()[1]}]"
               if totals["priced_runs"] else ", no run priced")
            + (f"; no price for {', '.join(totals['unpriced_models'])}"
               if totals["unpriced_models"] else "") + "), "
            + (f"{totals['unvouched_runs']} run"
               f"{'s' if totals['unvouched_runs'] != 1 else ''} excluded "
               f"(recorded before cdx could measure them; cdx repair clears these), "
               if totals["unvouched_runs"] else "")
            + f"{_format_duration_ms(totals['duration_ms'])}.",
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
        write_hint(ctx)
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
    write_hint(ctx)
    return 0

def _refresh_claude_auth_states(service, target_names=None, spawn_sync=None, env_override=None):
    target_names = set(target_names or [])
    candidates = [
        session for session in service["list_sessions"]()
        if session["provider"] == PROVIDER_CLAUDE
        and session.get("enabled", True) is not False
        and (not target_names or session["name"] in target_names)
        and (session.get("auth") or {}).get("status") in ("authenticated", "logged_out")
    ]
    if not candidates:
        return {"updated": [], "errors": []}

    errors = []
    results = {}
    threads = []

    # The probe itself is the slow part (a subprocess spawn per session on a
    # cache miss); it doesn't touch shared state, so it's safe to run
    # concurrently, same as the sibling Claude usage refresh right after this
    # call. Side effects (service["update_auth_state"]) still run serially,
    # after every thread has joined.
    def probe(session):
        try:
            results[session["name"]] = _probe_provider_auth_status(
                session,
                spawn_sync=spawn_sync,
                env_override=env_override,
            )
        except Exception as error:
            errors.append({"session": session["name"], "error": str(error)})

    for session in candidates:
        t = threading.Thread(target=probe, args=(session,), daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join(timeout=AUTH_PROBE_TIMEOUT_SECONDS + 1)

    results = dict(results)
    errors = list(errors)

    updated = []
    now = _local_now_iso()
    for session in candidates:
        auth_status = results.get(session["name"])
        if auth_status is None:
            continue
        if auth_status == AUTH_PROBE_DEGRADED:
            errors.append({
                "session": session["name"],
                "error": "Auth probe timed out; authentication status is degraded.",
            })
            continue
        service["update_auth_state"](session["name"], lambda auth, auth_status=auth_status, now=now: {
            **auth,
            "status": "authenticated" if auth_status == AUTH_PROBE_AUTHENTICATED else "logged_out",
            "lastCheckedAt": now,
            **({"lastAuthenticatedAt": now} if auth_status == AUTH_PROBE_AUTHENTICATED else {}),
        })
        updated.append(session["name"])
    return {"updated": updated, "errors": errors}

def _rows_by_session(rows):
    return {
        row.get("session_name"): row
        for row in (rows or [])
        if row.get("session_name")
    }

def _is_invalid_claude_usage_auth(error):
    text = str(error or "").lower()
    if "http 401" not in text:
        return False
    return "invalid authentication credentials" in text or "oauth access token has expired" in text

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
