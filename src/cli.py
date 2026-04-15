#!/usr/bin/env python3

import json
import os
import signal
import subprocess
import sys
import threading
import inspect
import glob
import re
from datetime import datetime, timezone

from .claude_usage import refresh_claude_session_status
from .errors import CdxError
from .session_service import create_session_service

VERSION = "0.1.1"
LOG_ROTATE_BYTES = 10 * 1024 * 1024  # 10 MB
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


# ---------------------------------------------------------------------------
# Help / version
# ---------------------------------------------------------------------------

def _print_help(use_color=False):
    return "\n".join([
        _style("cdx - terminal session manager", "1", use_color),
        "",
        _style("Usage:", "1", use_color),
        f"  {_style('cdx', '36', use_color)}",
        f"  {_style('cdx status [name] [--json]', '36', use_color)}",
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


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_relative_age(iso_value):
    if not iso_value:
        return "-"
    try:
        ts = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
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


def _local_now_iso():
    return datetime.now().astimezone().isoformat()


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
    if value == 0:
        return _style(text, "31", use_color)
    if value <= 10:
        return _style(text, "33", use_color)
    return _style(text, "32", use_color)


def _success(text, use_color=False):
    return _style(text, "32", use_color)


def _warn(text, use_color=False):
    return _style(text, "33", use_color)


def _info(text, use_color=False):
    return _style(text, "36", use_color)


def _dim(text, use_color=False):
    return _style(text, "2", use_color)


def format_error(error, env=None, stderr=None):
    return _style(str(error), "31", _should_use_color(env or os.environ, stderr or sys.stderr))


def _format_sessions(service, use_color=False):
    rows = service["format_list_rows"]()
    has_provider = any(r.get("provider") for r in rows)
    headers = ["SESSION"]
    if has_provider:
        headers.append("PROVIDER")
    headers.append("UPDATED")
    headers = [_style(header, "1", use_color) for header in headers]
    table_rows = []
    for r in rows:
        parts = [r["name"]]
        if has_provider:
            parts.append(r.get("provider") or "n/a")
        parts.append(_dim(_format_relative_age(r.get("updated_at")), use_color))
        table_rows.append(parts)
    lines = [_style("Known sessions:", "1", use_color), _pad_table([headers] + table_rows), ""]
    lines += [
        _style("Next actions:", "1", use_color),
        f"  {_style('cdx add <name>', '36', use_color)}",
        f"  {_style('cdx <name>', '36', use_color)}",
        f"  {_style('cdx login <name>', '36', use_color)}",
        f"  {_style('cdx logout <name>', '36', use_color)}",
        f"  {_style('cdx ren <source> <dest>', '36', use_color)}",
        f"  {_style('cdx rmv <name>', '36', use_color)}",
        f"  {_style('cdx status', '36', use_color)}",
    ]
    return "\n".join(lines)


def _format_status_rows(rows, use_color=False):
    has_provider = len({r["provider"] for r in rows}) > 1
    if has_provider:
        headers = ["SESSION", "PROV.", "OK", "5H", "WEEK", "BLOCK", "CR", "RESET 5H", "RESET WEEK", "UPDATED"]
    else:
        headers = ["SESSION", "OK", "5H", "WEEK", "BLOCK", "CR", "RESET 5H", "RESET WEEK", "UPDATED"]
    if not rows:
        return "SESSION  OK  5H  WEEK  BLOCK  CR  RESET 5H  RESET WEEK  UPDATED\nNo saved sessions yet."
    headers = [_style(header, "1", use_color) for header in headers]
    priority = _recommend_priority_sessions(rows)
    table_rows = []
    for r in priority:
        base = [r["session_name"]]
        if has_provider:
            base.append(r.get("provider") or "n/a")
        block = _format_blocking_quota(r)
        credits = str(r["credits"]) if r.get("credits") is not None else "-"
        base += [
            _style_pct(r.get("available_pct"), use_color),
            _style_pct(r.get("remaining_5h_pct"), use_color),
            _style_pct(r.get("remaining_week_pct"), use_color),
            _style(block, "33" if block not in ("?", "-") else "2", use_color),
            _style(credits, "33" if r.get("credits") is not None else "2", use_color),
            _style_reset_time(r.get("reset_5h_at"), use_color),
            _style_reset_time(r.get("reset_week_at"), use_color),
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


# ---------------------------------------------------------------------------
# Launch helpers
# ---------------------------------------------------------------------------

def _get_auth_home(session):
    return session.get("authHome") or session.get("sessionRoot") or session.get("codexHome", "")


def _get_launch_transcript_path(session):
    return os.path.join(_get_auth_home(session), "log", "cdx-session.log")


def _get_launch_transcript_dir(session):
    return os.path.join(_get_auth_home(session), "log")


def _build_launch_transcript_path(session):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return os.path.join(
        _get_launch_transcript_dir(session),
        f"cdx-session-{stamp}-{os.getpid()}.log",
    )


def _list_launch_transcript_paths(session):
    log_dir = _get_launch_transcript_dir(session)
    if not os.path.isdir(log_dir):
        return []
    paths = set(glob.glob(os.path.join(log_dir, "cdx-session*.log")))
    legacy = _get_launch_transcript_path(session)
    if os.path.exists(legacy):
        paths.add(legacy)
    return sorted(paths)


def _rotate_log_if_needed(log_path):
    try:
        if os.path.getsize(log_path) >= LOG_ROTATE_BYTES:
            open(log_path, "w").close()
    except OSError:
        pass


def _wrap_launch_with_transcript(session, spec, capture_transcript=True):
    if not capture_transcript:
        return spec
    transcript_path = _build_launch_transcript_path(session)
    os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
    _rotate_log_if_needed(transcript_path)
    return {
        "command": "script",
        "args": ["-q", "-F", transcript_path, spec["command"]] + spec["args"],
        "options": spec["options"],
        "label": spec["label"],
    }


def _build_launch_spec(session, cwd=None, env_override=None):
    cwd = cwd or os.getcwd()
    env_override = env_override or {}
    if session["provider"] == "claude":
        return {
            "command": "claude",
            "args": ["--name", session["name"]],
            "options": {
                "cwd": cwd,
                "env": {**os.environ, **env_override, "HOME": _get_auth_home(session)},
            },
            "label": "claude",
        }
    return _wrap_launch_with_transcript(session, {
        "command": "codex",
        "args": ["--no-alt-screen", "--cd", cwd],
        "options": {
            "env": {**os.environ, **env_override, "CODEX_HOME": _get_auth_home(session)},
        },
        "label": "codex",
    })


def _build_login_status_spec(session, env_override=None):
    env = {**os.environ, **(env_override or {})}
    if session["provider"] == "claude":
        env["HOME"] = _get_auth_home(session)
        def parser(output):
            try:
                return bool(json.loads(output or "{}").get("loggedIn"))
            except (json.JSONDecodeError, AttributeError):
                return False
        return {"command": "claude", "args": ["auth", "status"], "env": env,
                "parser": parser, "label": "claude auth status"}
    env["CODEX_HOME"] = _get_auth_home(session)
    def parser(output):
        if "Not logged in" in (output or ""):
            return False
        return "Logged in" in (output or "")
    return {"command": "codex", "args": ["login", "status"], "env": env,
            "parser": parser, "label": "codex login status"}


def _build_auth_action_spec(session, action, cwd=None, env_override=None):
    cwd = cwd or os.getcwd()
    env = {**os.environ, **(env_override or {})}
    if session["provider"] == "claude":
        env["HOME"] = _get_auth_home(session)
        return {"command": "claude", "args": ["auth", action],
                "options": {"cwd": cwd, "env": env}, "label": f"claude auth {action}"}
    env["CODEX_HOME"] = _get_auth_home(session)
    return {"command": "codex", "args": [action],
            "options": {"cwd": cwd, "env": env}, "label": f"codex {action}"}


def _probe_provider_auth(session, spawn_sync=None, env_override=None):
    spawn_sync = spawn_sync or subprocess.run
    spec = _build_login_status_spec(session, env_override)
    if spawn_sync is subprocess.run:
        result = subprocess.run(
            [spec["command"]] + spec["args"],
            env=spec["env"],
            capture_output=True, text=True,
        )
        output = (result.stdout or "") + (result.stderr or "")
    else:
        result = spawn_sync(spec["command"], spec["args"], spec)
        error = result.get("error") if isinstance(result, dict) else getattr(result, "error", None)
        if error:
            raise CdxError(
                f"Failed to check login status for {session['name']}: {getattr(error, 'message', str(error))}"
            )
        stdout = result.get("stdout") if isinstance(result, dict) else getattr(result, "stdout", "")
        stderr = result.get("stderr") if isinstance(result, dict) else getattr(result, "stderr", "")
        output = (stdout or "") + (stderr or "")
    return spec["parser"](output)


def _signal_exit_code(sig):
    return {signal.SIGHUP: 129, signal.SIGINT: 130, signal.SIGTERM: 143}.get(sig, 1)


def _run_interactive_provider_command(session, action, spawn=None, cwd=None,
                                       env_override=None, signal_emitter=None):
    spawn = spawn or subprocess.Popen
    spec = (
        _build_launch_spec(session, cwd=cwd, env_override=env_override)
        if action == "launch"
        else _build_auth_action_spec(session, action, cwd=cwd, env_override=env_override)
    )
    child = spawn(
        [spec["command"]] + spec["args"],
        **{k: v for k, v in spec.get("options", {}).items() if k != "stdio"},
    )

    forwarded_signal = [None]
    handlers = []

    def forward(sig, _frame=None):
        forwarded_signal[0] = sig
        try:
            if hasattr(child, "send_signal"):
                child.send_signal(sig)
            elif hasattr(child, "kill"):
                child.kill(sig)
        except Exception:
            pass

    original_handlers = {}
    use_emitter = hasattr(signal_emitter, "on") and hasattr(signal_emitter, "removeListener")

    if use_emitter:
        for sig in ("SIGINT", "SIGTERM", "SIGHUP"):
            handler = lambda current_sig=sig: forward(getattr(signal, current_sig), None)
            handlers.append((sig, handler))
            signal_emitter.on(sig, handler)
    else:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            try:
                original_handlers[sig] = signal.signal(sig, forward)
            except (OSError, ValueError):
                pass

    try:
        child.wait()
    finally:
        if use_emitter:
            for sig, handler in handlers:
                try:
                    signal_emitter.removeListener(sig, handler)
                except Exception:
                    pass
        else:
            for sig, handler in original_handlers.items():
                try:
                    signal.signal(sig, handler)
                except (OSError, ValueError):
                    pass

    if forwarded_signal[0] is not None:
        raise CdxError(
            f"{spec['label']} interrupted by {forwarded_signal[0].name} for session {session['name']}",
            _signal_exit_code(forwarded_signal[0]),
        )
    if child.returncode != 0:
        raise CdxError(
            f"{spec['label']} exited with code {child.returncode} for session {session['name']}"
        )


def _ensure_session_authentication(session, service, spawn=None, spawn_sync=None,
                                    stdin_is_tty=True, env_override=None, behavior="launch",
                                    signal_emitter=None):
    is_authenticated = _probe_provider_auth(session, spawn_sync=spawn_sync, env_override=env_override)
    if is_authenticated:
        return {"authenticated": True, "checked": True}
    if behavior == "probe-only":
        return {"authenticated": False, "checked": True}
    if behavior == "launch":
        raise CdxError(
            f"Session {session['name']} is not authenticated. Run: cdx login {session['name']}"
        )
    if not stdin_is_tty:
        raise CdxError(
            f"Session {session['name']} is not authenticated. Run: cdx login {session['name']}"
        )
    _run_interactive_provider_command(
        session, "login", spawn=spawn, env_override=env_override, signal_emitter=signal_emitter
    )
    return {"authenticated": True, "checked": True, "bootstrapped": True}


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
# Claude refresh
# ---------------------------------------------------------------------------

def _refresh_claude_sessions(service, refresh_fn=None):
    refresh_fn = refresh_fn or refresh_claude_session_status
    sessions = service["list_sessions"]()
    claude_sessions = [s for s in sessions if s["provider"] == "claude"]
    if not claude_sessions:
        return

    errors = []
    results = {}
    threads = []

    def fetch(s):
        try:
            usage = refresh_fn(s)
            if inspect.isawaitable(usage):
                import asyncio
                usage = asyncio.run(usage)
            if usage:
                results[s["name"]] = usage
        except Exception as e:
            errors.append(e)

    for s in claude_sessions:
        t = threading.Thread(target=fetch, args=(s,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    for name, usage in results.items():
        try:
            service["record_status"](name, usage)
        except CdxError:
            pass


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
        args = [a for a in rest if a != "--json"]

        _refresh_claude_sessions(service, refresh_fn)

        if len(args) == 0:
            rows = service["get_status_rows"]()
            if json_flag:
                out(f"{json.dumps(rows, indent=2)}\n")
                return 0
            out(f"{_format_status_rows(rows, use_color=use_color)}\n")
            return 0
        if len(args) != 1:
            raise CdxError("Usage: cdx status [name] [--json]")
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
