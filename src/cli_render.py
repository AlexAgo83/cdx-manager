import os
import re
import sys
from datetime import datetime, timezone

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _format_relative_age(iso_value):
    if not iso_value:
        return "-"
    try:
        ts = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
        delta_s = (datetime.now(timezone.utc) - ts).total_seconds()
    except (ValueError, TypeError):
        return "-"
    if delta_s < 0:
        return "just now"
    minutes = int(delta_s // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def _format_pct(value):
    if value is None:
        return "n/a"
    return f"{value}%"


def _visible_len(value):
    return len(ANSI_RE.sub("", str(value)))


def _pad_table(columns):
    widths = [
        max(_visible_len(row[i]) for row in columns)
        for i in range(len(columns[0]))
    ]
    lines = []
    for row in columns:
        cells = []
        for i in range(len(row)):
            value = str(row[i])
            cells.append(value + " " * (widths[i] - _visible_len(value)))
        lines.append("  ".join(cells))
    return "\n".join(lines)


def _should_use_color(env, stdout):
    if env.get("NO_COLOR") is not None:
        return False
    if env.get("CLICOLOR_FORCE") not in (None, "", "0"):
        return True
    if env.get("CLICOLOR") == "0":
        return False
    if env.get("TERM") == "dumb":
        return False
    return bool(hasattr(stdout, "isatty") and stdout.isatty())


def _style(text, code, use_color=False):
    if not use_color:
        return str(text)
    return f"\033[{code}m{text}\033[0m"


def _style_pct(value, use_color=False):
    text = _format_pct(value)
    if value is None:
        return _style(text, "2", use_color)
    if value <= 0:
        return _style(text, "31", use_color)
    if value <= 10:
        return _style(text, "33", use_color)
    if value > 80:
        return _style(text, "96", use_color)
    return _style(text, "32", use_color)


def _success(text, use_color=False):
    return _style(text, "32", use_color)


def _warn(text, use_color=False):
    return _style(text, "33", use_color)


def _info(text, use_color=False):
    return _style(text, "36", use_color)


def _dim(text, use_color=False):
    return _style(text, "2", use_color)


def _format_launch_text(launch):
    if not launch:
        return "default"
    parts = []
    if launch.get("power"):
        parts.append(launch["power"])
    if launch.get("permission"):
        parts.append(launch["permission"])
    if launch.get("fast") is True:
        parts.append("fast-on")
    if launch.get("logics") is True:
        parts.append("logics-on")
    elif launch.get("logics") is False:
        parts.append("logics-off")
    return "/".join(parts) or "default"


def format_error(error, env=None, stderr=None):
    return _style(str(error), "31", _should_use_color(env or os.environ, stderr or sys.stderr))


def _format_onboarding(use_color=False):
    return "\n".join([
        _style("No sessions yet.", "1", use_color),
        "",
        "A session is an isolated account profile for a provider CLI.",
        "Register your first one, then launch it by name:",
        "",
        f"  {_style('cdx add codex work', '36', use_color)}     {_dim('register a Codex session named work', use_color)}",
        f"  {_style('cdx work', '36', use_color)}               {_dim('log in if needed, then launch it', use_color)}",
        "",
        f"{_dim('Providers: codex, claude, antigravity, ollama (ollama needs --model).', use_color)}",
        f"{_dim('Run cdx help for the full command list.', use_color)}",
    ])


def _format_sessions(service, use_color=False):
    rows = service["format_list_rows"]()
    if not rows:
        return _format_onboarding(use_color=use_color)
    has_provider = any(r.get("provider") for r in rows)
    has_label = any(r.get("label") for r in rows)
    has_launch = any(r.get("launch") for r in rows)
    headers = ["SESSION"]
    if has_provider:
        headers.append("PROVIDER")
    if has_label:
        headers.append("LABEL")
    headers.append("STATUS")
    if has_launch:
        headers.append("LAUNCH")
    headers.append("UPDATED")
    headers = [_style(header, "1", use_color) for header in headers]
    table_rows = []
    for r in rows:
        name = f"{r['name']}*" if r.get("active") else r["name"]
        parts = [name]
        if has_provider:
            parts.append(r.get("provider") or "n/a")
        if has_label:
            parts.append(r.get("label") or "-")
        status = r.get("enabled_status") or ("enabled" if r.get("enabled", True) else "disabled")
        parts.append(_style(status, "2" if status == "disabled" else "32", use_color))
        if has_launch:
            launch = r.get("launch") or {}
            parts.append(_dim(_format_launch_text(launch), use_color))
        parts.append(_dim(_format_relative_age(r.get("updated_at")), use_color))
        table_rows.append(parts)
    lines = [_style("Known sessions:", "1", use_color), _pad_table([headers] + table_rows), ""]
    lines += [
        _style("Next actions:", "1", use_color),
        f"  {_style('cdx status', '36', use_color)}",
        f"  {_style('cdx next', '36', use_color)}",
        f"  {_style('cdx configs', '36', use_color)}",
        f"  {_style('cdx stats', '36', use_color)}",
        f"  {_style('cdx ready', '36', use_color)}",
        f"  {_style('cdx set <name> --notify on', '36', use_color)}",
        f"  {_style('cdx perm all default', '36', use_color)}",
        f"  {_style('cdx handoff <source> <target>', '36', use_color)}",
        f"  {_style('cdx history', '36', use_color)}",
        f"  {_style('cdx help', '36', use_color)}",
        f"  {_style('cdx update', '36', use_color)}",
    ]
    return "\n".join(lines)
