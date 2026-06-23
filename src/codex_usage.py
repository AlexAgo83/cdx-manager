import contextlib
import json
import os
import queue
import subprocess
import threading
from datetime import datetime, timezone

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None

CODEX_AUTH_LOCK_NAME = ".cdx-auth.lock"


@contextlib.contextmanager
def codex_auth_lock(auth_home, blocking=False):
    """Serialize codex token refreshes per CODEX_HOME.

    Codex rotates its OAuth refresh_token on refresh and invalidates the old
    one. If a status probe and an interactive session refresh the same
    auth.json concurrently, one rotates the token from under the other and that
    session gets logged out. This flock makes them take turns. Yields True when
    the lock is held, False when a non-blocking acquire found it already taken.
    ponytail: POSIX flock only; on Windows (no fcntl) this is a no-op.
    """
    if not auth_home or fcntl is None:
        yield True
        return
    try:
        os.makedirs(auth_home, exist_ok=True)
        handle = open(os.path.join(auth_home, CODEX_AUTH_LOCK_NAME), "w")
    except OSError:
        yield True
        return
    flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
    try:
        fcntl.flock(handle, flags)
    except OSError:
        handle.close()
        yield False
        return
    try:
        yield True
    finally:
        try:
            fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            handle.close()

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _format_reset_date(unix_seconds):
    if unix_seconds is None:
        return None
    try:
        dt = datetime.fromtimestamp(int(unix_seconds), tz=timezone.utc).astimezone()
    except (TypeError, ValueError, OSError):
        return None
    return f"{MONTH_ABBR[dt.month - 1]} {dt.day} {str(dt.hour).zfill(2)}:{str(dt.minute).zfill(2)}"


def _remaining_from_used_percent(value):
    if value is None:
        return None
    try:
        return max(0, min(100, round(100 - float(value))))
    except (TypeError, ValueError):
        return None


def _get_window(snapshot, duration_mins):
    for key in ("primary", "secondary"):
        window = snapshot.get(key) or {}
        if window.get("windowDurationMins") == duration_mins:
            return window
        if window.get("window_minutes") == duration_mins:
            return window
    return {}


def normalize_codex_rate_limit_snapshot(snapshot):
    if not snapshot:
        return None

    five_hour = _get_window(snapshot, 300)
    weekly = _get_window(snapshot, 10080)
    credits = snapshot.get("credits")
    credit_balance = None
    if isinstance(credits, dict):
        credit_balance = credits.get("balance")
        if not credits.get("hasCredits") and not credits.get("unlimited") and str(credit_balance or "0") == "0":
            credit_balance = None
    elif credits is not None:
        credit_balance = credits

    reset_5h_at = _format_reset_date(five_hour.get("resetsAt") or five_hour.get("resets_at"))
    reset_week_at = _format_reset_date(weekly.get("resetsAt") or weekly.get("resets_at"))

    raw_status_text = json.dumps(snapshot, sort_keys=True)
    return {
        "remaining_5h_pct": _remaining_from_used_percent(
            five_hour.get("usedPercent", five_hour.get("used_percent"))
        ),
        "remaining_week_pct": _remaining_from_used_percent(
            weekly.get("usedPercent", weekly.get("used_percent"))
        ),
        "credits": credit_balance,
        "reset_5h_at": reset_5h_at,
        "reset_week_at": reset_week_at,
        "reset_at": reset_week_at or reset_5h_at,
        "updated_at": datetime.now().astimezone().isoformat(),
        "raw_status_text": raw_status_text,
        "source_ref": "api:codex-app-server-rate-limits",
    }


def _reader_thread(stream, output):
    try:
        for line in stream:
            output.put(line)
    finally:
        output.put(None)


def _read_response(output, request_id, timeout):
    deadline = datetime.now().timestamp() + timeout
    while datetime.now().timestamp() < deadline:
        remaining = max(0.01, deadline - datetime.now().timestamp())
        try:
            line = output.get(timeout=remaining)
        except queue.Empty:
            break
        if line is None:
            break
        try:
            message = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            continue
        if message.get("id") == request_id:
            return message
    return None


def _write_json_line(process, payload):
    process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
    process.stdin.flush()


def fetch_codex_rate_limit_diagnostic(session, timeout=5, popen_factory=None):
    auth_home = session.get("authHome")
    if not auth_home:
        return {"ok": False, "reason": "missing_auth_home", "status": None}
    # Back off to cached status rather than racing an interactive session's
    # token refresh (which would log it out). The launcher holds this lock for
    # the whole session, so a busy account simply skips the live probe.
    with codex_auth_lock(auth_home) as acquired:
        if not acquired:
            return {"ok": False, "reason": "auth_locked", "status": None}
        return _probe_codex_rate_limit_diagnostic(session, auth_home, timeout, popen_factory)


def _probe_codex_rate_limit_diagnostic(session, auth_home, timeout=5, popen_factory=None):
    env = os.environ.copy()
    env["CODEX_HOME"] = auth_home
    popen_factory = popen_factory or subprocess.Popen
    process = None
    output = queue.Queue()
    try:
        process = popen_factory(
            ["codex", "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
        )
        thread = threading.Thread(target=_reader_thread, args=(process.stdout, output), daemon=True)
        thread.start()
        _write_json_line(process, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "cdx-manager", "version": "0"},
                "capabilities": {"experimentalApi": True},
            },
        })
        initialized = _read_response(output, 1, timeout)
        if not initialized or initialized.get("error"):
            return {
                "ok": False,
                "reason": "initialize_failed",
                "status": None,
                "response": initialized,
            }

        _write_json_line(process, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "account/rateLimits/read",
            "params": None,
        })
        response = _read_response(output, 2, timeout)
        if not response or response.get("error"):
            return {
                "ok": False,
                "reason": "rate_limits_read_failed",
                "status": None,
                "response": response,
            }
        result = response.get("result") or {}
        by_limit = result.get("rateLimitsByLimitId") or {}
        snapshot = by_limit.get("codex") or result.get("rateLimits")
        status = normalize_codex_rate_limit_snapshot(snapshot)
        if not status:
            return {
                "ok": False,
                "reason": "missing_rate_limits",
                "status": None,
                "response": response,
            }
        return {"ok": True, "reason": None, "status": status, "response": response}
    except FileNotFoundError as error:
        return {"ok": False, "reason": "codex_cli_not_found", "status": None, "error": str(error)}
    except (OSError, ValueError, BrokenPipeError) as error:
        return {"ok": False, "reason": "probe_failed", "status": None, "error": str(error)}
    finally:
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass


def fetch_codex_rate_limits(session, timeout=5, popen_factory=None):
    diagnostic = fetch_codex_rate_limit_diagnostic(
        session,
        timeout=timeout,
        popen_factory=popen_factory,
    )
    return diagnostic.get("status") if diagnostic.get("ok") else None
