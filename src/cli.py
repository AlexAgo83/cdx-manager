#!/usr/bin/env python3

import json
import os
import signal
import subprocess
import sys
import threading
import inspect
from datetime import datetime, timezone

from .claude_usage import refresh_claude_session_status
from .errors import CdxError
from .session_service import create_session_service

VERSION = "0.1.0"
LOG_ROTATE_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Help / version
# ---------------------------------------------------------------------------

def _print_help():
    return "\n".join([
        "cdx - terminal session manager",
        "",
        "Usage:",
        "  cdx",
        "  cdx status [name] [--json]",
        "  cdx add [provider] <name>",
        "  cdx cp <source> <dest>",
        "  cdx login <name>",
        "  cdx logout <name>",
        "  cdx rmv <name> [--force]",
        "  cdx clean [name]",
        "  cdx <name>",
        "  cdx --help",
        "  cdx --version",
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


def _format_pct(value):
    if value is None:
        return "n/a"
    return f"{value}%"


def _pad_table(columns):
    widths = [
        max(len(str(row[i])) for row in columns)
        for i in range(len(columns[0]))
    ]
    lines = []
    for row in columns:
        lines.append("  ".join(str(row[i]).ljust(widths[i]) for i in range(len(row))))
    return "\n".join(lines)


def _format_sessions(service):
    rows = service["format_list_rows"]()
    has_provider = any(r.get("provider") for r in rows)
    headers = ["SESSION"]
    if has_provider:
        headers.append("PROVIDER")
    headers.append("UPDATED")
    table_rows = []
    for r in rows:
        parts = [r["name"]]
        if has_provider:
            parts.append(r.get("provider") or "n/a")
        parts.append(r.get("updated_at") or "-")
        table_rows.append(parts)
    lines = ["Known sessions:", _pad_table([headers] + table_rows), ""]
    lines += [
        "Next actions:",
        "  cdx add <name>",
        "  cdx <name>",
        "  cdx login <name>",
        "  cdx logout <name>",
        "  cdx rmv <name>",
        "  cdx status",
    ]
    return "\n".join(lines)


def _format_status_rows(rows):
    has_provider = len({r["provider"] for r in rows}) > 1
    if has_provider:
        headers = ["SESSION", "PROVIDER", "5H LEFT", "WEEK LEFT", "RESET", "UPDATED"]
    else:
        headers = ["SESSION", "5H LEFT", "WEEK LEFT", "RESET", "UPDATED"]
    if not rows:
        return "SESSION  5H LEFT  WEEK LEFT  RESET  UPDATED\nNo saved sessions yet."
    table_rows = []
    for r in rows:
        base = [r["session_name"]]
        if has_provider:
            base.append(r.get("provider") or "n/a")
        base += [
            _format_pct(r.get("remaining_5h_pct")),
            _format_pct(r.get("remaining_week_pct")),
            r.get("reset_at") or "-",
            _format_relative_age(r.get("updated_at")),
        ]
        table_rows.append(base)
    return "\n".join([
        _pad_table([headers] + table_rows),
        "",
        "Tip: run /status in codex to refresh. Claude sessions refresh automatically.",
    ])


def _format_status_detail(row):
    lines = [
        f"Session: {row['session_name']}",
        f"Provider: {row.get('provider') or 'n/a'}",
        f"5h left: {_format_pct(row.get('remaining_5h_pct'))}",
        f"Week left: {_format_pct(row.get('remaining_week_pct'))}",
        f"Next reset: {row.get('reset_at') or 'n/a'}",
        f"Updated: {_format_relative_age(row.get('updated_at'))}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Launch helpers
# ---------------------------------------------------------------------------

def _get_auth_home(session):
    return session.get("authHome") or session.get("sessionRoot") or session.get("codexHome", "")


def _get_launch_transcript_path(session):
    return os.path.join(_get_auth_home(session), "log", "cdx-session.log")


def _rotate_log_if_needed(log_path):
    try:
        if os.path.getsize(log_path) >= LOG_ROTATE_BYTES:
            open(log_path, "w").close()
    except OSError:
        pass


def _wrap_launch_with_transcript(session, spec, capture_transcript=True):
    if not capture_transcript:
        return spec
    transcript_path = _get_launch_transcript_path(session)
    os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
    _rotate_log_if_needed(transcript_path)
    return {
        "command": "script",
        "args": ["-q", transcript_path, spec["command"]] + spec["args"],
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
        out(f"{_print_help()}\n")
        return 0

    if "--version" in argv or "-v" in argv:
        if len(argv) != 1:
            raise CdxError("Usage: cdx --version")
        out(f"{_print_version()}\n")
        return 0

    if not argv:
        out(f"{_format_sessions(service)}\n")
        return 0

    command, *rest = argv

    if command == "add":
        parsed = _parse_add_args(rest)
        session = service["create_session"](parsed["name"], parsed["provider"])
        out(f"Created session {parsed['name']} ({parsed['provider']})\n")
        _ensure_session_authentication(
            session, service, spawn=spawn, spawn_sync=spawn_sync,
            stdin_is_tty=stdin_is_tty, behavior="bootstrap", signal_emitter=signal_emitter,
        )
        now = datetime.now(timezone.utc).isoformat()
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
        out(f"Copied session {parsed['source']} to {parsed['dest']}{overwritten}\n")
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
                out("Cancelled.\n")
                return 0
        service["remove_session"](parsed["name"])
        out(f"Removed session {parsed['name']}\n")
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
            log_path = _get_launch_transcript_path(session)
            try:
                size = os.path.getsize(log_path)
                open(log_path, "w").close()
                out(f"Cleared {session['name']} log ({round(size / 1024)} KB freed)\n")
            except OSError:
                out(f"{session['name']}: no log found\n")
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
            out(f"{_format_status_rows(rows)}\n")
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
        out(f"{_format_status_detail(row)}\n")
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
        now = datetime.now(timezone.utc).isoformat()
        service["update_auth_state"](rest[0], lambda auth: {
            **auth, "status": "authenticated",
            "lastCheckedAt": now, "lastAuthenticatedAt": now,
        })
        out(f"Reauthenticated session {session['name']} ({session['provider']})\n")
        return 0

    if command == "logout":
        if len(rest) != 1:
            raise CdxError("Usage: cdx logout <name>")
        session = service["get_session"](rest[0])
        if not session:
            raise CdxError(f"Unknown session: {rest[0]}")
        _run_interactive_provider_command(session, "logout", spawn=spawn, signal_emitter=signal_emitter)
        now = datetime.now(timezone.utc).isoformat()
        service["update_auth_state"](rest[0], lambda auth: {
            **auth, "status": "logged_out",
            "lastCheckedAt": now, "lastLoggedOutAt": now,
        })
        out(f"Logged out session {session['name']} ({session['provider']})\n")
        return 0

    if command in ("help",):
        out(f"{_print_help()}\n")
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
        out(f"Launching {session['provider']} session {session['name']}\n")
        _run_interactive_provider_command(session, "launch", spawn=spawn, signal_emitter=signal_emitter)
        return 0

    raise CdxError(f"Unknown command: {command}. Use cdx --help.")


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except CdxError as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(error.exit_code)
