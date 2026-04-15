from datetime import datetime

from .cli_render import (
    _dim,
    _format_pct,
    _format_relative_age,
    _pad_table,
    _style,
    _style_pct,
)


def _format_reset_time(value):
    if not value:
        return "-"
    timestamp = _parse_reset_timestamp(value)
    if timestamp is None:
        return value
    delta_s = timestamp - _now_timestamp()
    if delta_s < 0:
        minutes_ago = int(abs(delta_s) // 60)
        if minutes_ago < 1:
            return "passed"
        if minutes_ago < 60:
            return f"passed {minutes_ago}m ago"
        hours_ago = minutes_ago // 60
        if hours_ago < 24:
            return f"passed {hours_ago}h ago"
        return value
    if delta_s < 60:
        return "now"
    if delta_s < 24 * 60 * 60:
        minutes = int(delta_s // 60)
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if hours == 0:
            return f"in {remaining_minutes}m"
        if remaining_minutes == 0:
            return f"in {hours}h"
        return f"in {hours}h {remaining_minutes}m"
    return value


def _style_reset_time(value, use_color=False):
    text = _format_reset_time(value)
    if text == "-":
        return _style(text, "2", use_color)
    if text == "now" or text.startswith("in "):
        return _style(text, "32", use_color)
    if text == "passed" or text.startswith("passed "):
        return _style(text, "31", use_color)
    return text


def _format_status_rows(rows, use_color=False, small=False):
    has_provider = len({r["provider"] for r in rows}) > 1 and not small
    if small:
        headers = ["SESSION", "OK", "5H", "WEEK", "RESET 5H", "RESET WEEK"]
    elif has_provider:
        headers = ["SESSION", "PROV.", "OK", "5H", "WEEK", "BLOCK", "CR", "RESET 5H", "RESET WEEK", "UPDATED"]
    else:
        headers = ["SESSION", "OK", "5H", "WEEK", "BLOCK", "CR", "RESET 5H", "RESET WEEK", "UPDATED"]
    if not rows:
        if small:
            return "SESSION  OK  5H  WEEK  RESET 5H  RESET WEEK\nNo saved sessions yet."
        return "SESSION  OK  5H  WEEK  BLOCK  CR  RESET 5H  RESET WEEK  UPDATED\nNo saved sessions yet."
    headers = [_style(header, "1", use_color) for header in headers]
    priority = _recommend_priority_sessions(rows)
    table_rows = []
    for r in priority:
        base = [r["session_name"]]
        if has_provider:
            base.append(r.get("provider") or "n/a")
        usage_columns = [
            _style_pct(r.get("available_pct"), use_color),
            _style_pct(r.get("remaining_5h_pct"), use_color),
            _style_pct(r.get("remaining_week_pct"), use_color),
            _style_reset_time(r.get("reset_5h_at"), use_color),
            _style_reset_time(r.get("reset_week_at"), use_color),
        ]
        if small:
            base += usage_columns
        else:
            block = _format_blocking_quota(r)
            credits = str(r["credits"]) if r.get("credits") is not None else "-"
            base += usage_columns[:3] + [
                _style(block, "33" if block not in ("?", "-") else "2", use_color),
                _style(credits, "33" if r.get("credits") is not None else "2", use_color),
                *usage_columns[3:],
                _style(_format_relative_age(r.get("updated_at")), "2", use_color),
            ]
        table_rows.append(base)
    priority_line = (
        f"Priority: {_priority_instruction(priority[0], 'first')}"
        + (
            f", {_priority_instruction(priority[1], 'next')}."
            if len(priority) > 1 else "."
        )
    ) if priority else "Priority: no usable session status yet."
    return "\n".join([
        _pad_table([headers] + table_rows),
        "",
        _style(priority_line, "1", use_color),
        _style("Tip: run /status in codex to refresh. Claude sessions refresh automatically.", "2", use_color),
    ])


def _recommend_priority_sessions(rows):
    if not rows:
        return []

    def rank(row):
        has_credits = row.get("credits") is not None
        credit_rank = 0 if has_credits else 1
        available = row.get("available_pct")
        usable_now = available is not None and available > 0
        known_available = available is not None
        reset_timestamp = _priority_reset_timestamp(row)
        reset_is_future = reset_timestamp is not None and reset_timestamp >= _now_timestamp()
        blocked_future = not usable_now and reset_is_future
        reset_is_known = reset_timestamp is not None
        reset_rank = -reset_timestamp if reset_is_known else float("-inf")
        available_rank = available if available is not None else -1
        name_rank = row.get("session_name") or ""
        if usable_now:
            return (3, credit_rank, 1 if known_available else 0, available_rank, reset_rank, name_rank)
        if blocked_future:
            return (2, 1 if reset_is_known else 0, reset_rank, credit_rank, available_rank, name_rank)
        if reset_is_known:
            return (1, reset_rank, credit_rank, 1 if known_available else 0, available_rank, name_rank)
        return (0, credit_rank, 1 if known_available else 0, available_rank, name_rank)

    return sorted(rows, key=rank, reverse=True)


def _format_blocking_quota(row):
    remaining_5h = row.get("remaining_5h_pct")
    remaining_week = row.get("remaining_week_pct")
    if remaining_5h is None and remaining_week is None:
        return "?"
    if remaining_5h is None:
        return "WEEK"
    if remaining_week is None:
        return "5H"
    if remaining_5h < remaining_week:
        return "5H"
    if remaining_week < remaining_5h:
        return "WEEK"
    return "5H+WEEK"


def _priority_instruction(row, position):
    action = "refresh" if _priority_needs_refresh(row) else "use"
    if position == "next" and action == "use":
        return f"next {row['session_name']} ({_priority_reason(row)})"
    return f"{action} {row['session_name']} {position} ({_priority_reason(row)})"


def _priority_needs_refresh(row):
    available = row.get("available_pct")
    if available is None or available > 0:
        return False
    _label, is_past = _priority_reset_info(row)
    return is_past


def _priority_reason(row):
    available = row.get("available_pct")
    if available is None:
        return "status unknown"
    if available > 0:
        return f"{_format_pct(available)} OK"
    label, is_past = _priority_reset_info(row)
    if label:
        if is_past:
            return f"0% OK, {label} reset passed"
        return f"0% OK, {label} resets first"
    return "0% OK"


def _priority_reset_info(row):
    remaining_5h = row.get("remaining_5h_pct")
    remaining_week = row.get("remaining_week_pct")
    candidates = []
    if remaining_5h is not None:
        candidates.append((remaining_5h, "5H", row.get("reset_5h_at")))
    if remaining_week is not None:
        candidates.append((remaining_week, "WEEK", row.get("reset_week_at")))
    if not candidates:
        return None
    lowest_remaining = min(value for value, _label, _reset in candidates)
    blocked = [
        (label, reset)
        for value, label, reset in candidates
        if value == lowest_remaining and reset
    ]
    timestamps = [
        (timestamp, label)
        for label, reset in blocked
        for timestamp in [_parse_reset_timestamp(reset)]
        if timestamp is not None
    ]
    if timestamps:
        timestamp, label = min(timestamps)
        return label, timestamp < _now_timestamp()
    if blocked:
        return blocked[0][0], False
    return None, False


def _priority_reset_timestamp(row):
    remaining_5h = row.get("remaining_5h_pct")
    remaining_week = row.get("remaining_week_pct")
    candidates = []
    if remaining_5h is not None:
        candidates.append((remaining_5h, row.get("reset_5h_at")))
    if remaining_week is not None:
        candidates.append((remaining_week, row.get("reset_week_at")))
    if not candidates:
        return None
    lowest_remaining = min(value for value, _reset in candidates)
    reset_values = [_reset for value, _reset in candidates if value == lowest_remaining]
    timestamps = [
        timestamp
        for timestamp in (_parse_reset_timestamp(reset_value) for reset_value in reset_values)
        if timestamp is not None
    ]
    if not timestamps:
        return None
    return min(timestamps)


def _parse_reset_timestamp(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return parsed.timestamp()
    except (TypeError, ValueError):
        pass
    try:
        parsed = datetime.strptime(text, "%b %d %H:%M")
    except (TypeError, ValueError):
        return None
    now = datetime.now().astimezone()
    parsed = parsed.replace(year=now.year, tzinfo=now.tzinfo)
    return parsed.timestamp()


def _now_timestamp():
    return datetime.now().astimezone().timestamp()


def _format_status_detail(row, use_color=False):
    lines = [
        f"{_style('Session:', '1', use_color)} {row['session_name']}",
        f"{_style('Provider:', '1', use_color)} {row.get('provider') or 'n/a'}",
        f"{_style('Available:', '1', use_color)} {_style_pct(row.get('available_pct'), use_color)}",
        f"{_style('5h left:', '1', use_color)} {_style_pct(row.get('remaining_5h_pct'), use_color)}",
        f"{_style('Week left:', '1', use_color)} {_style_pct(row.get('remaining_week_pct'), use_color)}",
        f"{_style('Block:', '1', use_color)} {_style(_format_blocking_quota(row), '33', use_color)}",
        f"{_style('Credits:', '1', use_color)} {_style(row['credits'] if row.get('credits') is not None else 'n/a', '33' if row.get('credits') is not None else '2', use_color)}",
        f"{_style('5h reset:', '1', use_color)} {_style_reset_time(row.get('reset_5h_at'), use_color)}",
        f"{_style('Week reset:', '1', use_color)} {_style_reset_time(row.get('reset_week_at'), use_color)}",
        f"{_style('Updated:', '1', use_color)} {_dim(_format_relative_age(row.get('updated_at')), use_color)}",
    ]
    return "\n".join(lines)
